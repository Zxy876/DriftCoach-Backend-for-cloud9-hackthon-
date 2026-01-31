import json
from pathlib import Path

RESULT_PATH = Path("/tmp/hackathon_nl_results.json")

QUERIES_ORDER = [
    ("Q1", "这场比赛是否属于高风险对局？"),
    ("Q2", "如果当时选择保枪而不是强起，结果可能会不同吗？"),
    ("Q3", "这场比赛里是否出现过关键的局势反转？"),
    ("Q4", "这种局势反转在整场比赛中是偶发还是反复出现？"),
]


def load_results():
    if not RESULT_PATH.exists():
        raise SystemExit(f"Results file not found: {RESULT_PATH}")
    return json.loads(RESULT_PATH.read_text())


def build_summary(data: dict) -> dict:
    out = {"series_id": data.get("series_id"), "session_id": data.get("session_id"), "queries": []}
    for label, q in QUERIES_ORDER:
        resp = data.get("responses", {}).get(label, {})
        ctx = resp.get("context") or {}
        mp = ctx.get("hackathon_mining_plan") or {}
        facts = [f.get("fact_type") for f in (ctx.get("hackathon_evidence") or []) if f.get("fact_type")]
        msgs = resp.get("messages") or []
        answer = next((m.get("content", "") for m in msgs if m.get("role") == "assistant"), "")
        nodes_added = len((resp.get("session_analysis") or {}).get("recently_added_node_ids") or [])
        out["queries"].append(
            {
                "label": label,
                "query": q,
                "mining_plan": {
                    "intent": mp.get("intent"),
                    "required_facts": mp.get("required_facts"),
                    "scope": mp.get("scope"),
                    "constraints": mp.get("constraints"),
                },
                "facts_used": sorted(set(facts)),
                "analysis_nodes_added": nodes_added,
                "assistant_answer": answer,
            }
        )
    return out


def main():
    data = load_results()
    summary = build_summary(data)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
