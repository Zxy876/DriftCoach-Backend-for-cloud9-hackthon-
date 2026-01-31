from __future__ import annotations

from typing import Any, Dict, List, Iterable

from driftcoach.mining.planner import MiningSummary, QueryAttempt


_TEMPLATE_PATH_LABELS = {
    "SERIES_TO_TEAMS_MIN": "series → teams",
    "SERIES_BASIC_MIN": "series → series",
    "SERIES_TO_TOURNAMENT_MIN": "series → tournament",
    "TEAM_TO_PLAYERS_MIN": "team → players",
    "PLAYER_TO_SERIES_MIN": "player → series",
    "TEAM_TO_SERIES_MIN": "team → series",
    "TOURNAMENT_TO_SERIES_MIN": "tournament → series",
}


def _coerce_attempts(obj: Any) -> List[QueryAttempt | Dict[str, Any]]:
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    return []


def _normalize_attempt(attempt: QueryAttempt | Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(attempt, QueryAttempt):
        return {
            "template_id": attempt.template_id,
            "substitutions": attempt.substitutions,
            "entity_id": attempt.entity_id,
            "result": attempt.result,
            "notes": attempt.notes,
            "discovered_ids": attempt.discovered_ids,
            "error_path": attempt.error_path,
        }
    return {
        "template_id": attempt.get("template_id"),
        "substitutions": attempt.get("substitutions", {}),
        "entity_id": attempt.get("entity_id"),
        "result": attempt.get("result"),
        "notes": attempt.get("notes"),
        "discovered_ids": attempt.get("discovered_ids", []) or [],
        "error_path": attempt.get("error_path"),
    }


def _format_attempt(att: Dict[str, Any]) -> str:
    path_label = _TEMPLATE_PATH_LABELS.get(att.get("template_id"), att.get("template_id") or "unknown")
    result = (att.get("result") or "unknown").upper()
    discovered = att.get("discovered_ids") or []
    extra = ""
    if discovered:
        extra = f", discovered {len(discovered)} entities"
    elif att.get("error_path"):
        extra = f", error at {att['error_path']}"
    return f"{path_label} ({result}{extra})"


def _flatten_seeds(seeds: Dict[str, Iterable[str]]) -> List[str]:
    flat: List[str] = []
    for etype, ids in (seeds or {}).items():
        for eid in ids or []:
            flat.append(f"{etype.rstrip('s')}:{eid}")
    return flat


def _compute_new_entities(seeds: Dict[str, List[str]] | None, discovered: Dict[str, List[str]] | None) -> Dict[str, List[str]]:
    seeds = seeds or {}
    discovered = discovered or {}
    new_entities: Dict[str, List[str]] = {}
    for etype, ids in discovered.items():
        seed_ids = set(seeds.get(etype, []))
        new_ids = [eid for eid in ids if eid not in seed_ids]
        new_entities[etype] = new_ids
    return new_entities


def _blocking_reason(termination_reason: str | None, blocked_paths: Any) -> str:
    if termination_reason == "API_CONSTRAINED":
        return "API rate limit or network constrained"
    if termination_reason == "ALL_TEMPLATES_BLOCKED":
        return "All templates are blocked by schema or rules"
    if termination_reason == "ALL_COMBINATIONS_EMPTY":
        return "Tried combinations returned empty results"
    if termination_reason == "INTENSITY_MAX_NO_PROGRESS":
        return "Reached max intensity without progress"
    if termination_reason == "FRONTIER_EXHAUSTED":
        return "No further expandable nodes in current frontier"
    if blocked_paths and getattr(blocked_paths, "field_paths", None):
        return "GraphQL schema blocks further expansion"
    return "Exploration stopped"


def render_mining_narrative(mining_summary: MiningSummary | Dict[str, Any] | None) -> Dict[str, Any]:
    if mining_summary is None:
        return {}

    summary_dict: Dict[str, Any]
    if isinstance(mining_summary, MiningSummary):
        summary_dict = {
            "seeds": mining_summary.seeds,
            "discovered": mining_summary.discovered,
            "attempts": mining_summary.attempts,
            "blocked": mining_summary.blocked,
            "frontier_exhausted": mining_summary.frontier_exhausted,
            "termination_reason": mining_summary.termination_reason,
        }
    else:
        summary_dict = mining_summary

    seeds = summary_dict.get("seeds") or {}
    discovered = summary_dict.get("discovered") or {}
    attempts_raw = summary_dict.get("attempts")
    attempts = [_normalize_attempt(a) for a in _coerce_attempts(attempts_raw)]

    narrative = {
        "starting_seeds": _flatten_seeds(seeds),
        "attempted_paths": [_format_attempt(att) for att in attempts],
        "new_entities": _compute_new_entities(seeds, discovered),
        "blocking_reason": _blocking_reason(summary_dict.get("termination_reason"), summary_dict.get("blocked")),
        "frontier_exhausted": bool(summary_dict.get("frontier_exhausted")),
        "termination_reason": summary_dict.get("termination_reason"),
    }

    return narrative


__all__ = ["render_mining_narrative"]
