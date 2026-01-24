# DriftCoach Backend

A post-hoc decision analysis backend skeleton built to operate on GRID-aligned structured data (or mocks).

## Out of Scope (frozen)
- ❌ Chat/agent functionality or prompt-based planners
- ❌ Free-form natural language Q&A
- ❌ LLM-driven decision-making or analysis logic
- ❌ Real-time match guidance or live shot-calling
- ❌ End-to-end ML decision models
- ❌ Direct GRID API integration in this phase (mock-only inputs)

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
	- 基于已生成的 DerivedFact 组装示例输出：`[INSIGHT]`、`[REVIEW]`、`[WHAT-IF]`（仅结构化占位，无自然语言渲染）。
