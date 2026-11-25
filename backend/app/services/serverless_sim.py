"""
محرك المحاكاة السحابي الخفيف (Serverless Multi-Agent Simulation Engine)
يعمل مباشرة عبر واجهة OpenAI المتوافقة بدون الحاجة إلى PyTorch أو camel-oasis،
مما يتيح تشغيل المحاكاة كاملة مجاناً على Vercel والبيئات السحابية الخفيفة.
"""

import os
import json
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

from ..config import Config
from .research_integrity import EVIDENCE_POLICY
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from . import platform_inputs
from . import platforms as platform_registry

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
    counts = {plat: 0 for plat in platforms}
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
        plat_posts: List[int] = []  # معرّفات المنشورات في هذه المنصّة بالترتيب

        with open(actions_path, "w", encoding="utf-8") as af:
            af.write(
                json.dumps(
                    {"event_type": "simulation_start", "platform": plat, "timestamp": base_time.isoformat()},
                    ensure_ascii=False,
                )
                + "\n"
            )
            for r_idx, r_item in enumerate(rounds_data, start=1):
                if not isinstance(r_item, dict):
                    continue
                r_time = (base_time + timedelta(minutes=30 * r_idx)).isoformat()
                af.write(
                    json.dumps(
                        {"event_type": "round_start", "round": r_idx, "simulated_hours": r_idx, "timestamp": r_time},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                raw_actions = [e for e in (r_item.get("actions") or []) if isinstance(e, dict)]
                # كل فعل يُكتب في منصّته فقط. الخيار القديم (نسخ كل الأفعال
                # إلى المنصّة الفارغة) كان يضاعف العدّ ويجعل «أفعال فيسبوك»
                # تساوي الإجمالي، فحذفناه.
                entries = [
                    e for e in raw_actions
                    if (str(e.get("platform") or "").strip().lower() or plat) in (plat, "both")
                ]

                round_actions = 0
                for act_idx, act in enumerate(entries):
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

                    # الأفعال كانت تحمل وقت الجولة نفسه بالثانية، فيبدو الخط
                    # الزمني ثابتًا؛ كل فعل يتقدّم ٤٠ ثانية عن سابقه.
                    act_time = (
                        base_time
                        + timedelta(minutes=30 * r_idx, seconds=40 * act_idx)
                    ).isoformat()

                    if action_type == "CREATE_COMMENT" and post_counter > 0:
                        # التعليق يذهب للمنشور المطلوب داخل المنصّة نفسها
                        wanted = int(act.get("post_id") or 0)
                        if wanted > 0 and wanted <= len(plat_posts):
                            target_post = plat_posts[wanted - 1]
                        else:
                            target_post = plat_posts[-1] if plat_posts else max(1, post_counter)
                        cur.execute(
                            "INSERT INTO comment (post_id, user_id, content, created_at, num_likes) VALUES (?, ?, ?, ?, ?)",
                            (target_post, agent_id, content, act_time, int(act.get("likes", 4))),
                        )
                        action_args = {"post_id": target_post, "content": content}
                    else:
                        action_type = "CREATE_POST"
                        cur.execute(
                            "INSERT INTO post (user_id, content, created_at, num_likes, num_shares) VALUES (?, ?, ?, ?, ?)",
                            (agent_id, content, act_time, int(act.get("likes", 9)), int(act.get("shares", 3))),
                        )
                        post_counter = cur.lastrowid or (post_counter + 1)
                        plat_posts.append(post_counter)
                        action_args = {"post_id": post_counter, "content": content}

                    cur.execute(
                        "INSERT INTO trace (user_id, created_at, action, info) VALUES (?, ?, ?, ?)",
                        (agent_id, act_time, action_type, json.dumps(action_args, ensure_ascii=False)),
                    )
                    af.write(
                        json.dumps(
                            {
                                "round": r_idx,
                                "timestamp": act_time,
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


def _clamp_platforms(rounds_data: List[Dict[str, Any]],
                     platforms: List[str]) -> List[Dict[str, Any]]:
    """يمنع المنصّات المخترعة ويضمن توزيع الجولة على أكثر من منصّة.

    النموذج قد يخرج بـ facebook أو whatsapp من تلقاء نفسه، لكنه أيضًا قد
    يخترع أسماء غريبة؛ نُلزمه بالقائمة المتاحة فقط.
    """
    if not platforms:
        return rounds_data
    allowed = set(platforms)
    used_all: set = set()
    for r_item in rounds_data:
        actions = r_item.get("actions") or []
        seen = set()
        for i, act in enumerate(actions):
            raw = str(act.get("platform") or "").strip().lower()
            raw = {"x": "twitter", "fb": "facebook"}.get(raw, raw)
            if raw not in allowed:
                raw = platforms[(i * 3 + 1) % len(platforms)]
            act["platform"] = raw
            seen.add(raw)
        # إن كانت الجولة كلها على منصّة واحدة نوزّع بعض الأفعال على منصّة ثانية
        if len(platforms) > 1 and len(seen) == 1 and len(actions) > 1:
            second = next(p for p in platforms if p not in seen)
            for act in actions[1::2]:
                act["platform"] = second

        # ضمان حضور: كل منصّة متاحة يجب أن تظهر في الجولة ما دام فيها أفعال
        # كافية — كان النموذج يُهمل ريديت تمامًا في بعض الجولات.
        counts: Dict[str, int] = {}
        for act in actions:
            counts[act["platform"]] = counts.get(act["platform"], 0) + 1
        for missing in [p for p in platforms if p not in counts]:
            if len(actions) < len(platforms):
                break
            donor = max(counts, key=lambda k: counts[k])
            if counts[donor] <= 1:
                break
            for act in actions:
                if act.get("platform") == donor and act.get("action_type") != "CREATE_POST":
                    act["platform"] = missing
                    counts[donor] -= 1
                    counts[missing] = 1
                    break
        used_all |= {a.get("platform") for a in actions}
    return rounds_data


def max_sim_rounds() -> int:
    """أقصى عدد جولات يسمح به المحرّك (قابل للتغيير بمتغيّر بيئة)."""
    try:
        return max(1, int(getattr(Config, "OASIS_MAX_SIM_ROUNDS", 12) or 12))
    except (TypeError, ValueError):
        return 12



def _norm_text(text: str) -> str:
    """يبسّط النص للمقارنة: بلا رموز ولا مسافات زائدة."""
    import re as _re
    t = _re.sub(r"[*_`#>•\-\[\]()\"«»\u2066\u2069]|#", " ", str(text or ""))
    return _re.sub(r"\s+", " ", t).strip()


def _shingles(text: str, k: int = 4) -> set:
    words = _norm_text(text).split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def _drop_repeats(rounds_data: List[Dict[str, Any]], thresh: float = 0.70) -> int:
    """يحذف الفعل الذي يعيد فكرة سبق قولها (بأي وكيل، على أي منصّة).

    المحرك يطلب من النموذج تطورًا جديدًا كل جولة، لكن النموذج يعيد الصياغة
    نفسها؛ فالتنقية هنا حتمية ولا تعتمد على طاعة النموذج.
    """
    seen: List[set] = []
    removed = 0
    for r_item in rounds_data:
        kept = []
        for act in (r_item.get("actions") or []):
            sh = _shingles(act.get("content"))
            if sh:
                dup = False
                for other in seen:
                    if not other:
                        continue
                    inter = len(sh & other)
                    if inter / min(len(sh), len(other)) >= thresh:
                        dup = True
                        break
                if dup:
                    removed += 1
                    continue
                seen.append(sh)
            kept.append(act)
        r_item["actions"] = kept
    return removed

def _clean_rounds(raw: Any) -> List[Dict[str, Any]]:
    """يُنقّي ما يعيده النموذج: كائنات فقط، ولكل فعل محتوى غير فارغ."""
    if not isinstance(raw, list):
        return []
    cleaned: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        actions = []
        for act in (item.get("actions") or []):
            if not isinstance(act, dict):
                continue
            if not str(act.get("content") or "").strip():
                continue
            actions.append(act)
        if actions:
            cleaned.append({**item, "actions": actions})
    return cleaned


def _context_digest(rounds_data: List[Dict[str, Any]], limit: int = 10) -> str:
    """ملخّص قصير لما جرى في الجولات السابقة لتبقى المحاكاة متصلة السياق."""
    lines: List[str] = []
    for r_item in rounds_data[-2:]:
        for act in (r_item.get("actions") or [])[-limit:]:
            who = act.get("agent_name") or act.get("agent_id")
            text = str(act.get("content") or "").strip().replace("\n", " ")
            if text:
                lines.append(f"- [{act.get('platform')}] {who}: {text[:120]}")
    if not lines:
        return ""
    return "آخر ما جرى في المحاكاة:\n" + "\n".join(lines[-limit:])


def _posts_by_platform(rounds_data: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """يجمع المنشورات المنشأة حتى الآن (مرقّمة داخل كل منصّة) لتعليق عليها."""
    posts: Dict[str, List[Dict[str, Any]]] = {}
    for r_item in rounds_data:
        for act in (r_item.get("actions") or []):
            if str(act.get("action_type") or "CREATE_POST").upper() == "CREATE_COMMENT":
                continue
            plat = str(act.get("platform") or "").strip().lower()
            posts.setdefault(plat, []).append(
                {
                    "post_id": len(posts.get(plat, [])) + 1,
                    "agent_name": act.get("agent_name") or act.get("agent_id"),
                    "content": str(act.get("content") or "")[:100],
                }
            )
    return posts


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

    # عدد الجولات: طلب المستخدم، وإلا توصية إعدادات المحاكاة، وإلا الافتراضي.
    # السقف القديم (5) كان يبتلع طلب المستخدم ويُبقي التفاعل ضئيلًا.
    recommended = 0
    try:
        time_cfg = sim_config.get("time_config") or {}
        hours = float(time_cfg.get("total_simulation_hours") or 0)
        minutes = float(time_cfg.get("minutes_per_round") or 0)
        if hours > 0 and minutes > 0:
            recommended = int(hours * 60 / minutes)
    except (TypeError, ValueError):
        recommended = 0
    requested = int(max_rounds or recommended or Config.OASIS_DEFAULT_MAX_ROUNDS)
    rounds = max(1, min(requested, max_sim_rounds()))
    platforms = platform_registry.normalize(platform)

    # سقف الوكلاء المشاركين في الجولة: كان 12، والمطلوب توزيعهم على خمس
    # منصّات، فنرفعه إلى 16 ونضيف لكل وكيل منصّته الأساسية.
    # سقف الوكلاء: كان 16. جمهور المحاكاة يحتاج تنوّعًا أوسع (سائق، تاجر،
    # موظف، طالب، أمّ، نازح…) ليصير التفاعل كثيفًا وليس مجرد بضعة أصوات.
    agent_summary = [
        {
            "agent_id": int(p.get("user_id", idx)),
            "name": p.get("name") or p.get("username") or f"Agent {idx}",
            "bio": (p.get("bio") or "")[:140],
            "persona": (p.get("persona") or "")[:160],
            "primary_platform": platform_registry.preferred_for(idx, platforms),
        }
        for idx, p in enumerate(profiles[:24])
    ]
    # أرقام المستخدم الحقيقية (إن أدخلها) توزّع الأفعال بحسب حجم جمهوره فعلاً
    user_inputs = platform_inputs.load(os.path.basename(os.path.abspath(sim_dir)))
    inputs_block = platform_inputs.prompt_block(user_inputs, platforms, rounds * 6)

    requirement = sim_config.get("simulation_requirement", "")
    narrative = sim_config.get("event_config", {}).get("narrative_direction", "")
    initial_posts = sim_config.get("event_config", {}).get("initial_posts", [])

    # منشورات حقيقية منشورة على حسابات صاحب المشروع (فيسبوك/تيك توك/إكس)،
    # تُقرأ من روابط الصفحات التي أدخلها. تبدأ المحاكاة منها لأن القارئ
    # يستطيع فتحها والتحقق منها، وهي أولى بالثقة من منشورات مُتخيَّلة.
    real_by_platform: Dict[str, List[Dict[str, Any]]] = {}
    platform_mentions: Dict[str, List[Dict[str, Any]]] = {}

    def _read_json(rel: str):
        path = os.path.join(sim_dir, rel)
        if not os.path.exists(path):
            path = ensure_local_file(os.path.join(sim_dir, rel))
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    try:
        bundle = _read_json("platform_posts.json")
        if isinstance(bundle, dict):
            for plat, entry in bundle.items():
                posts = (entry or {}).get("posts") if isinstance(entry, dict) else entry
                if isinstance(posts, list) and posts:
                    real_by_platform[str(plat)] = [
                        p for p in posts if isinstance(p, dict) and p.get("text")
                    ]
                mentions = (entry or {}).get("mentions") if isinstance(entry, dict) else None
                if isinstance(mentions, list) and mentions:
                    platform_mentions[str(plat)] = [
                        m for m in mentions if isinstance(m, dict) and m.get("text")
                    ]
        # توافق: ملف فيسبوك القديم
        legacy = _read_json("facebook_posts.json")
        if isinstance(legacy, list) and legacy and "facebook" not in real_by_platform:
            real_by_platform["facebook"] = [
                p for p in legacy if isinstance(p, dict) and p.get("text")
            ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("تعذر قراءة منشورات الحسابات الحقيقية: %s", exc)

    real_posts_block = ""
    if real_by_platform:
        sections = []
        total = 0
        for plat, posts in real_by_platform.items():
            name = platform_registry.label(plat) if plat in platform_registry.ORDER else plat
            lines = []
            for post in posts[:6]:
                total += 1
                text = str(post.get("text") or "").strip().replace("\n", " ")
                url = str(post.get("url") or "").strip()
                lines.append(f"{total}. «{text[:200]}» — الرابط: {url}")
            if lines:
                sections.append(f"[{name}]\n" + "\n".join(lines))
        if sections:
            real_posts_block = (
                "منشورات حقيقية منشورة فعلًا على حسابات صاحب المشروع "
                "(قرأناها من روابط صفحاته، ولكلٍّ رابطها):\n"
                + "\n\n".join(sections)
                + "\n\nقاعدة: ابنِ على هذه المنشورات — علّق عليها، وأضف تطوّرات جديدة، "
                "ولا تنسب إلى صاحب الحساب كلامًا لم يقله، ولا تُخترع أرقامًا. "
                "إذا استشهدت بمنشور فاذكر رابطه كما هو، ومن أي منصّة هو.\n\n"
            )

    # أصوات من حول صاحب المشروع: من يذكره ويتحدث عن موضوعه على المنصّات.
    # تدخل الجولات كآراء متعدّدة (مؤيد/ناقد/متشكّك) لا كصوت واحد.
    if platform_mentions:
        sections = []
        total = 0
        for plat, items in platform_mentions.items():
            name = platform_registry.label(plat) if plat in platform_registry.ORDER else plat
            lines = []
            for item in items[:5]:
                total += 1
                text = str(item.get("text") or "").strip().replace("\n", " ")
                url = str(item.get("url") or "").strip()
                lines.append(f"{total}. «{text[:200]}» — الرابط: {url}")
            if lines:
                sections.append(f"[{name}]\n" + "\n".join(lines))
        if sections:
            real_posts_block += (
                "أصوات من حول صاحب المشروع — منشورات وتعليقات نشرها آخرون عنه أو "
                "عن موضوعه، ولكلٍّ رابطها:\n"
                + "\n\n".join(sections)
                + "\n\nقاعدة: هذه آراء أصحابها لا كلام صاحب المشروع. اجعل الوكلاء "
                "يعبّرون عن هذا التنوّع (مؤيد وناقد ومتشكّك ومن لا يعرف المشروع)، "
                "وانسب كل رأي إلى قائله حسب رابطه، ولا تخلط صوت الناقد بصوت المؤيد.\n\n"
            )

    platform_header = f"المنصّات المتاحة في هذه المحاكاة:\n{platform_registry.prompt_block(platforms)}\n\n"

    # وقائع بحث الويب عن الموضوع: تجعل الأفعال تتكلم عن الواقع اليوم لا عن العموميات
    try:
        from . import web_research

        bundle = web_research.load(sim_dir)
        research_block = web_research.prompt_block(bundle, max_facts=15)
        if research_block:
            platform_header += f"{research_block}\n\n"
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"تعذر إدراج وقائع البحث في المحاكاة: {exc}")
    if inputs_block:
        platform_header += f"{inputs_block}\n\n"
    # Context comes from the study, not a fixed national dialect template.
    platform_header += "حلّل سياق الدراسة فقط؛ لا تخترع بلداً أو لهجة أو فئات غير محددة.\n"

    llm = LLMClient()

    # النصّ الأساسي المشترك: من نحن، الموضوع، الوكلاء، المنصّات، قواعد السلوك.
    prompt = (
        "أنت محرك محاكاة اجتماعية متعدد الوكلاء في منصة «استشراف المستقبل».\n"
        f"موضوع الاستشراف: {requirement}\n"
        f"السياق السردي: {narrative}\n"
        f"المنشورات الافتتاحية: {json.dumps(initial_posts, ensure_ascii=False)}\n"
        f"{real_posts_block}"
        f"قائمة الوكلاء المتاحين: {json.dumps(agent_summary, ensure_ascii=False)}\n\n"
        f"{platform_header}"
        "قواعد المنصّات (مهمة):\n"
        f"- الحقل platform يأخذ قيمة واحدة فقط من: {', '.join(platforms)}. لا تخترع منصّة أخرى.\n"
        "- في كل جولة استخدم ثلاث منصّات مختلفة على الأقل، ولا تحشر كل الأفعال في منصّة واحدة ولا تهمل ريديت.\n"
        "- احترم طبيعة المنصّة في شكل المحتوى: رسالة واتساب قصيرة داخل مجموعة، "
        "تيك توك وصف قصير لفيديو مع تعليقات، فيسبوك منشور/تعليق، تويتر تغريدة/رد، "
        "ريديت منشور داخل مجتمع متخصّص مع تعليق أطول ويذكر مصدره.\n"
        "- المحتوى العربي فقط (يجوز أسماء الأعلام والأرقام).\n"
    )

    # كمية الأفعال لكل جولة: كل وكيل تقريبًا يتفاعل مرة في الجولة، بسقف
    # معقول يحافظ على جودة النصّ العربي داخل حدّ الرموز.
    # رفع سقف التفاعل: الطلب من صاحب المشروع «أقصى تفاعل ممكن»، فصار الهدف
    # ضعفَي عدد الوكلاء (بحدّ ١٢–٢٠) بدل ٨–١٦.
    per_round_target = max(12, min(20, (len(agent_summary) or 10) * 2))
    per_round_min = max(8, per_round_target // 2 + 3)

    json_spec = (
        '{"rounds": [{"round": 1, "actions": [{"agent_id": 0, "platform": "'
        + platforms[0]
        + '", "action_type": "CREATE_POST", "content": "...", "likes": 18, "shares": 5}]}]}'
    )

    # توزيع الأفعال على المنصّات في كل جولة بحسب أوزان السجل. كان التوزيع
    # يُحقن فقط عند إدخال المستخدم أرقامًا، فكانت ريديت تخرج بنصيب هزيل (١٣٪).
    try:
        from . import platform_inputs as _pi

        _w = _pi.weights({}, platforms)
        _sum = sum(_w.values()) or 1.0
        round_mix = {
            p: max(1, int(round(per_round_target * (_w.get(p, 0) / _sum))))
            for p in platforms
        }
        mix_line = '، '.join(
            f"{platform_registry.label(p)} {round_mix[p]}" for p in platforms
        )
    except Exception:  # noqa: BLE001
        round_mix = {}
        mix_line = ""

    def _batch_prompt(start_round: int, count: int, digest: str) -> str:
        span = (
            f"الدفعة الحالية: الجولة {start_round} فقط."
            if count == 1
            else f"الدفعة الحالية: الجولات من {start_round} إلى {start_round + count - 1}."
        )
        return (
            f"{prompt}\n\n{span}\n"
            + (f"{digest}\n\n" if digest else "")
            + (
                f"وزّع أفعال كل جولة على المنصّات بهذا التقريب: {mix_line} "
                "(ريديت منصّة كاملة لها نصيبها، لا ذكر عابر).\n"
                if mix_line else ""
            )
            + f"في كل جولة أدرج {per_round_min} إلى {per_round_target} تفاعلًا مختلفًا بين الوكلاء "
            "(CREATE_POST منشور جديد، CREATE_COMMENT تعليق على منشور سبق في نفس المنصّة).\n"
            "أعطِ لكل تفاعل أرقام تفاعل واقعية (likes و shares) تناسب المنصّة والموضوع.\n"
            "استند إلى وقائع البحث أعلاه ووسّعها: اذكر تفاصيل محددة من مصادر مختلفة "
        "(رقم، تاريخ، تصريح، تقرير)، وقارن بينها، ولا تكتفِ بما ورد في طلب المستخدم.\n"
        "نوّع الوكلاء: لا تجعل الوكيل نفسه يتكلم أكثر من مرتين في الجولة، وأشرك على الأقل "
            "خمسة وكلاء مختلفين في كل جولة.\n"
            "قاعدة التطور (إلزامية): كل جولة تُدخل شيئًا لم يرد قبلها — حدث جديد، رقم جديد، "
            "تصريح، اعتراض، أو نتيجة. يُمنع تكرار فكرة أو رقم أو جملة سبق ذكرها في الجولات "
            "السابقة، ويُمنع إعادة صياغة منشور سابق بكلمات أخرى. لا تعِد أي رقم استخدمته.\n"
            f"أعد JSON فقط بهذا الهيكل: {json_spec}"
        )

    rounds_data: List[Dict[str, Any]] = []
    next_round = 1
    consecutive_failures = 0
    # حجم الدفعة: عند سقف ١٤ فعلًا أو أكثر لكل جولة، نجعلها جولة واحدة لكل
    # طلب حتى لا يُبتر JSON (حدث فعليًا: «truncated at the token limit»).
    batch_size = 1 if per_round_target >= 14 else 2
    started_at = time.monotonic()
    # سقف زمني: لو نُفِّذت المحاكاة داخل طلب Vercel (بدون عامل) فلا نتجاوز
    # المهلة ونُبقي ما تولّد بدل أن يُقتل الطلب ويضيع كل شيء.
    time_budget = 230.0
    while next_round <= rounds:
        if time.monotonic() - started_at > time_budget:
            logger.warning("انتهت ميزانية الوقت بعد %s جولة؛ يُحتفظ بالمولَّد", next_round - 1)
            break
        chunk = min(batch_size, rounds - next_round + 1)
        part: Any = None
        try:
            resp = llm.chat_json(
                messages=[
                    {
                        "role": "system",
                        "content": "أجب بـ JSON صالح فقط يمثّل وقائع المحاكاة متعددة الوكلاء." + "\n" + EVIDENCE_POLICY,
                    },
                    {"role": "user", "content": _batch_prompt(next_round, chunk, _context_digest(rounds_data))},
                ],
                temperature=0.75,
            )
            if isinstance(resp, dict):
                part = resp.get("rounds")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"تعذر توليد الجولات {next_round}-{next_round + chunk - 1}: {exc}")

        valid = _clean_rounds(part)
        if not valid and chunk > 1:
            # جرّب جولة واحدة فقط (طلب أخفّ) قبل الاستسلام
            try:
                resp = llm.chat_json(
                    messages=[
                        {"role": "system", "content": "أجب بـ JSON صالح فقط." + "\n" + EVIDENCE_POLICY},
                        {"role": "user", "content": _batch_prompt(next_round, 1, _context_digest(rounds_data))},
                    ],
                    temperature=0.75,
                    max_tokens=2048,
                )
                valid = _clean_rounds(resp.get("rounds") if isinstance(resp, dict) else None)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"تعذر توليد الجولة {next_round} منفردة: {exc}")

        if not valid:
            # كان أول إخفاق واحد يوقف المحاكاة كلها (خرجت ٦ جولات بدل ١٢).
            # الآن نتجاوز الجولة ونكمل، ولا نتوقف إلا بعد ٣ إخفاقات متتالية.
            consecutive_failures += 1
            logger.warning(
                "لم يصل فعل صالح للجولة %s — نتجاوزها ونكمل (إخفاقات متتالية: %s)",
                next_round, consecutive_failures,
            )
            if consecutive_failures >= 3:
                logger.warning("٣ إخفاقات متتالية — يُحتفظ بما تولّد (%s جولة)", len(rounds_data))
                break
            next_round += chunk
            continue
        consecutive_failures = 0
        for offset, item in enumerate(valid):
            item["round"] = next_round + offset
            for act in item["actions"]:
                agent_id = int(act.get("agent_id", 0) or 0)
                if 0 <= agent_id < len(agent_summary):
                    act.setdefault("agent_name", agent_summary[agent_id]["name"])
        rounds_data.extend(valid)
        try:
            _dup = _drop_repeats(rounds_data)
            if _dup:
                logger.info("حُذف %s فعلًا يعيد فكرة سابقة", _dup)
        except Exception as exc:  # noqa: BLE001
            logger.warning("تعذر تنقية الأفعال المتكررة: %s", exc)
        next_round += len(valid)

    # طبقة التفاعل العميق: تعليقات على المنشورات الأكثر جذبًا، فالتفاعل ليس
    # منشورات متفرقة فقط بل محادثات حقيقية تحت المنشور.
    try:
        posts_index = _posts_by_platform(rounds_data)
        if posts_index and rounds_data:
            listing = []
            for plat, plist in posts_index.items():
                for post in plist[:8]:
                    listing.append(
                        f"- المنصّة {plat} · منشور رقم {post['post_id']} لـ{post['agent_name']}: {post['content']}"
                    )
            if listing:
                resp = llm.chat_json(
                    messages=[
                        {
                            "role": "system",
                            "content": "أجب بـ JSON صالح فقط يمثّل تعليقات واقعية على منشورات." + "\n" + EVIDENCE_POLICY,
                        },
                        {
                            "role": "user",
                            "content": (
                                f"{prompt}\n\nالمنشورات الجاهزة للتعليق:\n" + "\n".join(listing[:24])
                                + f"\n\nاكتب من 14 إلى 20 تعليقًا قصيرًا مختلفًا على هذه المنشورات، "
                                "بأصوات وكلاء مختلفين، وبلهجة منصّتهم.\n"
                                'أعد JSON فقط: {"comments": [{"platform": "' + platforms[0]
                                + '", "post_id": 1, "agent_id": 0, "content": "...", "likes": 6}]}'
                            ),
                        },
                    ],
                    temperature=0.8,
                )
                comments = resp.get("comments") if isinstance(resp, dict) else None
                if isinstance(comments, list):
                    last_round = rounds_data[-1]
                    for c in comments[:20]:
                        if not isinstance(c, dict):
                            continue
                        text = str(c.get("content") or "").strip()
                        plat = str(c.get("platform") or "").strip().lower()
                        if not text or plat not in platforms:
                            continue
                        agent_id = int(c.get("agent_id", 0) or 0)
                        if not (0 <= agent_id < len(agent_summary)):
                            continue
                        last_round["actions"].append(
                            {
                                "agent_id": agent_id,
                                "platform": plat,
                                "action_type": "CREATE_COMMENT",
                                "post_id": int(c.get("post_id") or 0) or None,
                                "content": text,
                                "likes": int(c.get("likes") or 5),
                                "shares": 0,
                            }
                        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"تعذر توليد طبقة التعليقات: {exc}")

    # احتياط: نداء واحد يغطّي كل الجولات (السلوك القديم) قبل السقوط لمنشور واحد
    if not rounds_data:
        try:
            resp = llm.chat_json(
                messages=[
                    {"role": "system", "content": "أجب بـ JSON صالح فقط يمثّل وقائع المحاكاة." + "\n" + EVIDENCE_POLICY},
                    {
                        "role": "user",
                        "content": (
                            f"{prompt}\n\nقم بمحاكاة {rounds} جولات. في كل جولة أدرج "
                            f"{per_round_min} إلى {per_round_target} تفاعلًا.\n"
                            f"أعد JSON فقط: {json_spec}"
                        ),
                    },
                ],
                temperature=0.75,
            )
            fallback_rounds = _clean_rounds(resp.get("rounds") if isinstance(resp, dict) else None)
            if fallback_rounds:
                for idx, item in enumerate(fallback_rounds, start=1):
                    item["round"] = idx
                rounds_data = fallback_rounds
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"تعذر الاحتياط الكامل للمحاكاة: {exc}")

    # احتياط أخير: لم يولّد النموذج شيئًا صالحًا → منشور واحد يمنع فشل المحاكاة
    if not rounds_data:
        rounds_data = [
            {
                "round": 1,
                "actions": [
                    {
                        "agent_id": int(agent_summary[0]["agent_id"]) if agent_summary else 0,
                        "platform": platforms[0],
                        "action_type": "CREATE_POST",
                        "content": requirement or "بدء النقاش التحليلي حول السيناريو المطروح.",
                        "likes": 15,
                        "shares": 4,
                    }
                ],
            }
        ]

    rounds_data = _clamp_platforms(rounds_data, platforms)

    # حماية من «تدهور النتيجة»: إذا نفدت حصة النموذج في تشغيلٍ جديد، لا نكتب
    # نسخة أفقر فوق نسخة ناجحة سابقة. (حدث فعليًا: محاكاة بـ٩١ تفاعلًا صارت
    # تفاعلًا واحدًا بعد إعادة تشغيل فاشلة، فقرأ مولّد التقرير النسخة الفقيرة.)
    try:
        from ..models import storage as _storage

        previous_total = 0
        for plat in platforms:
            for source in (
                f"simulations/{os.path.basename(sim_dir)}/{plat}/actions.jsonl",
                os.path.join(sim_dir, plat, "actions.jsonl"),
            ):
                raw = ""
                try:
                    if os.path.isabs(source) and os.path.exists(source):
                        raw = open(source, encoding='utf-8').read()
                    elif not os.path.isabs(source):
                        raw = _storage.read_text_fresh(source) or ""
                except Exception:  # noqa: BLE001
                    raw = ""
                previous_total = max(
                    previous_total,
                    sum(1 for ln in raw.splitlines() if ln.strip() and '"agent_id"' in ln),
                )
        new_total = sum(len(r.get("actions") or []) for r in rounds_data)
        if previous_total and new_total < previous_total:
            logger.warning(
                "النسخة الجديدة أضعف (%s < %s تفاعلًا) — يُحتفظ بالنسخة السابقة",
                new_total, previous_total,
            )
            kept: Dict[str, int] = {}
            for plat in platforms:
                raw = ""
                local_path = os.path.join(sim_dir, plat, "actions.jsonl")
                try:
                    if os.path.exists(local_path):
                        raw = open(local_path, encoding='utf-8').read()
                except OSError:
                    raw = ""
                if not raw:
                    raw = _storage.read_text_fresh(
                        f"simulations/{os.path.basename(sim_dir)}/{plat}/actions.jsonl"
                    ) or ""
                kept[plat] = sum(1 for ln in raw.splitlines() if ln.strip() and '"agent_id"' in ln)
                try:
                    _storage.ensure_local(
                        f"simulations/{os.path.basename(sim_dir)}/{plat}/actions.jsonl"
                    )
                except Exception:  # noqa: BLE001
                    pass
            return {
                "rounds_completed": max(1, len(rounds_data)),
                "platforms": platforms,
                "platform_actions": kept,
                "twitter_actions": kept.get("twitter", 0),
                "reddit_actions": kept.get("reddit", 0),
                "total_actions": sum(kept.values()),
                "kept_previous": True,
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("تعذر مقارنة النسخ قبل الكتابة: %s", exc)

    counts = write_simulation_artifacts(sim_dir, profiles, rounds_data, platforms)

    # احفظ مخرجات المحاكاة في التخزين الدائم فورًا، فالقرص المؤقت يُفقد بعد
    # انتهاء الطلب على Vercel، وحينها لا يجد مولّد التقرير أي وقائع للمحاكاة.
    from .simulation_runner import persist_file

    for plat in platforms:
        for relative in (os.path.join(plat, "actions.jsonl"), f"{plat}_simulation.db"):
            try:
                persist_file(os.path.join(sim_dir, relative))
            except Exception as exc:  # pragma: no cover
                logger.warning(f"تعذر حفظ مخرجات المحاكاة: {relative} ({exc})")

    return {
        "rounds_completed": len(rounds_data),
        "platforms": platforms,
        "platform_actions": counts,
        "twitter_actions": counts.get("twitter", 0),
        "reddit_actions": counts.get("reddit", 0),
        "total_actions": sum(counts.values()),
            }
