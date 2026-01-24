# DriftCoach Backend — Engineering Goal (2026-01-24)

## Objective
在不接入真实 GRID API 的前提下，交付一个可运行的后端分析骨架，可通过 mock/fixture 流程完成：State 构建 → Transition 识别 → AnalysisMethod 触发 → 生成三类结构化输出（Insight / Review Agenda / What-if）。

## Scope & Guardrails
- 输入仅限 GRID 对齐的结构化数据（mock/fixture）；禁止自由问答与实时指导。
- 分析方法为显式有限集合；拒绝动态生成或 LLM 介入分析逻辑。
- LLM 仅用于渲染已生成的结构化结果，不接触原始数据。
- ML 仅限 StandardScaler + PCA + kNN/cosine（必做），可选 Logistic/GBDT 概率估计；禁止深度学习/强化学习。

## Deliverables (DoD-aligned)
- `core/`: `State`, `Action` 枚举（SAVE/RETAKE/FORCE/ECO/CONTEST/TRADE）、`Transition`、`DerivedFact` 基类。
- `analysis/`: Registry + Trigger 引擎；3 个方法 stub（free_death_impact, econ_cascade, objective_fail）。
- `outputs/`: Insight / ReviewAgendaItem / WhatIfOutcome 结构。
- `ml/`: StateSimilarity (Scaler+PCA+kNN/cosine)；OutcomeModel stub（LogReg）。
- `llm/renderer.py`: 仅声明渲染接口。
- `fixtures/`: GRID 对齐的示例占位文件。
- `README`: Out-of-Scope 声明与目录冻结。
- `main.py`: 可运行，能注册并列出分析方法。

## Milestones & Checks
1) **工程约束冻结**：README 写明 Out-of-Scope；目录结构与约束落地。
2) **核心数据模型**：State/Action/Transition/DerivedFact 定义完备；分析输入仅接收 State 列表。
3) **分析运行时**：Registry+Trigger 可用，3 个方法可注册并通过样本量校验。
4) **输出结构**：三类输出 dataclass 就绪，可被后续渲染。
5) **ML 受限实现**：StateSimilarity 可 fit/query；OutcomeModel stub 可 fit/predict_prob。
6) **端到端烟测**：从 fixture 读取 → 构造 State → 注册方法 → 运行触发检查 → 输出占位结构。

## Acceptance Criteria
- 运行 `python driftcoach/main.py` 可看到注册的 analysis methods 列表。
- 任意分析方法在数据不足时返回“不符合触发条件”而非输出结果（Trigger 层负责判定）。
- 输出结构仅包含结构化字段，不生成自然语言。
- 代码中无 agent/prompt/即兴分析逻辑；LLM 仅出现在 renderer 接口。
