
⸻

① 统一约定（所有 query 通用）
	•	只用 variables，不拼字符串
	•	不引入任何未在 Playground 出现的字段
	•	所有 filter 都是可选/可裁剪的

⸻

② Series 相关（Anchor / 扩样本的根）

Q_SERIES_BY_ID（Anchor Series）

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

用途
	•	SLICE_SERIES_WINDOW 的第一步
	•	取 startTimeScheduled / format / tournament

⸻

Q_ALL_SERIES_WINDOW（核心扩样本）

query AllSeriesWindow(
  $gte: DateTime!
  $lte: DateTime!
  $first: Int = 50
  $after: String
) {
  allSeries(
    filter: {
      startTimeScheduled: {
        gte: $gte
        lte: $lte
      }
    }
    orderBy: StartTimeScheduled
    first: $first
    after: $after
  ) {
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
  }
}

用途
	•	PATCH: ENUMERATE_SERIES
	•	PATCH: SLICE_SERIES_WINDOW（第二步）
	•	这是你 delta_states 最容易 >0 的 patch

⸻

Q_SERIES_FORMATS（辅助上下文）

query SeriesFormats {
  seriesFormats {
    id
    name
    nameShortened
  }
}


⸻

③ Team / Player 实体（为 stats 铺路）

Q_TEAM_BY_ID

query TeamById($id: ID!) {
  team(id: $id) {
    id
    name
    colorPrimary
    colorSecondary
    logoUrl
  }
}


⸻

Q_TEAM_ROSTER（ENUMERATE_PLAYERS）

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

用途
	•	PATCH: ENUMERATE_PLAYERS
	•	只产 roster ids，不一定产 EvidenceState

⸻

Q_PLAYER_BY_ID

query PlayerById($id: ID!) {
  player(id: $id) {
    id
    nickname
    title {
      name
    }
  }
}


⸻

④ Stats（真正“养活分析器”的 patch）

⚠️ 注意：
stats 一定要被当成“可能 unavailable”，但 query 本身是合法的

⸻

Q_TEAM_STATISTICS_TIMEWINDOW

query TeamStatisticsTimeWindow(
  $teamId: ID!
  $timeWindow: TimeWindow!
) {
  teamStatistics(
    teamId: $teamId
    filter: { timeWindow: $timeWindow }
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

变量示例

{
  "teamId": "83",
  "timeWindow": "LAST_3_MONTHS"
}


⸻

Q_TEAM_STATISTICS_TOURNAMENTS

query TeamStatisticsTournaments(
  $teamId: ID!
  $tournamentIds: [ID!]!
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


⸻

Q_PLAYER_STATISTICS_TIMEWINDOW

query PlayerStatisticsTimeWindow(
  $playerId: ID!
  $timeWindow: TimeWindow!
) {
  playerStatistics(
    playerId: $playerId
    filter: { timeWindow: $timeWindow }
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


⸻

Q_PLAYER_STATISTICS_TOURNAMENTS

query PlayerStatisticsTournaments(
  $playerId: ID!
  $tournamentIds: [ID!]!
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


⸻

⑤ PatchExecutor 应该怎么用这些模板（关键）

 
PatchExecutor 规则
	•	不再调用 planner.execute_plan
	•	每个 PatchType → 固定调用一个 query 模板
	•	只负责：
	1.	填 variables
	2.	run_query
	3.	把 response → EvidenceState
	•	GraphQL errors 中如出现 ENHANCE_YOUR_CALM：
	•	retry ≤3（指数退避 + jitter）
	•	retry 失败 → patch status=failed(rate_limited)
	•	stats query 返回空/null → EvidenceState 标记 aggregation_unavailable=true，但仍算一次 patch 执行

⸻

⑥ 为什么这一步一定会让 delta_states 动起来
	•	ENUMERATE_SERIES → 必然产生 CONTEXT_ONLY states
	•	stats 类 patch → 即使 aggregation 不可用，也会生成 AGGREGATED_PERFORMANCE（with unavailable flag）
	•	所有 query 都是 你已在 Grid Playground 验证过的

👉 这意味着：
delta_states = 0 的唯一可能，只剩“真的没有任何新事实”
而不是“infra 写错 / query 被打回”。

 