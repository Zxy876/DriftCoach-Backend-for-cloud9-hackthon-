import time

from fastapi.testclient import TestClient

from driftcoach.api import app


def main() -> None:
    client = TestClient(app)

    resp = client.post(
        "/api/coach/init", json={"grid_player_id": "91", "grid_series_id": "2819676"}
    )
    resp.raise_for_status()
    session_id = resp.json()["session_id"]
    print("session_id", session_id)

    queries = [
        "如果我们当时保枪，会不会更好？",
        "这名选手在 Bo3 中的表现是否异常？",
        "这场比赛是否属于高风险对局？",
    ]

    prev_len = 0
    prev_used = 0
    markers = ["states_lt_", "series_pool", "gate-insufficient", "debug", "trace_id"]

    for idx, q in enumerate(queries, 1):
        r = client.post("/api/coach/query", json={"coach_query": q, "session_id": session_id})
        r.raise_for_status()
        payload = r.json()

        msg = (payload.get("assistant_message") or "").lower()
        if any(m in msg for m in markers):
            raise SystemExit(f"debug marker found in round {idx}")

        analysis = payload.get("session_analysis") or {}
        nodes = analysis.get("analysis_nodes") or []
        ra = analysis.get("recently_added_node_ids") or []
        used_total = sum(len(n.get("used_in_queries") or []) for n in nodes)

        print(f"round {idx}: nodes={len(nodes)} used_total={used_total} ra={len(ra)}")

        if not ra:
            raise SystemExit(f"round {idx}: recently_added empty")
        if idx > 1 and not (len(nodes) > prev_len or used_total > prev_used):
            raise SystemExit(f"round {idx}: no growth")

        prev_len = len(nodes)
        prev_used = used_total
        time.sleep(0.2)

    print("✅ E2E acceptance passed")


if __name__ == "__main__":
    main()