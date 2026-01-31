"""
Patch Executor v4 (Grid queries frozen):
- Directly executes pre-validated GraphQL templates (no planner).
- Each PatchType maps to a fixed query + inputs.
- Retries handled in GridClient (ENHANCE_YOUR_CALM aware).
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple, Optional, Iterable

from driftcoach.adapters.grid.client import GridClient
from driftcoach.adapters.grid import queries as q
from driftcoach.core.state import State

logger = logging.getLogger(__name__)

SUPPORTED_PATCHES = {
    "ENUMERATE_SERIES",
    "ENUMERATE_PLAYERS",
    "SLICE_SERIES_WINDOW",
    "SLICE_BY_OPPONENT",
    "SLICE_BY_TIME_BUCKET",
    "AGGREGATE_SERIES_DISTRIBUTION",
    "STATS_QUERY_EXPERIMENT",
}


def _trace_id() -> str:
    return uuid.uuid4().hex[:12]


def _ts(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _time_bucket(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m")
    except Exception:
        return "UNKNOWN"


def _hash_state_id(trace_id: str, evidence_type: str, series_id: str | None, subject_id: str | None, window_key: str) -> str:
    raw = "|".join([trace_id, evidence_type, series_id or "unknown", subject_id or "", window_key])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _context_state(
    trace_id: str,
    evidence_type: str,
    series: Dict[str, Any],
    player_id: str,
    window_key: str,
    provenance: Dict[str, Any],
    idx: int,
    slice_axis: Optional[str] = None,
    slice_value: Optional[str] = None,
) -> State:
    series_id = str(series.get("id", "unknown"))
    teams = series.get("teams") or []
    team_names = []
    team_ids = []
    for t in teams:
        base = t.get("baseInfo") or {}
        if base.get("name"):
            team_names.append(str(base.get("name")))
        if base.get("id"):
            team_ids.append(str(base.get("id")))
    state_id = _hash_state_id(trace_id, evidence_type, series_id, player_id, f"{window_key}|{slice_axis or ''}|{slice_value or ''}")
    extras = {
        "evidence_type": evidence_type,
        "slice_type": evidence_type,
        "series_id": series_id,
        "player_id": player_id,
        "tournament": (series.get("tournament") or {}).get("nameShortened") if isinstance(series.get("tournament"), dict) else None,
        "format": (series.get("format") or {}).get("name") if isinstance(series.get("format"), dict) else None,
        "start_time": series.get("startTimeScheduled"),
        "team_names": team_names,
        "team_ids": team_ids,
        "slice_axis": slice_axis,
        "slice_value": slice_value,
        "provenance": provenance,
        "trace_id": trace_id,
    }
    return State(
        state_id=state_id,
        series_id=series_id,
        game_index=idx,
        timestamp=_ts(series.get("startTimeScheduled")),
        map="context",
        score_diff=0,
        econ_diff=0,
        alive_diff=0,
        ult_diff=0,
        objective_context=None,
        phase="CONTEXT",
        extras=extras,
    )


def _aggregation_state(
    trace_id: str,
    level: str,
    player_id: str,
    subject_id: str,
    agg_payload: Optional[Dict[str, Any]],
    filter_used: Dict[str, Any],
    idx: int,
) -> State:
    aggregation_series_ids = []
    data = None
    mock_flag = False
    note = None
    if isinstance(agg_payload, dict):
        aggregation_series_ids = agg_payload.get("aggregationSeriesIds") or []
        data = agg_payload
        mock_flag = bool(agg_payload.get("mock"))
        note = agg_payload.get("note")

    window_key = str(filter_used)
    state_id = _hash_state_id(trace_id, "AGGREGATED_PERFORMANCE", subject_id, player_id, window_key)
    extras = {
        "evidence_type": "AGGREGATED_PERFORMANCE",
        "aggregation_level": level,
        "aggregation_series_ids": aggregation_series_ids,
        "aggregation_unavailable": not bool(data),
        "aggregation_raw": data or None,
        "filter_used": filter_used,
        "trace_id": trace_id,
        "mock": mock_flag,
        "note": note,
    }
    return State(
        state_id=state_id,
        series_id=str(subject_id),
        game_index=idx,
        timestamp=0.0,
        map="context",
        score_diff=0,
        econ_diff=0,
        alive_diff=0,
        ult_diff=0,
        objective_context=None,
        phase="CONTEXT",
        extras=extras,
    )


def _paginate(
    client: GridClient,
    query: str,
    variables: Dict[str, Any],
    edge_path: Iterable[str],
    max_pages: int = 2,
    max_items: int = 100,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    vars_local = dict(variables)
    page_count = 0
    while True:
        if page_count >= max_pages or len(items) >= max_items:
            break
        payload = client.run_query(query, vars_local)
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        cursor_node = data
        for key in edge_path:
            cursor_node = cursor_node.get(key, {}) if isinstance(cursor_node, dict) else {}
        edges = cursor_node.get("edges") if isinstance(cursor_node, dict) else []
        for edge in edges or []:
            node = edge.get("node") if isinstance(edge, dict) else None
            if node:
                items.append(node)
                if len(items) >= max_items:
                    break
        page = cursor_node.get("pageInfo") if isinstance(cursor_node, dict) else {}
        page_count += 1
        if not page or not page.get("hasNextPage"):
            break
        vars_local["after"] = page.get("endCursor")
    return items


def execute_patches(
    proposed: List[Dict[str, Any]],
    max_patches: int,
    data_source: str,
    grid_api_key: str | None,
    grid_player_id: str,
    grid_series_id: str,
    anchor_team_id: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[State]]:
    results: List[Dict[str, Any]] = []
    new_states: List[State] = []
    seen_state_ids: set[str] = set()

    if not proposed:
        return results, new_states

    page_caps = (1, 30) if data_source == "grid" else (3, 150)

    if data_source != "grid":
        class _MockGridClient:
            def run_query(self, query: str, variables: Dict[str, Any]):
                now = datetime.now(timezone.utc).isoformat()
                if query == q.Q_SERIES_BY_ID:
                    return {
                        "data": {
                            "series": {
                                "id": grid_series_id or "mock-series",
                                "startTimeScheduled": now,
                                "format": {"name": "BO3"},
                                "tournament": {"nameShortened": "MockCup"},
                                "teams": [
                                    {"baseInfo": {"id": "mock-team-a", "name": "MockTeamA"}},
                                    {"baseInfo": {"id": "mock-team-b", "name": "MockTeamB"}},
                                ],
                            }
                        }
                    }
                if query == q.Q_ALL_SERIES_WINDOW:
                    edges = []
                    for idx in range(2):
                        edges.append(
                            {
                                "node": {
                                    "id": f"mock-series-{idx}",
                                    "startTimeScheduled": now,
                                    "format": {"name": "BO3"},
                                    "tournament": {"nameShortened": "MockCup"},
                                    "teams": [
                                        {"baseInfo": {"id": "mock-team-a", "name": "MockTeamA"}},
                                        {"baseInfo": {"id": "mock-team-b", "name": "MockTeamB"}},
                                    ],
                                }
                            }
                        )
                    return {"data": {"allSeries": {"edges": edges, "pageInfo": {"hasNextPage": False}}}}
                if query == q.Q_TEAM_ROSTER:
                    return {"data": {"players": {"edges": []}}}
                if query == q.Q_PLAYER_STATISTICS:
                    return {"data": {"playerStatistics": {"aggregationSeriesIds": [], "mock": True}}}
                return {"data": {}}

        client = _MockGridClient()
    else:
        client = GridClient(api_key=grid_api_key) if grid_api_key else None
        if client is None:
            raise RuntimeError("GRID_API_KEY missing")

    # Cache anchor series for window calculations
    anchor_series_payload = client.run_query(q.Q_SERIES_BY_ID, {"id": grid_series_id})
    anchor_series = (anchor_series_payload.get("data", {}) or {}).get("series") or {}

    limited = proposed[:max_patches]

    for patch in limited:
        p_type = patch.get("patch_type")
        trace_id = _trace_id()
        start_ts = time.time()

        if p_type not in SUPPORTED_PATCHES:
            results.append({"patch": p_type, "status": "error", "reason": "unsupported_patch_type", "trace_id": trace_id})
            continue

        try:
            if p_type == "SLICE_SERIES_WINDOW":
                params = patch.get("params") or {}
                days_before = int(params.get("days_before", 180))
                days_after = int(params.get("days_after", 180))
                anchor_start = anchor_series.get("startTimeScheduled")
                if anchor_start:
                    start_dt = datetime.fromisoformat(anchor_start.replace("Z", "+00:00"))
                    gte = (start_dt - timedelta(days=days_before)).isoformat()
                    lte = (start_dt + timedelta(days=days_after)).isoformat()
                else:
                    now = datetime.now(timezone.utc)
                    gte = (now - timedelta(days=days_before)).isoformat()
                    lte = (now + timedelta(days=days_after)).isoformat()
                enum_params = {
                    "patch_type": "ENUMERATE_SERIES",
                    "params": {"gte": gte, "lte": lte, "first": 50},
                }
                patch_result, patch_states = _run_enumerate_series(client, trace_id, enum_params, grid_player_id, window_key=f"{gte}|{lte}")
                results.append(patch_result)
                for s in patch_states:
                    if s.state_id in seen_state_ids:
                        continue
                    seen_state_ids.add(s.state_id)
                    new_states.append(s)
                continue

            if p_type == "ENUMERATE_SERIES":
                patch_result, patch_states = _run_enumerate_series(client, trace_id, patch, grid_player_id, page_caps)
                added = _append_states(patch_states, new_states, seen_state_ids)
                if added == 0 and patch_states:
                    patch_result["status"] = "noop_duplicate"
                results.append(patch_result)
                continue

            if p_type == "ENUMERATE_PLAYERS":
                patch_result, patch_states = _run_enumerate_players(client, trace_id, patch, page_caps)
                added = _append_states(patch_states, new_states, seen_state_ids)
                if added == 0 and patch_states:
                    patch_result["status"] = "noop_duplicate"
                results.append(patch_result)
                continue

            if p_type == "SLICE_BY_OPPONENT":
                patch_result, patch_states = _run_slice_by_opponent(client, trace_id, patch, grid_player_id, page_caps)
                added = _append_states(patch_states, new_states, seen_state_ids)
                if added == 0 and patch_states:
                    patch_result["status"] = "noop_duplicate"
                results.append(patch_result)
                continue

            if p_type == "SLICE_BY_TIME_BUCKET":
                patch_result, patch_states = _run_slice_by_time_bucket(client, trace_id, patch, grid_player_id, page_caps)
                added = _append_states(patch_states, new_states, seen_state_ids)
                if added == 0 and patch_states:
                    patch_result["status"] = "noop_duplicate"
                results.append(patch_result)
                continue

            if p_type == "AGGREGATE_TEAM_STATISTICS":
                results.append({
                    "patch": p_type,
                    "status": "disabled",
                    "reason": "stats_via_patch_disabled",
                    "trace_id": trace_id,
                    "origin": "ai-patch",
                })
                continue

            if p_type == "AGGREGATE_PLAYER_STATISTICS":
                results.append({
                    "patch": p_type,
                    "status": "disabled",
                    "reason": "stats_via_patch_disabled",
                    "trace_id": trace_id,
                    "origin": "ai-patch",
                })
                continue

            if p_type == "AGGREGATE_SERIES_DISTRIBUTION":
                # Derive buckets from existing ENUMERATE_SERIES states
                buckets = {}
                for s in new_states:
                    fmt = (s.extras.get("format") or "OTHER").upper()
                    buckets[fmt] = buckets.get(fmt, 0) + 1
                state = _aggregation_state(trace_id, "series", grid_player_id, grid_series_id, {"buckets": buckets}, {"source": "enumerate_series"}, len(new_states))
                status = "noop_duplicate" if state.state_id in seen_state_ids else "ok"
                if status == "ok":
                    seen_state_ids.add(state.state_id)
                    new_states.append(state)
                results.append({"patch": p_type, "status": status, "reason": "aggregated locally", "trace_id": trace_id, "origin": "ai-patch"})
                continue

            if p_type == "STATS_QUERY_EXPERIMENT":
                patch_result, patch_states = _run_stats_experiment(client, trace_id, patch)
                added = _append_states(patch_states, new_states, seen_state_ids)
                if added == 0 and patch_states:
                    patch_result["status"] = patch_result.get("status") or "noop_duplicate"
                results.append(patch_result)
                continue

            results.append({"patch": p_type, "status": "error", "reason": "unhandled_patch_type", "trace_id": trace_id})
        except Exception as exc:  # pragma: no cover
            logger.warning("patch execution failed", exc_info=exc)
            results.append({"patch": p_type, "status": "error", "reason": str(exc), "trace_id": trace_id, "origin": "ai-patch"})

    return results, new_states


def _append_states(candidates: List[State], collector: List[State], seen: set[str]) -> int:
    added = 0
    for s in candidates:
        if s.state_id in seen:
            continue
        seen.add(s.state_id)
        collector.append(s)
        added += 1
    return added


def _run_enumerate_series(client: GridClient, trace_id: str, patch: Dict[str, Any], player_id: str, page_caps: Tuple[int, int], window_key: Optional[str] = None) -> Tuple[Dict[str, Any], List[State]]:
    params = patch.get("params") or {}
    gte = params.get("gte")
    lte = params.get("lte")
    first = min(int(params.get("first", 200)), 30)
    if not gte or not lte:
        now = datetime.now(timezone.utc)
        gte = (now - timedelta(days=180)).isoformat()
        lte = (now + timedelta(days=180)).isoformat()
    vars_query = {"gte": gte, "lte": lte, "first": first}
    series_list = _paginate(client, q.Q_ALL_SERIES_WINDOW, vars_query, ["allSeries"], max_pages=page_caps[0], max_items=page_caps[1])
    window_key = window_key or f"{gte}|{lte}"
    states: List[State] = []
    for idx, series in enumerate(series_list):
        prov = {"query_name": "allSeries", "window": {"gte": gte, "lte": lte}, "aggregation_level": "series"}
        state = _context_state(trace_id, "CONTEXT_ONLY", series, player_id, window_key, prov, idx)
        states.append(state)
    status = "ok" if series_list else "ok_empty"
    result = {"patch": "ENUMERATE_SERIES", "status": status, "reason": f"series={len(series_list)}", "trace_id": trace_id, "origin": "ai-patch"}
    return result, states


def _run_slice_by_opponent(client: GridClient, trace_id: str, patch: Dict[str, Any], player_id: str, page_caps: Tuple[int, int]) -> Tuple[Dict[str, Any], List[State]]:
    params = patch.get("params") or {}
    window_params = params.get("window") or {}
    gte = window_params.get("gte")
    lte = window_params.get("lte")
    first = min(int(params.get("limit", 200)), 30)
    if not gte or not lte:
        now = datetime.now(timezone.utc)
        gte = (now - timedelta(days=180)).isoformat()
        lte = (now + timedelta(days=180)).isoformat()
    vars_query = {"gte": gte, "lte": lte, "first": first}
    series_list = _paginate(client, q.Q_ALL_SERIES_WINDOW, vars_query, ["allSeries"], max_pages=page_caps[0], max_items=page_caps[1])
    window_key = f"{gte}|{lte}|opponent"
    states: List[State] = []
    for idx, series in enumerate(series_list):
        prov = {"query_name": "allSeries", "window": {"gte": gte, "lte": lte}, "aggregation_level": "series", "slice": "opponent"}
        opponents = series.get("teams") or []
        team_names = []
        for t in opponents:
            base = t.get("baseInfo") or {}
            if base.get("name"):
                team_names.append(str(base.get("name")))
        label = " vs ".join(sorted(team_names)) if team_names else "UNKNOWN"
        state = _context_state(trace_id, "CONTEXT_ONLY", series, player_id, window_key, prov, idx, slice_axis="opponent", slice_value=label)
        states.append(state)
    status = "ok" if series_list else "ok_empty"
    result = {"patch": "SLICE_BY_OPPONENT", "status": status, "reason": f"series={len(series_list)}", "trace_id": trace_id, "origin": "ai-patch"}
    return result, states


def _run_slice_by_time_bucket(client: GridClient, trace_id: str, patch: Dict[str, Any], player_id: str, page_caps: Tuple[int, int]) -> Tuple[Dict[str, Any], List[State]]:
    params = patch.get("params") or {}
    window_params = params.get("window") or {}
    gte = window_params.get("gte")
    lte = window_params.get("lte")
    first = min(int(params.get("limit", 200)), 30)
    if not gte or not lte:
        now = datetime.now(timezone.utc)
        gte = (now - timedelta(days=180)).isoformat()
        lte = (now + timedelta(days=180)).isoformat()
    vars_query = {"gte": gte, "lte": lte, "first": first}
    series_list = _paginate(client, q.Q_ALL_SERIES_WINDOW, vars_query, ["allSeries"], max_pages=page_caps[0], max_items=page_caps[1])
    window_key = f"{gte}|{lte}|time"
    states: List[State] = []
    for idx, series in enumerate(series_list):
        prov = {"query_name": "allSeries", "window": {"gte": gte, "lte": lte}, "aggregation_level": "series", "slice": "time_bucket"}
        start = series.get("startTimeScheduled")
        label = _time_bucket(str(start)) if start else "UNKNOWN"
        state = _context_state(trace_id, "CONTEXT_ONLY", series, player_id, window_key, prov, idx, slice_axis="time_bucket", slice_value=label)
        states.append(state)
    status = "ok" if series_list else "ok_empty"
    result = {"patch": "SLICE_BY_TIME_BUCKET", "status": status, "reason": f"series={len(series_list)}", "trace_id": trace_id, "origin": "ai-patch"}
    return result, states


def _run_enumerate_players(client: GridClient, trace_id: str, patch: Dict[str, Any], page_caps: Tuple[int, int]) -> Tuple[Dict[str, Any], List[State]]:
    params = patch.get("params") or {}
    team_id = params.get("team_id")
    if not team_id:
        return {"patch": "ENUMERATE_PLAYERS", "status": "error", "reason": "team_id missing", "trace_id": trace_id, "origin": "ai-patch"}, []
    roster = _paginate(client, q.Q_TEAM_ROSTER, {"teamId": team_id}, ["players"], max_pages=page_caps[0], max_items=page_caps[1])
    extras_state = {
        "evidence_type": "ROSTER_CONTEXT",
        "team_id": team_id,
        "roster_ids": [p.get("id") for p in roster if isinstance(p, dict) and p.get("id")],
        "trace_id": trace_id,
    }
    state = State(
        state_id=_hash_state_id(trace_id, "ROSTER_CONTEXT", str(team_id), None, "roster"),
        series_id=str(team_id),
        game_index=0,
        timestamp=0.0,
        map="context",
        score_diff=0,
        econ_diff=0,
        alive_diff=0,
        ult_diff=0,
        objective_context=None,
        phase="CONTEXT",
        extras=extras_state,
    )
    result = {"patch": "ENUMERATE_PLAYERS", "status": "ok", "reason": f"players={len(roster)}", "trace_id": trace_id, "origin": "ai-patch"}
    return result, [state]


def _run_team_stats(client: GridClient, trace_id: str, patch: Dict[str, Any], anchor_team_id: Optional[str]) -> Tuple[Dict[str, Any], List[State]]:
    params = patch.get("params") or {}
    team_id = params.get("team_id") or anchor_team_id
    tournament_ids = params.get("tournamentIds") or []
    if not team_id:
        return {"patch": "AGGREGATE_TEAM_STATISTICS", "status": "error", "reason": "team_id missing", "trace_id": trace_id, "origin": "ai-patch"}, []
    vars_query = {"teamId": team_id, "tournamentIds": tournament_ids}
    payload = client.run_query(q.Q_TEAM_STATISTICS, vars_query)
    data = (payload.get("data", {}) or {}).get("teamStatistics") if isinstance(payload, dict) else None
    filter_used = {"tournamentIds": tournament_ids}
    state = _aggregation_state(trace_id, "team", "", str(team_id), data, filter_used, 0)
    result = {"patch": "AGGREGATE_TEAM_STATISTICS", "status": "ok", "reason": "executed", "trace_id": trace_id, "origin": "ai-patch", "aggregationSeriesIds": (data or {}).get("aggregationSeriesIds") if isinstance(data, dict) else []}
    return result, [state]


def _run_player_stats(client: GridClient, trace_id: str, patch: Dict[str, Any], player_id: str) -> Tuple[Dict[str, Any], List[State]]:
    params = patch.get("params") or {}
    target_player_id = params.get("player_id") or player_id
    tournament_ids = params.get("tournamentIds") or []
    intensity_level = params.get("intensity_level")
    if not target_player_id:
        return {"patch": "AGGREGATE_PLAYER_STATISTICS", "status": "error", "reason": "player_id missing", "trace_id": trace_id, "origin": "ai-patch"}, []

    # If stats unavailable (grid disabled) but mock client in use, return structured mock
    if not getattr(q, "STATS_AVAILABLE", False) and client.__class__.__name__ == "_MockGridClient":
        mock_payload = {
            "aggregationSeriesIds": ["mock-series-1", "mock-series-2", "mock-series-3"],
            "mock": True,
            "note": "structured mock aggregation for synthesis",
            "timeWindow": time_window,
            "tournamentIds": tournament_ids,
            "scope": {"level": "player", "playerId": str(target_player_id)},
            "sample": {"series_count": 12, "map_count": 36, "round_count": 540},
            "performance": {
                "win_rate": {"value": 0.62, "baseline": 0.55, "delta": 0.07, "sample": 12},
                "rating": {"value": 1.12, "baseline": 1.0, "delta": 0.12, "sample": 36},
                "kills_per_map": {"value": 18.4, "baseline": 15.2, "delta": 0.21, "sample": 36},
            },
            "trend": {
                "last_10_series": {"win_rate": 0.70, "kills_per_map": 19.5, "rating": 1.18},
                "previous_10_series": {"win_rate": 0.55, "kills_per_map": 16.0, "rating": 1.02},
            },
            "context": {
                "format_mix": {"BO3": 8, "BO5": 2, "BO1": 2},
                "opponent_tiers": {"tier1": 5, "tier2": 5, "tier3": 2},
            },
        }
        filter_used = {"tournamentIds": tournament_ids, "mock": True, "intensity_level": intensity_level}
        state = _aggregation_state(trace_id, "player", target_player_id, str(target_player_id), mock_payload, filter_used, 0)
        result = {"patch": "AGGREGATE_PLAYER_STATISTICS", "status": "ok", "reason": "mock_returned", "trace_id": trace_id, "origin": "ai-patch", "aggregationSeriesIds": mock_payload.get("aggregationSeriesIds")}
        return result, [state]

    if not getattr(q, "STATS_AVAILABLE", False):
        return {
            "patch": "AGGREGATE_PLAYER_STATISTICS",
            "status": "unavailable",
            "reason": "schema_field_missing",
            "trace_id": trace_id,
            "origin": "ai-patch",
        }, []

    # Real Grid query
    vars_query = {"playerId": target_player_id, "tournamentIds": tournament_ids}
    payload = client.run_query(q.Q_PLAYER_STATISTICS, vars_query)
    data = (payload.get("data", {}) or {}).get("playerStatistics") if isinstance(payload, dict) else None

    aggregation_series_ids = []
    sample = {}
    perf: Dict[str, Any] = {}
    trend: Dict[str, Any] = {}
    if isinstance(data, dict):
        aggregation_series_ids = data.get("aggregationSeriesIds") or []
        series = data.get("series") or {}
        game = data.get("game") or {}
        kills = series.get("kills") or {}
        wins = (game.get("wins") or {}) if isinstance(game, dict) else {}
        series_count = series.get("count") or 0
        game_count = game.get("count") or 0
        sample = {
            "series_count": series_count,
            "map_count": game_count,
            "round_count": None,
        }
        if kills.get("avg") is not None:
            perf["kills_per_map"] = {"value": kills.get("avg"), "baseline": kills.get("avg"), "delta": 0.0, "sample": series_count}
        if wins.get("percentage") is not None:
            perc = wins.get("percentage")
            perf["win_rate"] = {
                "value": perc,
                "baseline": perc,
                "delta": 0.0,
                "sample": game_count,
            }
        # rating unavailable in current schema
        perf.setdefault("rating", {"value": None, "baseline": None, "delta": None, "sample": None})

    agg_payload = {
        "aggregationSeriesIds": aggregation_series_ids,
        "mock": False,
        "timeWindow": None,
        "tournamentIds": tournament_ids,
        "scope": {"level": "player", "playerId": str(target_player_id)},
        "sample": sample,
        "performance": perf,
        "trend": trend,
        "context": {},
    }
    filter_used = {"timeWindow": time_window, "tournamentIds": tournament_ids, "mock": False, "intensity_level": intensity_level}
    state = _aggregation_state(trace_id, "player", target_player_id, str(target_player_id), agg_payload, filter_used, 0)
    result = {
        "patch": "AGGREGATE_PLAYER_STATISTICS",
        "status": "ok",
        "reason": "executed",
        "trace_id": trace_id,
        "origin": "ai-patch",
        "aggregationSeriesIds": aggregation_series_ids,
    }
    return result, [state]


def _run_stats_experiment(client: GridClient, trace_id: str, patch: Dict[str, Any]) -> Tuple[Dict[str, Any], List[State]]:
    params = patch.get("params") or {}
    target = params.get("target")
    variant = params.get("query_variant")
    filled = params.get("filled_variables") or {}

    try:
        if target == "PLAYER_STATS":
            player_id = filled.get("playerId") or filled.get("player_id")
            if not player_id:
                return {"patch": "STATS_QUERY_EXPERIMENT", "status": "error", "reason": "playerId missing", "trace_id": trace_id, "origin": "stats-experiment"}, []
            patch_vars = {
                "patch_type": "AGGREGATE_PLAYER_STATISTICS",
                "params": {
                    "player_id": player_id,
                    "timeWindow": filled.get("timeWindow"),
                    "tournamentIds": filled.get("tournamentIds"),
                },
            }
            result, states = _run_player_stats(client, trace_id, patch_vars, player_id)
        elif target == "TEAM_STATS":
            team_id = filled.get("teamId") or filled.get("team_id")
            if not team_id:
                return {"patch": "STATS_QUERY_EXPERIMENT", "status": "error", "reason": "teamId missing", "trace_id": trace_id, "origin": "stats-experiment"}, []
            patch_vars = {
                "patch_type": "AGGREGATE_TEAM_STATISTICS",
                "params": {
                    "team_id": team_id,
                    "timeWindow": filled.get("timeWindow"),
                    "tournamentIds": filled.get("tournamentIds"),
                },
            }
            result, states = _run_team_stats(client, trace_id, patch_vars, None)
        else:
            return {"patch": "STATS_QUERY_EXPERIMENT", "status": "error", "reason": "unknown_target", "trace_id": trace_id, "origin": "stats-experiment"}, []

        result.update({"patch": "STATS_QUERY_EXPERIMENT", "target": target, "variant": variant, "origin": "stats-experiment"})
        return result, states
    except Exception as exc:  # pragma: no cover
        return {"patch": "STATS_QUERY_EXPERIMENT", "status": "schema_error", "reason": str(exc), "trace_id": trace_id, "origin": "stats-experiment"}, []
