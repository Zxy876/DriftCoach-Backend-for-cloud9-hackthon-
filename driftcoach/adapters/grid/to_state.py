import datetime as dt
import logging
from typing import Any, Dict, List, Optional, Tuple

from driftcoach.core.state import State

logger = logging.getLogger(__name__)


ActionTag = str


def _to_ts(value: Any) -> float:
    if not value:
        return 0.0
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _format_name(series: Dict[str, Any]) -> Optional[str]:
    fmt = series.get("format")
    if isinstance(fmt, dict):
        return fmt.get("name")
    if isinstance(fmt, str):
        return fmt
    return None


def _tournament_name(series: Dict[str, Any]) -> Optional[str]:
    t = series.get("tournament")
    if isinstance(t, dict):
        return t.get("name")
    if isinstance(t, str):
        return t
    return None


def _team_ids(series: Dict[str, Any]) -> List[str]:
    teams = series.get("teams") or []
    ids: List[str] = []
    for t in teams:
        base = t.get("baseInfo") or {}
        if base.get("id"):
            ids.append(str(base.get("id")))
    return ids


def _team_names(series: Dict[str, Any]) -> List[str]:
    teams = series.get("teams") or []
    names: List[str] = []
    for t in teams:
        base = t.get("baseInfo") or {}
        if base.get("name"):
            names.append(str(base.get("name")))
    return names


def _action_tags(series: Dict[str, Any]) -> List[ActionTag]:
    tags: List[ActionTag] = []
    fmt = (_format_name(series) or "").lower()
    if "bo1" in fmt:
        tags.append("PLAY_BO1")
    if "bo3" in fmt or "best of 3" in fmt:
        tags.append("PLAY_BO3")

    tourn = (_tournament_name(series) or "").lower()
    if "playoff" in tourn or "final" in tourn:
        tags.append("PLAYOFF")
    elif tourn:
        tags.append("REGULAR_SEASON")

    return tags


def _bucket_key(series: Dict[str, Any]) -> str:
    fmt = (_format_name(series) or "").lower()
    if "bo3" in fmt:
        return "BO3"
    if "bo1" in fmt:
        return "BO1"
    return "OTHER"


def _outcome(series: Dict[str, Any]) -> Optional[str]:
    if series.get("winner"):
        return "WIN"
    if isinstance(series.get("winner"), str) and series.get("winner"):
        return "WIN"
    result = series.get("result") or series.get("outcome")
    if isinstance(result, str):
        res = result.lower()
        if "win" in res:
            return "WIN"
        if "loss" in res or "lose" in res:
            return "LOSS"
    teams = series.get("teams") or []
    if len(teams) >= 2:
        scores = [t.get("score") for t in teams]
        if all(isinstance(s, (int, float)) for s in scores):
            if scores[0] > scores[1]:
                return "WIN"
            if scores[0] < scores[1]:
                return "LOSS"
    return None


def _make_state(
    idx: int,
    evidence_type: str,
    series: Dict[str, Any],
    outcome: Optional[str],
    player_id: str,
    provenance: Dict[str, Any],
) -> State:
    sid = series.get("id", "unknown")
    state_id = f"{evidence_type}_{idx:03d}"
    timestamp = _to_ts(series.get("startTimeScheduled") or series.get("startTime"))
    extras = {
        "evidence_type": evidence_type,
        "slice_type": evidence_type,
        "outcome": outcome,
        "player_id": player_id,
        "series_id": sid,
        "team_ids": _team_ids(series),
        "tournament": _tournament_name(series),
        "format": _format_name(series),
        "start_time": series.get("startTimeScheduled") or series.get("startTime"),
        "action_tags": _action_tags(series),
        "provenance": provenance,
    }
    return State(
        state_id=state_id,
        series_id=str(sid),
        game_index=idx,
        timestamp=timestamp,
        map="context",
        score_diff=0,
        econ_diff=0,
        alive_diff=0,
        ult_diff=0,
        objective_context=None,
        phase="CONTEXT",
        extras=extras,
    )


