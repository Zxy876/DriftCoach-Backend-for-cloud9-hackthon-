from __future__ import annotations

from typing import Any, Dict, List


class EvidencePlanner:
    """Lightweight coordinator to steer mining based on research axes and Grid health."""

    def plan(
        self,
        research_plan: Any,
        research_progress: Any,
        mining_summary: Any,
        grid_health: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        missing_axes: List[str] = getattr(research_progress, "missing_axes", []) or []
        grid_health = grid_health or {}
        run_remaining = grid_health.get("run_budget_remaining")
        global_remaining = grid_health.get("global_remaining")
        circuit_state = grid_health.get("circuit_state")

        budget_denied = bool(circuit_state == "OPEN")
        if run_remaining is not None and run_remaining <= 0:
            budget_denied = True
        if global_remaining is not None and global_remaining <= 0:
            budget_denied = True

        directives: Dict[str, Any] = {
            "grid_blocked": budget_denied,
            "mining_goal_override": "EXPAND_GRAPH_FOR_CONTEXT",
            "preferred_templates": [],
            "stop_policy_override": {},
            "stats_execution_allowed": not budget_denied,
        }

        if "baseline" in missing_axes:
            directives["mining_goal_override"] = "EXPAND_GRAPH_TOWARDS_BASELINE_PROXY"
            directives["preferred_templates"] = [
                "SERIES_TO_TEAMS_MIN",
                "SERIES_TO_TOURNAMENT_MIN",
                "TEAM_TO_SERIES_MIN",
                "TOURNAMENT_TO_SERIES_MIN",
            ]
            directives["stats_target_hint"] = ["player", "team"]

        if budget_denied:
            directives["stop_policy_override"] = {
                "allow_proxy_completion": True,
                "reason": "grid_budget_or_circuit",
            }
            directives["stats_execution_allowed"] = False

        return directives
