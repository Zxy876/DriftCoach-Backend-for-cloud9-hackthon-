# DataMiningPlanner（代入式数据挖掘）一页工程指令

> 目标：在 **无 introspection / 无 stats / schema 不透明** 的约束下，持续挖掘可达子图，并为后续执行层提供“可执行的请求体计划”。Planner 只做决策，不直接发 GraphQL。

## 0. 现实约束（不可改）
- Grid GraphQL：禁止 introspection；`playerStatistics`/`teamStatistics` 不可用；部分字段缺失（如 `player.name`、`allSeries.*`）。
- 已有种子：真实 `player_id`、`series_id`；时间窗口可控。
- 现有能力：patch 执行、iteration/intensity、research_task。
- **禁止** 在 Planner 层假设 stats 可达。

## 1. 模块定位
```
AI reasoning
  ↓
DataMiningPlanner  ← 新增（只产计划、不执行）
  ↓
Patch Generator
  ↓
Executor
  ↓
Context
```
职责：
1) 维护已知实体池；2) 选择下一步挖掘目标；3) 生成可执行的请求体计划。

## 2. 输入 / 输出契约
**Input: `MiningContext`**
- `known_entities`: `{ players: ID[], series: ID[], teams: ID[], tournaments: ID[] }`（去重，记录来源）
- `attempted_queries`: `QuerySignature[]`（模板 + substitutions）
- `blocked_paths`: `string[]`（schema error 的模板 ID 或字段路径）
- `iteration_state`: `{ depth: number, intensity: L0–L5 }

**Output: `MiningPlan`**
- `goal`: `EXPAND_GRAPH | CONFIRM_LINK | NARROW_SCOPE`
- `target_entity`: `player | series | team`
- `query_template`: `TemplateID`
- `substitutions`: `Record<string, ID>`
- `expected_signal`: `new_id | new_link | non_empty_connection`

## 3. 核心组件
### 3.1 Entity Pool
- 所有 ID 去重；记录 `source_query` 和 `source_entity`。
- 空结果 **不删除** 实体，避免误杀。

### 3.2 Query Template Registry（禁止即兴写 query；默认只用 MIN 形态）
模板必须分层，默认使用 MIN（最小可接受字段），RICH 仅在 MIN 成功后再尝试。

示例（可扩充）：
- `SERIES_TO_TEAMS_MIN`: `series(id:$seriesId){ teams{ id } }`
- `SERIES_TO_TEAMS_RICH` *(二级尝试)*: `series(id:$seriesId){ teams{ id baseInfo{ id name } } }`
- `SERIES_TO_TOURNAMENT_MIN`: `series(id:$seriesId){ tournament{ id } }`
- `TEAM_TO_PLAYERS_MIN`: `team(id:$teamId){ players{ id } }`
- `PLAYER_TO_SERIES_MIN`: `player(id:$playerId){ series{ id } }`
- `TEAM_TO_SERIES_MIN`: `series(filter:{ teamIds:[$teamId] }){ id }` *(若 filter 被接受)*
- `TOURNAMENT_TO_SERIES_MIN`: `series(filter:{ tournamentIds:[$tournamentId] }){ id }`
- `SERIES_BASIC_MIN`: `series(id:$seriesId){ id }` *(最小探测，占位)*

> 规则：先 MIN 后 RICH；字段级错误只降级/冻结对应 RICH，不封杀 MIN 模板。

### 3.3 代入式搜索逻辑
每一轮：
1) 从 entity pool 选一个“未充分展开”的实体（优先：新发现、未被此模板尝试）。
2) 找到可接受该实体类型的模板集合（先 MIN，MIN 成功后才允许 RICH）。
3) 生成 substitutions（如 `{seriesId: known_series}`）。
4) 过滤掉 `attempted_queries` / `blocked_paths`（分层规则见下）/ 达到 empty 冷却的组合。
5) 产出 `MiningPlan`（含 `expected_signal`）。

## 4. 成功 / 失败信号（含分层阻塞与空结果冷却）
- **成功**（任一即可）：返回新 ID；返回非空 connection；扩大 entity pool；解锁新模板。
- **失败处理分层**：
  - `schema error`（字段级）→ 记录到 `blocked_paths.field_paths`，对应模板保持可用，但降级/跳过 RICH 字段。
  - `schema error`（模板级 shape 不被接受）→ 记录到 `blocked_paths.template_id`。
  - `substitution 不匹配`（ID 组合导致错误）→ 记录到 `blocked_paths.substitution_pairs`（template+entity）。
  - `empty result` → 对 `(template_id, entity_id)` 递增 `empty_count`；`empty_count ≥ 2` 进入 cooldown。

**Empty Result Policy（最小规则）**
- 维护 `empty_count[(template_id, entity_id)]`。
- `empty_count ≥ 2` → 冷却该组合（不再尝试）。
- 冷却解除条件：强度升级（intensity 上升）或 entity pool 有新增 ID。

## 5. 与 intensity 的映射
- L1：单实体、单 hop
- L2：单实体、多模板尝试
- L3：跨实体链（player→series→team）
- L4：多 seed 并行（并行多个实体）
- L5：回溯 + 重组（对 blocked/empty 组合做再尝试或路径换序）

## 6. 终止条件 + 验收清单
**Planner Termination Conditions（优雅停机）**
- 连续 N 轮（建议 N=2）`known_entities` 无新增 ID。
- 所有可用模板组合均在 cooldown（含 substitution 冻结）。
- intensity 已达 L5 且无新路径。
→ 产出 `MiningSummary`（尝试过的模板/反馈/blocked/空结果）并终止。

**验收清单**
- stats 不可用时仍能产出 `MiningPlan`
- 不依赖 introspection
- 2–3 轮内 `known_entities` 规模有增长（ID 数量或类型）
- iteration 不再卡死在 `small_sample`
- 即便无 stats，也能输出“可解释的挖掘路径”（列出尝试过的模板与反馈）

## 7. 最后一条
> 不要问“字段在不在”，而要问：“这个 entity 能否作为参数，被哪个 query 接受？”
