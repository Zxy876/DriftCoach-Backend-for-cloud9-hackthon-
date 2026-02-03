DriftCoach 是一个 基于真实赛事事件数据的可解释比赛分析系统，支持自然语言提问，在证据不足时明确告知边界，而不是胡乱生成结论。

## 1️⃣ What is DriftCoach
DriftCoach 提供 evidence-based、explainable 的比赛解析，通过 natural language query 识别分析意图，围绕真实事件给出结论。它在每一步都对证据做校验；当证据 partial / insufficient 时，会主动降级或拒绝，而不是“猜”。

## 2️⃣ What Problems It Solves
| 传统方式 | DriftCoach |
| --- | --- |
| 只能看统计 | 基于 round / event |
| 结果不可解释 | 每条结论有依据 |
| 数据不全就崩 | 自动降级 + 说明原因 |
| 固定视角 | 自然语言驱动 |

## 3️⃣ Core Capabilities（能力边界）
✅ 已支持（真实能力）
- 比赛关键反转（TURNING_POINT）
- 风险走势 / 稳定性分析
- 阶段对比（上半场 vs 下半场）
- 地图 / 经济 / 决策类问题（在事件存在时）

❌ 明确不支持 / 有条件支持
- 单个选手但 series 中无 player 映射
- 缺失胜负 / 比分字段的确定性结论
- 无任何事件支撑的推断

## 4️⃣ How Natural Language Works
User Question
	↓
Intent Detection
	↓
Required Facts Resolution
	↓
Event / File Download (if needed)
	↓
Evidence Gate
	↓
Analysis States + Explanation

结果状态
- ✅ Sufficient Evidence → 正常结论
- ⚠️ Partial Evidence → 降级结论 + 说明
- ❌ Insufficient Evidence → 明确拒绝

## 5️⃣ Why You See “Context Only”
CONTEXT_ONLY 表示只返回上下文而不下结论。触发原因包括数据字段缺失、series pool 为 0、intent 过泛。它不是错误，而是对证据不足的保护：当前数据不足以支撑一个可验证的分析结论。

## 6️⃣ Example Questions
✅ 稳定产出结论
- “这场比赛有没有关键反转？”
- “风险是在什么时候显著上升的？”

⚠️ 可能降级
- “这场比赛整体稳不稳？”
- “经济决策是否合理？”

❌ 会被拒绝
- “OXy 这场打得怎么样？”（无该选手）
- “这场比赛是不是打得很烂？”（无明确意图）

## 7️⃣ Current Status
- ✅ 系统主流程已跑通
- ✅ 自然语言 → 分析 → 前端展示闭环完成
- ⚠️ 部分分析仍依赖 CONTEXT_ONLY 填充规则
- ⚠️ GRID API 速率限制会触发降级

## 8️⃣ Who This Is For
- Hackathon judges
- Analysts / coaches
- Product / research demos

不面向：
- ❌ 博彩工具
- ❌ 即时战术助手

## 9️⃣ License
- MIT License. See `LICENSE` for details.
