import os
import sys
import json
import time
from typing import Any, Dict, List

import requests

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
SESSION_ID = os.getenv("SESSION_ID")
COACH_QUERIES = [
    "如果我们当时保枪，会不会更好？",
    "这名选手在 Bo3 中的表现是否异常？",
    "这场比赛是否属于高风险对局？",
]
DEBUG_MARKERS = [
    "states_lt_",
    "series_pool",
    "gate-insufficient",
    "debug",
    "trace_id",
]


def _post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{API_BASE}{path}"
    resp = requests.post(url, json=payload, timeout=30)
    try:
        resp.raise_for_status()
    except Exception as exc:  # pragma: no cover - simple runner
        raise SystemExit(f"HTTP {resp.status_code} for {url}: {resp.text}") from exc
    try:
        return resp.json()
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"Non-JSON response from {url}: {resp.text}") from exc


def _assert_no_debug(text: str) -> None:
    lowered = text.lower()
    for marker in DEBUG_MARKERS:
        if marker in lowered:
            raise AssertionError(f"assistant_message contains debug marker: {marker}")


def run_once(query: str, session_id: str | None, seq: int) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"coach_query": query}
    if session_id:
        payload["session_id"] = session_id
    result = _post("/api/coach/query", payload)
    assistant_message = result.get("assistant_message") or ""
    _assert_no_debug(assistant_message)

    analysis = result.get("session_analysis") or {}
    nodes = analysis.get("analysis_nodes") or []
    if not nodes:
        raise AssertionError(f"seq {seq}: session_analysis missing nodes")
    ra = analysis.get("recently_added_node_ids") or []
    if not ra:
        raise AssertionError(f"seq {seq}: recently_added_node_ids empty")
    return {"nodes": nodes, "assistant_message": assistant_message}


def _used_count(nodes: List[Dict[str, Any]]) -> int:
    total = 0
    for n in nodes:
        used = n.get("used_in_queries") or []
        total += len(used)
    return total


def main() -> None:
    print(f"Running 3-round acceptance against {API_BASE} (session_id={SESSION_ID or 'none'})")
    prev_nodes_len = 0
    prev_used_total = 0

    for idx, query in enumerate(COACH_QUERIES, start=1):
        print(f"Round {idx}: {query}")
        bundle = run_once(query, SESSION_ID, idx)
        nodes = bundle["nodes"]
        nodes_len = len(nodes)
        used_total = _used_count(nodes)

        if idx > 1:
            if not (nodes_len > prev_nodes_len or used_total > prev_used_total):
                raise AssertionError(
                    f"seq {idx}: neither analysis_nodes nor used_in_queries increased (nodes {prev_nodes_len}->{nodes_len}, used {prev_used_total}->{used_total})"
                )
        prev_nodes_len = nodes_len
        prev_used_total = used_total
        time.sleep(1.0)

    print("✅ Acceptance passed: nodes/used_in_queries grow, recently_added non-empty, no debug markers.")


if __name__ == "__main__":
    main()