def build_states(
    anchor_series: Dict[str, Any],
    series_pool: List[Dict[str, Any]],
    player_id: str,
    outcome_field: str,
    roster_proxy: str = "UNKNOWN",
    player_stats_info: Optional[Dict[str, Any]] = None,
    team_stats_info: Optional[Dict[str, Any]] = None,
) -> Tuple[List[State], Dict[str, Any]]:
    states: List[State] = []

    # Anchor fixed slices
    anchor_prov = {"step_ids": ["anchor"], "fields_used": ["series"], "aggregation_level": "series"}
    for idx, ev_type in enumerate(["FORMAT_CONTEXT", "TOURNAMENT_CONTEXT", "SCHEDULE_CONTEXT", "OPPONENT_CONTEXT"]):
        states.append(_make_state(idx, ev_type, anchor_series, None, player_id, anchor_prov))

    # Series pool slices
    for idx, series in enumerate(series_pool):
        outcome_val = _outcome(series)
        ev_type = "SERIES_OUTCOME" if outcome_val else "CONTEXT_ONLY"
        prov = {"step_ids": ["pool"], "fields_used": [outcome_field or "unknown"], "aggregation_level": "series"}
        states.append(_make_state(idx, ev_type, series, outcome_val, player_id, prov))

    # Aggregated performance (best-effort placeholder)
    def _add_aggregation_state(level: str, info: Optional[Dict[str, Any]]):
        if info is None:
            return
        data = info.get("data") if isinstance(info, dict) else None
        reason = info.get("reason") if isinstance(info, dict) else "unknown"
        query_name = info.get("query_name") if isinstance(info, dict) else None
        agg_ids = info.get("aggregation_series_ids") if isinstance(info, dict) else None

        available = bool(data)
        perf_series = {
            "id": anchor_series.get("id", f"agg_{level}"),
            "tournament": anchor_series.get("tournament"),
            "format": anchor_series.get("format"),
            "startTimeScheduled": anchor_series.get("startTimeScheduled"),
        }
        prov = {
            "step_ids": [f"{level}_stats"],
            "fields_used": [query_name or f"{level}Statistics"],
            "aggregation_level": level,
            "aggregationSeriesIds": agg_ids or [],
        }
        state = _make_state(len(states), "AGGREGATED_PERFORMANCE", perf_series, None, player_id, prov)
        state.extras.update(
            {
                "aggregation_level": level,
                "aggregation_unavailable": not available,
                "aggregation_reason": reason,
                "aggregation_series_ids": agg_ids or [],
            }
        )
        if isinstance(data, dict):
            state.extras["aggregation_raw"] = data
        states.append(state)

    _add_aggregation_state("team", team_stats_info)
    _add_aggregation_state("player", player_stats_info)

    aggregation_available = any(
        (
            isinstance(team_stats_info, dict) and team_stats_info.get("data"),
            isinstance(player_stats_info, dict) and player_stats_info.get("data"),
        )
    )

    # Metrics for evidence context
    bucket_counts: Dict[str, int] = {}
    for s in series_pool:
        key = _bucket_key(s)
        bucket_counts[key] = bucket_counts.get(key, 0) + 1

    evidence_meta = {
        "states": len(states),
        "seriesPool": len(series_pool),
        "buckets": bucket_counts,
        "roster_proxy": roster_proxy,
        "aggregation_available": bool(aggregation_available),
        "aggregation_meta": {
            "team": {
                "available": bool(team_stats_info and team_stats_info.get("data")),
                "reason": (team_stats_info or {}).get("reason"),
            },
            "player": {
                "available": bool(player_stats_info and player_stats_info.get("data")),
                "reason": (player_stats_info or {}).get("reason"),
            },
            "aggregated_states": len([s for s in states if s.extras.get("evidence_type") == "AGGREGATED_PERFORMANCE"]),
        },
    }

    schema_ctx = {
        "hasOutcome": outcome_field != "NOT_FOUND",
        "outcome_field": outcome_field,
        "missing": [] if outcome_field != "NOT_FOUND" else ["Series.winner", "Series.teams.score"],
    }

    return states, {"schema": schema_ctx, "evidence": evidence_meta}


# Deprecated legacy aliases for compatibility
def games_to_states(_: List[Dict[str, Any]]):  # pragma: no cover
    logger.warning("games_to_states deprecated under central-data path; use build_states")
    return []


def series_to_states(series_payload: Dict[str, Any], stats_payload: Dict[str, Any]):  # pragma: no cover
    logger.warning("series_to_states is deprecated; use build_states")
    return []
