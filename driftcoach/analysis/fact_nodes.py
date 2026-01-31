from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from driftcoach.session.analysis_store import SessionAnalysisStore


FACT_TO_NODE = {
    "FORCE_BUY_ROUND": "ECONOMIC_DECISION",
    "ECONOMY_COLLAPSE": "RISK_PROFILE",
    "ROUND_SWING": "TURNING_POINT",
    "HIGH_RISK_SEQUENCE": "RISK_PROFILE",
    "OBJECTIVE_LOSS_CHAIN": "TACTICAL_MISTAKE",
}


def _node_id(payload: List[Any]) -> str:
    raw = "|".join(str(x) for x in payload)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def nodes_from_facts(facts: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    now = SessionAnalysisStore._now()
    nodes: List[Dict[str, Any]] = []
    for fact in facts:
        fact_type = fact.get("fact_type")
        node_type = FACT_TO_NODE.get(fact_type)
        if not node_type:
            continue
        rr = fact.get("round_range") or [None, None]
        meta = {
            "fact_type": fact_type,
            "series_id": fact.get("series_id"),
            "round_range": rr,
            "derived_from": fact.get("derived_from"),
            "evidence_events": fact.get("evidence_events", [])[:20],
            "note": fact.get("note"),
        }
        conf = 0.55
        if fact.get("confidence") == "high":
            conf = 0.7
        elif fact.get("confidence") == "medium":
            conf = 0.6
        nodes.append(
            {
                "node_id": _node_id([node_type, fact.get("series_id"), tuple(rr)]),
                "type": node_type,
                "source": "file_download",
                "axes_covered": ["round", "series"],
                "confidence": conf,
                "created_from_query": query,
                "created_at": now,
                "last_updated_at": now,
                "target": fact.get("series_id"),
                "window": f"rounds_{rr[0]}_{rr[1]}",
                "used_in_queries": [query],
                "metadata": meta,
            }
        )
    if not facts:
        nodes.append(
            {
                "node_id": _node_id(["CONTEXT_ONLY", query, "file_download"]),
                "type": "CONTEXT_ONLY",
                "source": "file_download",
                "axes_covered": ["context"],
                "confidence": 0.35,
                "created_from_query": query,
                "created_at": now,
                "last_updated_at": now,
                "target": None,
                "window": None,
                "used_in_queries": [query],
                "metadata": {"note": "无可提炼事件事实"},
            }
        )
    return nodes
