from __future__ import annotations
from typing import Dict, Any, List, Tuple

from driftcoach.adapters.grid.patch_executor import execute_patches
from driftcoach.mining.planner import MiningPlan


def mining_plan_to_patch(plan: MiningPlan) -> Tuple[Dict[str, Any] | None, str | None]:
    """
    Map MiningPlan to existing PatchExecutor patch payload.
    Returns (patch, reason_if_none).
    Only MIN templates are supported; no field extension or smart guessing.
    """
    tid = plan.query_template.template_id
    subs = plan.substitutions or {}

    if tid == "SERIES_TO_TEAMS_MIN":
        # Enumerate series window (uses existing executor query) to harvest team_ids from series nodes
        return {"patch_type": "ENUMERATE_SERIES", "params": {"first": 30}}, None
    if tid == "SERIES_BASIC_MIN":
        return {"patch_type": "ENUMERATE_SERIES", "params": {"first": 20}}, None
    if tid == "PLAYER_TO_SERIES_MIN":
        # No direct mapping with current executor; unsupported
        return None, "unsupported_template_mapping"
    if tid == "TEAM_TO_PLAYERS_MIN":
        team_id = subs.get("teamId") or subs.get("team_id")
        if not team_id:
            return None, "missing_team_id"
        return {"patch_type": "ENUMERATE_PLAYERS", "params": {"team_id": team_id}}, None
    if tid == "TEAM_TO_SERIES_MIN":
        return {"patch_type": "ENUMERATE_SERIES", "params": {"first": 30}}, None
    if tid == "TOURNAMENT_TO_SERIES_MIN":
        return {"patch_type": "ENUMERATE_SERIES", "params": {"first": 30}}, None
    if tid == "SERIES_TO_TOURNAMENT_MIN":
        return {"patch_type": "ENUMERATE_SERIES", "params": {"first": 20}}, None

    return None, "unsupported_template_id"


def execute_mining_plan(
    plan: MiningPlan,
    data_source: str,
    grid_api_key: str | None,
    grid_player_id: str,
    grid_series_id: str,
    anchor_team_id: str | None = None,
) -> Tuple[List[Dict[str, Any]], List[Any]]:
    patch, reason = mining_plan_to_patch(plan)
    if patch is None:
        return [{"patch": plan.query_template.template_id, "status": "error", "reason": reason, "origin": "mining"}], []

    try:
        results, new_states = execute_patches(
            proposed=[patch],
            max_patches=1,
            data_source=data_source,
            grid_api_key=grid_api_key,
            grid_player_id=grid_player_id,
            grid_series_id=grid_series_id,
            anchor_team_id=anchor_team_id,
        )
    except Exception as exc:  # pragma: no cover
        return [
            {
                "patch": plan.query_template.template_id,
                "status": "error",
                "reason": str(exc),
                "origin": "mining",
            }
        ], []
    return results, new_states
