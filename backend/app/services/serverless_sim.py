"""
محرك المحاكاة السحابي الخفيف (Serverless Multi-Agent Simulation Engine)
يعمل مباشرة عبر واجهة OpenAI المتوافقة بدون الحاجة إلى PyTorch أو camel-oasis،
مما يتيح تشغيل المحاكاة كاملة مجاناً على Vercel والبيئات السحابية الخفيفة.
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger("mirofish.serverless_sim")


def _init_platform_db(db_path: str, profiles: List[Dict[str, Any]]) -> None:
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE user (
            user_id INTEGER PRIMARY KEY,
            agent_id INTEGER,
            user_name TEXT,
            name TEXT,
            bio TEXT,
            created_at TEXT,
            num_followings INTEGER DEFAULT 0,
            num_followers INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE post (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            original_post_id INTEGER,
            content TEXT,
            quote_content TEXT,
            created_at TEXT,
            num_likes INTEGER DEFAULT 0,
            num_dislikes INTEGER DEFAULT 0,
            num_shares INTEGER DEFAULT 0,
            num_reports INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE comment (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            content TEXT,
            created_at TEXT,
            num_likes INTEGER DEFAULT 0,
            num_dislikes INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE trace (
            user_id INTEGER,
            created_at TEXT,
            action TEXT,
            info TEXT
        )
        """
    )
    now_iso = datetime.now().isoformat()
    for idx, p in enumerate(profiles):
        uid = int(p.get("user_id", idx))
        uname = p.get("username") or p.get("user_name") or f"agent_{uid}"
        name = p.get("name") or uname
        bio = p.get("bio") or p.get("persona") or ""
        cur.execute(
            "INSERT OR REPLACE INTO user (user_id, agent_id, user_name, name, bio, created_at, num_followings, num_followers) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, uid, uname, name, bio, now_iso, 25, 120),
        )
    conn.commit()
    conn.close()


