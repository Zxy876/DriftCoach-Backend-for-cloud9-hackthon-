from __future__ import annotations

from typing import Dict, Tuple

from driftcoach.grid.grammar import stats as stats_grammar
from driftcoach.stats.spec import StatsQuerySpec


class StatsGrammar:
    """Compile StatsQuerySpec into a statistics-feed GraphQL query + variables.

    Only four combinations are allowed:
    1) player + time_window
    2) player + tournament_ids
    3) team + time_window
    4) team + tournament_ids
    """

    @staticmethod
    def compile(spec: StatsQuerySpec) -> Tuple[str, Dict[str, object]]:
        if not isinstance(spec, StatsQuerySpec) or not spec.is_valid():
            raise ValueError("stats_query_spec_invalid")

        target = spec.target
        vars_payload: Dict[str, object] = {}

        if target == "player":
            vars_payload["playerId"] = spec.target_id
            if spec.time_window:
                return stats_grammar.PLAYER_LAST_THREE_MONTHS, vars_payload
            if spec.tournament_ids:
                vars_payload["tournamentIds"] = spec.tournament_ids
                return stats_grammar.PLAYER_TOURNAMENTS, vars_payload
        elif target == "team":
            vars_payload["teamId"] = spec.target_id
            if spec.time_window:
                return stats_grammar.TEAM_LAST_THREE_MONTHS, vars_payload
            if spec.tournament_ids:
                vars_payload["tournamentIds"] = spec.tournament_ids
                return stats_grammar.TEAM_TOURNAMENTS, vars_payload

        raise ValueError("stats_query_spec_invalid")
