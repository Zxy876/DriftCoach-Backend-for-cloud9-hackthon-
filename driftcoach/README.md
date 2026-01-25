# DriftCoach Backend

A post-hoc decision analysis backend skeleton built to operate on GRID-aligned structured data (or mocks).

## Out of Scope (frozen)
- ❌ Chat/agent functionality or prompt-based planners
- ❌ Free-form natural language Q&A
- ❌ LLM-driven decision-making or analysis logic
- ❌ Real-time match guidance or live shot-calling
- ❌ End-to-end ML decision models
- ❌ Direct GRID API integration in this phase (mock-only inputs)

## Frontend Guardrails (frozen)
- Role：Decision Review Interface only；消费后端已生成的 `Insight` / `ReviewAgendaItem` / `WhatIfOutcome`，不做分析、不产出新结论。
- Out of Scope（Frontend）：无聊天/无 Copilot/无自由提问；无“你应该怎么打”类推荐；无实时指挥；不得隐藏 confidence / sample；不得直接展示原始 GRID 数据或中间 State/Transition。
- LLM：仅用于解释层，将现有数值翻译为可理解文本；不得改写或新增数值/结论；必须可开关；失败回退模板文本。

## Integration Freeze (demo-ready)
- Endpoint（frozen）：`GET /api/demo`（无 query/body）。
- Payload：字段与 `frontend/mocks/demo.json` 同构；不得增删字段；不暴露 State/Transition/DerivedFact 细节。
- Backend：FastAPI 仅为输出壳；可直接返回 demo.json；不得新增分析路径或参数。
- Frontend：仅切换数据源（mock/api），UI/顺序/Assumptions/LLM 开关行为不变；无聊天/推荐/实时语义。
- Freeze：通过 DoD 后禁止新增 API、改组件结构或添加功能；仅允许文档/讲稿/Q&A 补充。

## Phase Goal
Deliver a runnable backend skeleton that can:
1. Accept GRID-style structured streams (mock/fixture).
2. Build `State` snapshots and identify decision points via `Transition`.
3. Run explicit, finite `AnalysisMethod`s (rules + light ML) to produce derived facts.
4. Emit three structured outputs: Insights, Review Agenda Items, What-if Outcomes.
5. Maintain auditability: every output must trace back to data and reasoning.

## Directory Layout (frozen)
```
driftcoach/
├── core/
├── analysis/
│   └── methods/
├── ml/
├── outputs/
├── llm/
├── fixtures/
└── main.py
```

## Development Notes
- All analysis functions accept `State` or `list[State]` only.
- Analysis methods are explicitly registered; no dynamic generation.
- LLM is only for rendering structured results into human metaphors; it never sees raw data.
- ML is restricted to StandardScaler + PCA + kNN/cosine for similarity; optional logistic/GBDT for outcome probability.
- When data is insufficient, the system must refuse to output rather than hallucinate.

## Quickstart (mock dry-run)
1. 安装依赖：`pip install -r requirements.txt`
2. 运行：`python3 -m driftcoach.main`
3. 预期：
	- 打印已注册方法及基于 `fixtures/states.json` 的 DerivedFact 结果；当样本不足或缺字段时会显示 `[SKIP]`/`[NO RESULT]`。
	- 基于已生成的 DerivedFact 组装示例输出：`[INSIGHT]`、`[REVIEW]`、`[WHAT-IF]`（结构化）。
	- What-if 概率来自 StateSimilarity 的 Top-K 相似历史状态（按 action 分桶）经验胜率；confidence 由样本量与平均相似度共同决定。
4. 可选解释层：`python3 -m driftcoach.main --explain` 会额外打印 `[EXPLAIN]` 文本，仅对已有输出做数学隐喻解释，不改变任何结论或数值。

## LLM Interpretation Layer（冻结职责）
- 角色：Mathematical Interpreter，仅解释偏离、风险形态、不确定性。
- 输入白名单：Insight / ReviewAgendaItem / WhatIfOutcome（结构化输出对象）。
- 输出约束：不引入新数字、不建议行动、不修改原始对象；解释失败不影响主输出。
- 位置：`llm/interpreter.py`，可通过 `--explain` 触发附加文本打印。
- 解释多样性：使用受控模板与固定种子，保持语气多样但不新增事实。
