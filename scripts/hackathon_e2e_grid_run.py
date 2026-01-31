import json
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

from driftcoach.api import app


def main() -> None:
    grid_series_id = os.getenv("GRID_SERIES_ID")
    grid_player_id = os.getenv("GRID_PLAYER_ID")
    if not grid_series_id:
        raise SystemExit("GRID_SERIES_ID missing")

    client = TestClient(app)
    resp = client.post(
        "/api/coach/init",
        json={"grid_player_id": grid_player_id or "placeholder", "grid_series_id": grid_series_id},
    )
    resp.raise_for_status()
    session_id = resp.json()["session_id"]
    print("session_id", session_id)

    queries = [
        "如果我们当时保枪，会不会更好？",
        "这名选手在 Bo3 中的表现是否异常？",
        "这场比赛是否属于高风险对局？",
    ]

    results = []
    prev_nodes = 0
    prev_used_total = 0
    for idx, q in enumerate(queries, 1):
        r = client.post("/api/coach/query", json={"coach_query": q, "session_id": session_id})
        r.raise_for_status()
        payload = r.json()
        analysis = payload.get("session_analysis") or {}
        nodes = analysis.get("analysis_nodes") or []
        ra = analysis.get("recently_added_node_ids") or []
        used_total = sum(len(n.get("used_in_queries") or []) for n in nodes)
        results.append({"round": idx, "query": q, "response": payload})
        print(f"round {idx}: nodes={len(nodes)} ra={len(ra)} used_total={used_total}")
        if idx > 1 and not (len(nodes) > prev_nodes or used_total > prev_used_total):
            print(f"warning: no growth at round {idx}")
        prev_nodes = len(nodes)
        prev_used_total = used_total
        time.sleep(0.25)

    out_path = Path("/tmp/hackathon_e2e_grid.json")
    out_path.write_text(
        json.dumps({"series_id": grid_series_id, "player_id": grid_player_id, "results": results}, ensure_ascii=False, indent=2)
    )
    print(f"saved to {out_path}")


if __name__ == "__main__":
    main()