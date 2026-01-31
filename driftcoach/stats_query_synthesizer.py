from __future__ import annotations

from typing import Any, Dict, List

from driftcoach.research import ResearchPlan


StatsQueryCandidate = Dict[str, Any]


STATS_QUERY_TEMPLATES: List[Dict[str, Any]] = [
    {
        "template_name": "TeamStatisticsForLastThreeMonths",
        "target": "TEAM_STATS",
        "query_variant": "TIME_WINDOW",
        "graphql_template": """query TeamStatisticsForLastThreeMonths($teamId: ID!){\n  teamStatistics(teamId: $teamId, filter:{}){ id aggregationSeriesIds series{count kills{sum min max avg}} game{count wins{value count percentage streak{min max current}}} segment{type count deaths{sum min max avg}} }\n}""",
        "required_axes_unlocked": ["baseline", "opponent"],
        "defaults": {},
        "variables": ["teamId"],
    },
    {
        "template_name": "TeamStatisticsForChosenTournaments",
        "target": "TEAM_STATS",
        "query_variant": "TOURNAMENT_FILTER",
        "graphql_template": """query TeamStatisticsForChosenTournaments($teamId: ID!, $tournamentIds: [ID!]){\n  teamStatistics(teamId: $teamId, filter:{ tournamentIds:{ in: $tournamentIds }}){ id aggregationSeriesIds series{count kills{sum min max avg}} game{count wins{value count percentage streak{min max current}}} segment{type count deaths{sum min max avg}} }\n}""",
        "required_axes_unlocked": ["baseline", "opponent"],
        "defaults": {},
        "variables": ["teamId", "tournamentIds"],
    },
    {
        "template_name": "PlayerStatisticsForLastThreeMonths",
        "target": "PLAYER_STATS",
        "query_variant": "TIME_WINDOW",
        "graphql_template": """query PlayerStatisticsForLastThreeMonths($playerId: ID!){\n  playerStatistics(playerId: $playerId, filter:{}){ id aggregationSeriesIds series{count kills{sum min max avg}} game{count wins{value count percentage streak{min max current}}} segment{type count deaths{sum min max avg}} }\n}""",
        "required_axes_unlocked": ["baseline", "time"],
        "defaults": {},
        "variables": ["playerId"],
    },
    {
        "template_name": "PlayerStatisticsForChosenTournaments",
        "target": "PLAYER_STATS",
        "query_variant": "TOURNAMENT_FILTER",
        "graphql_template": """query PlayerStatisticsForChosenTournaments($playerId: ID!, $tournamentIds: [ID!]){\n  playerStatistics(playerId: $playerId, filter:{ tournamentIds:{ in: $tournamentIds }}){ id aggregationSeriesIds series{count kills{sum min max avg}} game{count wins{value count percentage streak{min max current}}} segment{type count deaths{sum min max avg}} }\n}""",
        "required_axes_unlocked": ["baseline", "time"],
        "defaults": {},
        "variables": ["playerId", "tournamentIds"],
    },
]


def _first(lst):
    return lst[0] if isinstance(lst, list) and lst else None


def synthesize_stats_candidates(research_plan: ResearchPlan, mining_summary: Any, intent: str) -> List[StatsQueryCandidate]:
    discovered = {}
    if mining_summary is not None:
        if isinstance(mining_summary, dict):
            discovered = mining_summary.get("discovered") or mining_summary.get("entity_counts") or {}
        else:
            discovered = getattr(mining_summary, "discovered", {}) or getattr(mining_summary, "entity_counts", {}) or {}

    players: List[str] = []
    teams: List[str] = []
    tournaments: List[str] = []

    for key in ("players", "player"):
        val = discovered.get(key)
        if isinstance(val, list):
            players.extend([str(x) for x in val if x is not None and str(x) != ""])
        elif isinstance(val, (int, str)):
            players.append(str(val))

    for key in ("teams", "team"):
        val = discovered.get(key)
        if isinstance(val, list):
            teams.extend([str(x) for x in val if x is not None and str(x) != ""])
        elif isinstance(val, (int, str)):
            teams.append(str(val))

    tval = discovered.get("tournaments")
    if isinstance(tval, list):
        tournaments = [str(x) for x in tval if x]

    candidates: List[StatsQueryCandidate] = []

    def _build_candidate(template: Dict[str, Any], filled: Dict[str, Any]) -> StatsQueryCandidate:
        return {
            "target": template["target"],
            "query_variant": template["query_variant"],
            "template_name": template["template_name"],
            "graphql_query": template["graphql_template"],
            "filled_variables": filled,
            "estimated_cost": "HIGH",
            "required_axes_unlocked": template.get("required_axes_unlocked", []),
            "confidence": "MEDIUM",
            "stop_on_failure": True,
        }

    # Priority: player time > player tournament > team time > team tournament
    if players:
        tmpl = next(t for t in STATS_QUERY_TEMPLATES if t["template_name"] == "PlayerStatisticsForLastThreeMonths")
        for pid in players:
            candidates.append(_build_candidate(tmpl, {"playerId": pid}))
        if tournaments:
            tmpl = next(t for t in STATS_QUERY_TEMPLATES if t["template_name"] == "PlayerStatisticsForChosenTournaments")
            candidates.append(_build_candidate(tmpl, {"playerId": players[0], "tournamentIds": tournaments}))

    if teams:
        tmpl = next(t for t in STATS_QUERY_TEMPLATES if t["template_name"] == "TeamStatisticsForLastThreeMonths")
        for tid in teams:
            candidates.append(_build_candidate(tmpl, {"teamId": tid}))
        if tournaments:
            tmpl = next(t for t in STATS_QUERY_TEMPLATES if t["template_name"] == "TeamStatisticsForChosenTournaments")
            candidates.append(_build_candidate(tmpl, {"teamId": teams[0], "tournamentIds": tournaments}))

    return candidates