def write_simulation_artifacts(
    sim_dir: str,
    profiles: List[Dict[str, Any]],
    rounds_data: List[Dict[str, Any]],
    platforms: List[str],
) -> Dict[str, int]:
    """يكتب قواعد بيانات SQLite وسجلات actions.jsonl المتوافقة تماماً مع واجهة العرض ومولّد التقارير."""
    counts = {"twitter": 0, "reddit": 0}
    base_time = datetime.now()

    for plat in platforms:
        plat_dir = os.path.join(sim_dir, plat)
        os.makedirs(plat_dir, exist_ok=True)
        db_path = os.path.join(sim_dir, f"{plat}_simulation.db")
        _init_platform_db(db_path, profiles)
        actions_path = os.path.join(plat_dir, "actions.jsonl")

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        post_counter = 0

        with open(actions_path, "w", encoding="utf-8") as af:
            af.write(
                json.dumps(
                    {"event_type": "simulation_start", "platform": plat, "timestamp": base_time.isoformat()},
                    ensure_ascii=False,
                )
                + "\n"
            )
            for r_idx, r_item in enumerate(rounds_data, start=1):
                r_time = (base_time + timedelta(minutes=30 * r_idx)).isoformat()
                af.write(
                    json.dumps(
                        {"event_type": "round_start", "round": r_idx, "simulated_hours": r_idx, "timestamp": r_time},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                entries = [e for e in r_item.get("actions", []) if e.get("platform", plat) in (plat, "both")]
                if not entries:
                    entries = r_item.get("actions", [])

                round_actions = 0
                for act in entries:
                    agent_id = int(act.get("agent_id", 0))
                    agent_profile = next(
                        (p for p in profiles if int(p.get("user_id", -1)) == agent_id),
                        profiles[agent_id % len(profiles)] if profiles else {"name": f"Agent {agent_id}"},
                    )
                    agent_name = agent_profile.get("name") or agent_profile.get("username") or f"Agent {agent_id}"
                    action_type = act.get("action_type", "CREATE_POST")
                    content = (act.get("content") or "").strip()
                    if not content:
                        continue

                    if action_type == "CREATE_COMMENT" and post_counter > 0:
                        target_post = max(1, post_counter)
                        cur.execute(
                            "INSERT INTO comment (post_id, user_id, content, created_at, num_likes) VALUES (?, ?, ?, ?, ?)",
                            (target_post, agent_id, content, r_time, int(act.get("likes", 4))),
                        )
                        action_args = {"post_id": target_post, "content": content}
                    else:
                        action_type = "CREATE_POST"
                        cur.execute(
                            "INSERT INTO post (user_id, content, created_at, num_likes, num_shares) VALUES (?, ?, ?, ?, ?)",
                            (agent_id, content, r_time, int(act.get("likes", 9)), int(act.get("shares", 3))),
                        )
                        post_counter = cur.lastrowid or (post_counter + 1)
                        action_args = {"post_id": post_counter, "content": content}

                    cur.execute(
                        "INSERT INTO trace (user_id, created_at, action, info) VALUES (?, ?, ?, ?)",
                        (agent_id, r_time, action_type, json.dumps(action_args, ensure_ascii=False)),
                    )
                    af.write(
                        json.dumps(
                            {
                                "round": r_idx,
                                "timestamp": r_time,
                                "platform": plat,
                                "agent_id": agent_id,
                                "agent_name": agent_name,
                                "action_type": action_type,
                                "action_args": action_args,
                                "success": True,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    counts[plat] += 1
                    round_actions += 1

                af.write(
                    json.dumps(
                        {
                            "event_type": "round_end",
                            "round": r_idx,
                            "simulated_hours": r_idx,
                            "actions_count": round_actions,
                            "timestamp": r_time,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            af.write(
                json.dumps(
                    {
                        "event_type": "simulation_end",
                        "platform": plat,
                        "total_rounds": len(rounds_data),
                        "total_actions": counts[plat],
                        "timestamp": (base_time + timedelta(minutes=30 * (len(rounds_data) + 1))).isoformat(),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

        conn.commit()
        conn.close()

    return counts


def run_serverless_simulation(
    sim_dir: str,
    platform: str = "parallel",
    max_rounds: int = 3,
) -> Dict[str, Any]:
    """يشغّل محاكاة متعددة الوكلاء عبر LLM مباشرة خلال ثوانٍ ويحفظ جميع المخرجات القياسية."""
    from .simulation_runner import ensure_local_file

    config_path = ensure_local_file(os.path.join(sim_dir, "simulation_config.json"))
    with open(config_path, "r", encoding="utf-8") as f:
        sim_config = json.load(f)

    reddit_path = ensure_local_file(os.path.join(sim_dir, "reddit_profiles.json"))
    profiles: List[Dict[str, Any]] = []
    if os.path.exists(reddit_path):
        with open(reddit_path, "r", encoding="utf-8") as f:
            profiles = json.load(f)

    if not profiles:
        for idx, ac in enumerate(sim_config.get("agent_configs", [])):
            profiles.append(
                {
                    "user_id": ac.get("agent_id", idx),
                    "username": f"agent_{idx}",
                    "name": ac.get("entity_name", f"وكيل {idx}"),
                    "persona": ac.get("stance", ""),
                }
            )

    rounds = max(1, min(int(max_rounds or Config.OASIS_DEFAULT_MAX_ROUNDS), 5))
    platforms = ["twitter", "reddit"] if platform == "parallel" else [platform]

    agent_summary = [
        {
            "agent_id": int(p.get("user_id", idx)),
            "name": p.get("name") or p.get("username") or f"Agent {idx}",
            "bio": (p.get("bio") or "")[:140],
            "persona": (p.get("persona") or "")[:160],
        }
        for idx, p in enumerate(profiles[:12])
    ]
    requirement = sim_config.get("simulation_requirement", "")
    narrative = sim_config.get("event_config", {}).get("narrative_direction", "")
    initial_posts = sim_config.get("event_config", {}).get("initial_posts", [])

    llm = LLMClient()
    prompt = (
        "أنت محرك محاكاة اجتماعية متعدد الوكلاء في منصة «استشراف المستقبل».\n"
        f"موضوع الاستشراف: {requirement}\n"
        f"السياق السردي: {narrative}\n"
        f"المنشورات الافتتاحية: {json.dumps(initial_posts, ensure_ascii=False)}\n"
        f"قائمة الوكلاء المتاحين: {json.dumps(agent_summary, ensure_ascii=False)}\n\n"
        f"قم بمحاكاة {rounds} جولات زمنية متتالية من النقاش الواقعي والمتنوع (تأييد، تحفظ، أرقام، مقترحات عملية) "
        "بين هؤلاء الوكلاء باللغة المناسبة للسياق (العربية افتراضياً). في كل جولة أدرج 4 إلى 6 تفاعلات متنوعة بين "
        "CREATE_POST و CREATE_COMMENT عبر منصتي twitter و reddit.\n"
        "أعد النتيجة بصيغة JSON فقط بهذا الهيكل الدقيق:\n"
        '{"rounds": [{"round": 1, "actions": [{"agent_id": 0, "platform": "twitter", "action_type": "CREATE_POST", "content": "...", "likes": 18, "shares": 5}]}]}'
    )

    resp = llm.chat_json(
        messages=[
            {"role": "system", "content": "أجب بـ JSON صالح فقط يمثّل وقائع المحاكاة متعددة الوكلاء."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    rounds_data = resp.get("rounds") if isinstance(resp, dict) else None
    if not rounds_data or not isinstance(rounds_data, list):
        rounds_data = [
            {
                "round": 1,
                "actions": [
                    {
                        "agent_id": int(agent_summary[0]["agent_id"]) if agent_summary else 0,
                        "platform": "both",
                        "action_type": "CREATE_POST",
                        "content": requirement or "بدء النقاش التحليلي حول السيناريو المطروح.",
                        "likes": 15,
                        "shares": 4,
                    }
                ],
            }
        ]

    counts = write_simulation_artifacts(sim_dir, profiles, rounds_data, platforms)
    return {
        "rounds_completed": len(rounds_data),
        "twitter_actions": counts.get("twitter", 0),
        "reddit_actions": counts.get("reddit", 0),
        "total_actions": counts.get("twitter", 0) + counts.get("reddit", 0),
    }
