"""Grid statistics-feed GraphQL grammar.

Only the four allowed combinations are defined here.
"""

PLAYER_LAST_THREE_MONTHS = """
query PlayerStatisticsForLastThreeMonths($playerId: ID!) {
  playerStatistics(playerId: $playerId, filter: { timeWindow: LAST_3_MONTHS }) {
    id
    aggregationSeriesIds
    series { count kills { sum min max avg } }
    game { count wins { value count percentage streak { min max current } } }
    segment { type count deaths { sum min max avg } }
  }
}
"""

PLAYER_TOURNAMENTS = """
query PlayerStatisticsForChosenTournaments($playerId: ID!, $tournamentIds: [ID!]) {
  playerStatistics(playerId: $playerId, filter: { tournamentIds: { in: $tournamentIds } }) {
    id
    aggregationSeriesIds
    series { count kills { sum min max avg } }
    game { count wins { value count percentage streak { min max current } } }
    segment { type count deaths { sum min max avg } }
  }
}
"""

TEAM_LAST_THREE_MONTHS = """
query TeamStatisticsForLastThreeMonths($teamId: ID!) {
  teamStatistics(teamId: $teamId, filter: { timeWindow: LAST_3_MONTHS }) {
    id
    aggregationSeriesIds
    series { count kills { sum min max avg } }
    game { count wins { value count percentage streak { min max current } } }
    segment { type count deaths { sum min max avg } }
  }
}
"""

TEAM_TOURNAMENTS = """
query TeamStatisticsForChosenTournaments($teamId: ID!, $tournamentIds: [ID!]) {
  teamStatistics(teamId: $teamId, filter: { tournamentIds: { in: $tournamentIds } }) {
    id
    aggregationSeriesIds
    series { count kills { sum min max avg } }
    game { count wins { value count percentage streak { min max current } } }
    segment { type count deaths { sum min max avg } }
  }
}
"""

__all__ = [
    "PLAYER_LAST_THREE_MONTHS",
    "PLAYER_TOURNAMENTS",
    "TEAM_LAST_THREE_MONTHS",
    "TEAM_TOURNAMENTS",
]
