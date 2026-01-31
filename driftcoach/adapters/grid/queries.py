"""
Frozen Grid GraphQL query templates (validated in Playground).
- Do not alter field names or shapes.
- Only variables are meant to change.
"""

import os

Q_TOURNAMENTS = """
query Tournaments($first: Int = 50, $after: String) {
  tournaments(first: $first, after: $after) {
    totalCount
    pageInfo {
      hasPreviousPage
      hasNextPage
      startCursor
      endCursor
    }
    edges {
      cursor
      node {
        id
        nameShortened
      }
    }
  }
}
"""

Q_TOURNAMENT = """
query Tournament($id: ID!) {
  tournament(id: $id) {
    id
    nameShortened
  }
}
"""

Q_ALL_SERIES_WINDOW = """
query GetAllSeriesInWindow($gte: String!, $lte: String!, $first: Int!) {
  allSeries(
    filter: {
      startTimeScheduled: {
        gte: $gte
        lte: $lte
      }
    }
    first: $first
  ) {
    edges {
      node {
        id
        startTimeScheduled
        format { name }
        tournament { nameShortened }
        teams { baseInfo { id name } }
      }
    }
  }
}
"""

Q_SERIES_BY_ID = """
query SeriesById($id: ID!) {
  series(id: $id) {
    id
    title {
      nameShortened
    }
    tournament {
      nameShortened
    }
    startTimeScheduled
    format {
      name
      nameShortened
    }
    teams {
      baseInfo {
        name
      }
      scoreAdvantage
    }
  }
}
"""

Q_SERIES_FORMATS = """
query SeriesFormats {
  seriesFormats {
    id
    name
    nameShortened
  }
}
"""

Q_TEAM_BY_ID = """
query TeamById($id: ID!) {
  team(id: $id) {
    id
    name
    colorPrimary
    colorSecondary
    logoUrl
  }
}
"""

Q_TEAMS = """
query Teams($first: Int = 50, $after: String) {
  teams(first: $first, after: $after) {
    totalCount
    pageInfo {
      hasPreviousPage
      hasNextPage
      startCursor
      endCursor
    }
    edges {
      cursor
      node {
        id
        name
        colorPrimary
        colorSecondary
        logoUrl
      }
    }
  }
}
"""

Q_PLAYER_BY_ID = """
query PlayerById($id: ID!) {
  player(id: $id) {
    id
    nickname
    title {
      name
    }
  }
}
"""

Q_PLAYERS = """
query Players($first: Int = 50, $after: String) {
  players(first: $first, after: $after) {
    totalCount
    pageInfo {
      hasPreviousPage
      hasNextPage
      startCursor
      endCursor
    }
    edges {
      cursor
      node {
        id
        nickname
        title {
          name
        }
      }
    }
  }
}
"""

Q_TEAM_ROSTER = """
query TeamRoster($teamId: ID!) {
  players(filter: { teamIdFilter: { id: $teamId } }) {
    edges {
      node {
        id
        nickname
        title {
          name
        }
      }
    }
    pageInfo {
      hasNextPage
      hasPreviousPage
    }
  }
}
"""

Q_TEAM_STATISTICS = """
query TeamStatistics(
  $teamId: ID!
  $tournamentIds: [ID!]
) {
  teamStatistics(
    teamId: $teamId
    filter: { tournamentIds: { in: $tournamentIds } }
  ) {
    id
    aggregationSeriesIds
    series {
      count
      kills {
        sum
        min
        max
        avg
      }
    }
    game {
      count
      wins {
        value
        count
        percentage
        streak {
          min
          max
          current
        }
      }
    }
    segment {
      type
      count
      deaths {
        sum
        min
        max
        avg
      }
    }
  }
}
"""

Q_PLAYER_STATISTICS = """
query PlayerStatistics(
  $playerId: ID!
  $tournamentIds: [ID!]
) {
  playerStatistics(
    playerId: $playerId
    filter: { tournamentIds: { in: $tournamentIds } }
  ) {
    id
    aggregationSeriesIds
    series {
      count
      kills {
        sum
        min
        max
        avg
      }
    }
    game {
      count
      wins {
        value
        count
        percentage
        streak {
          min
          max
          current
        }
      }
    }
    segment {
      type
      count
      deaths {
        sum
        min
        max
        avg
      }
    }
  }
}
"""

STATS_AVAILABLE = (os.getenv("GRID_STATS_AVAILABLE") or "false").lower() == "true"
