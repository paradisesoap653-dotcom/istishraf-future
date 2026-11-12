"""
محرك بناء وقراءة الرسم المعرفي المحلي عبر النموذج اللغوي (LLM Local Knowledge Graph Engine)
يتيح تشغيل المنصة مجاناً بالكامل باستخدام مفتاح الذكاء الاصطناعي فقط (مثل Groq)
دون إلزام المستخدم باشتراك أو مفتاح Zep Cloud، مع بقاء دعم Zep مفعّلاً تلقائياً عند توفر المفتاح.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from ..config import Config
from ..models import storage
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger("mirofish.local_graph")


def local_graph_path(graph_id: str) -> str:
    graphs_dir = os.path.join(Config.UPLOAD_FOLDER, "graphs")
    storage.makedirs(graphs_dir)
    return os.path.join(graphs_dir, f"{graph_id}.json")


def load_local_graph(graph_id: str) -> Optional[Dict[str, Any]]:
    """يقرأ الرسم من القرص المحلي أو من التخزين الدائم إن لم يكن محليًا."""
    if not graph_id:
        return None
    path = local_graph_path(graph_id)
    if not storage.exists(path):
        return None
    try:
        return storage.read_json(path)
    except Exception as err:
        logger.warning(f"Failed reading local graph {graph_id}: {err}")
        return None


def build_local_graph_via_llm(
    text: str,
    ontology: Dict[str, Any],
    graph_name: str = "Istishraf Graph",
) -> Dict[str, Any]:
    """يبني رسماً معرفياً متكاملاً (كيانات وعلاقات) عبر LLM ويحفظه محلياً."""
    graph_id = f"graph_local_{uuid.uuid4().hex[:12]}"
    entity_types_raw = (ontology or {}).get("entity_types") or []
    type_names: List[str] = []
    for et in entity_types_raw:
        if isinstance(et, dict) and et.get("name"):
            type_names.append(str(et["name"]))
        elif isinstance(et, str):
            type_names.append(et)

    if not type_names:
        type_names = ["شخصية_فاعلة", "مؤسسة", "خبير", "فئة_اجتماعية"]

    excerpt = (text or "")[:12000]
    llm = LLMClient()

    prompt = (
        "أنت محرك بناء رسوم معرفية في منصة «استشراف المستقبل».\n"
        f"عنوان الرسم: {graph_name}\n"
        f"أنواع الكيانات المعتمدة: {json.dumps(type_names, ensure_ascii=False)}\n"
        f"النص المصدري:\n{excerpt}\n\n"
        "استخرج من النص (ومن الأطراف الفاعلة المرتبطة منطقياً بالسيناريو) ما بين 7 و 12 كياناً رئيسياً "
        "تغطي أنواع الكيانات المعتمدة، وما بين 8 و 16 علاقة سببية أو تفاعلية تربط بينها.\n"
        "أعد JSON صالحاً فقط بهذا الهيكل الدقيق:\n"
        "{\n"
        '  "nodes": [\n'
        '    {"id": "n1", "name": "اسم الكيان", "entity_type": "نوع من القائمة المعتمدة", "summary": "وصف غني لدوره وموقفه ودوافعه"}\n'
        "  ],\n"
        '  "edges": [\n'
        '    {"source": "n1", "target": "n2", "relation": "نوع_العلاقة", "fact": "جملة دقيقة تشرح العلاقة أو التأثير بين الطرفين"}\n'
        "  ]\n"
        "}"
    )

    resp = llm.chat_json(
        messages=[
            {"role": "system", "content": "أجب بـ JSON صالح فقط يمثّل الكيانات والعلاقات المستخرجة."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )

    raw_nodes = resp.get("nodes") if isinstance(resp, dict) else []
    raw_edges = resp.get("edges") if isinstance(resp, dict) else []
    now_iso = datetime.now().isoformat()

    nodes: List[Dict[str, Any]] = []
    id_map: Dict[str, Dict[str, Any]] = {}
    for idx, rn in enumerate(raw_nodes or [], start=1):
        nid = str(rn.get("id") or f"n{idx}")
        etype = str(rn.get("entity_type") or type_names[idx % len(type_names)])
        name = str(rn.get("name") or f"فاعل {idx}")
        summary = str(rn.get("summary") or "")
        node_obj = {
            "uuid": nid,
            "name": name,
            "labels": ["Entity", etype],
            "summary": summary,
            "attributes": {"role": etype},
            "created_at": now_iso,
        }
        nodes.append(node_obj)
        id_map[nid] = node_obj

    edges: List[Dict[str, Any]] = []
    for idx, re_item in enumerate(raw_edges or [], start=1):
        src = str(re_item.get("source") or "")
        tgt = str(re_item.get("target") or "")
        if src not in id_map or tgt not in id_map:
            continue
        edges.append(
            {
                "uuid": f"e{idx}",
                "name": str(re_item.get("relation") or "يتفاعل_مع"),
                "fact": str(re_item.get("fact") or f"{id_map[src]['name']} يرتبط بـ {id_map[tgt]['name']}"),
                "source_node_uuid": src,
                "target_node_uuid": tgt,
                "source_node_name": id_map[src]["name"],
                "target_node_name": id_map[tgt]["name"],
                "attributes": {},
                "created_at": now_iso,
            }
        )

    graph_data = {
        "graph_id": graph_id,
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }

    storage.write_json(local_graph_path(graph_id), graph_data)

    return graph_data
