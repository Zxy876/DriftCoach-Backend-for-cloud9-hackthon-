import json
import os
import sys
import datetime as dt
from typing import Dict, Any, List, Optional, Tuple

from driftcoach.adapters.grid.client import GridClient
from driftcoach.adapters.grid import queries as q

CALL_LIMIT = 50
SERIES_LIMIT = 20
TIME_WINDOWS = ["LAST_6_MONTHS", "LAST_12_MONTHS"]
MAP_COUNT_THRESHOLD = 20
SERIES_COUNT_THRESHOLD = 5


def main():
    print("[scan] start", file=sys.stderr)
    api_key = os.getenv("GRID_API_KEY")
    if not api_key:
        print("GRID_API_KEY missing", file=sys.stderr)
        sys.exit(1)

    client = GridClient(api_key=api_key)
    call_count = 0

    def safe_run(query: str, variables: Dict[str, Any]):
        nonlocal call_count
        if call_count >= CALL_LIMIT:
            raise RuntimeError(f"Call limit {CALL_LIMIT} reached")
        call_count += 1
        return client.run_query(query, variables)

    hit: Optional[Dict[str, Any]] = None
    tried_players: set[str] = set()

    now = dt.datetime.utcnow()
    gte = (now - dt.timedelta(days=180)).isoformat() + "Z"
    lte = (now + dt.timedelta(days=180)).isoformat() + "Z"

    for tw in TIME_WINDOWS:
        # Step1: enumerate series
        series_payload = safe_run(q.Q_ALL_SERIES_WINDOW, {"gte": gte, "lte": lte, "first": SERIES_LIMIT})
        series_edges = (series_payload.get("data", {}) or {}).get("allSeries", {}).get("edges") or []
        series_nodes = [edge.get("node") for edge in series_edges if isinstance(edge, dict)]
        if not series_nodes:
            print(f"[scan] no series in window {tw}", file=sys.stderr)
            continue
        print(f"[scan] window={tw} series={len(series_nodes)}", file=sys.stderr)

        for series in series_nodes:
            teams = (series or {}).get("teams") or []
            team_ids = []
            for t in teams:
                base = t.get("baseInfo") or {}
                if base.get("id"):
                    team_ids.append(base["id"])

            # Step2: roster to player ids
            player_ids: List[str] = []
            for team_id in team_ids:
                roster_payload = safe_run(q.Q_TEAM_ROSTER, {"teamId": team_id})
                edges = (roster_payload.get("data", {}) or {}).get("players", {}).get("edges") or []
                for edge in edges:
                    node = edge.get("node") if isinstance(edge, dict) else None
                    if node and node.get("id"):
                        player_ids.append(node["id"])
            print(f"[scan] series={series.get('id')} teams={len(team_ids)} players={len(player_ids)}", file=sys.stderr)

            # Step3: stats per player (dedup)
            for pid in player_ids:
                if pid in tried_players:
                    continue
                tried_players.add(pid)
                try:
                    stats_payload = safe_run(q.Q_PLAYER_STATISTICS, {"playerId": pid, "timeWindow": tw, "tournamentIds": None})
                except Exception as exc:
                    result = {
                        "error": str(exc),
                        "player_id": pid,
                        "series_id": series.get("id"),
                        "call_count": call_count,
                        "time_window": tw,
                        "tried_players": len(tried_players),
                    }
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    print("[scan] error", file=sys.stderr)
                    return
                stats = (stats_payload.get("data", {}) or {}).get("playerStatistics") or {}
                series_count = (stats.get("series") or {}).get("count") or 0
                map_count = (stats.get("game") or {}).get("count") or 0
                agg_ids = stats.get("aggregationSeriesIds") or []

                if (map_count >= MAP_COUNT_THRESHOLD) or (series_count >= SERIES_COUNT_THRESHOLD):
                    hit = {
                        "player_id": pid,
                        "series_id": series.get("id"),
                        "time_window": tw,
                        "series_count": series_count,
                        "map_count": map_count,
                        "aggregation_series_ids": agg_ids,
                        "call_count": call_count,
                    }
                    break
            if hit:
                break
        if hit:
            break

    result = {
        "hit": hit,
        "tried_players": len(tried_players),
        "call_count": call_count,
        "time_windows_tried": TIME_WINDOWS,
    }
    if not hit:
        result["reason"] = "no playerStatistics met threshold within limits"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("[scan] done", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)
