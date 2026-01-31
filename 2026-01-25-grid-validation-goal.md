 
⸻

DriftCoach Frontend — LLM 语境化解释层

Engineering Goal（v1.0.1 · 可执行 · 冻结版 · GPT-4o）

适用范围

React / Vite 前端，消费 GET /api/demo 固定契约（Mock / GRID 两种数据源）。
通过 renderMode: off | template | llm-contextual 的前端 LLM Wrapper，将后端结构化分析结果转为符合具体游戏语境的自然语言解释文本。
LLM 供应商：OpenAI GPT-4o（冻结）。

⸻

0. 项目定位（冻结 · 不可修改）

0.1 系统角色定义
	•	前端 LLM 角色：语境解释器（Contextual Interpreter）
	•	❌ 非分析器
	•	❌ 非决策器
	•	❌ 非 Agent
	•	❌ 非聊天系统
	•	核心职责：将后端已产出的 Insight / ReviewAgendaItem / WhatIfOutcome
→ 转换为符合特定游戏分析文化的自然语言表述（教练/分析师口吻）。

0.2 真相源（Truth Source）
	•	唯一事实来源：后端返回的结构化结果（HTTP 响应 JSON）。
	•	前端 LLM 不得直接或间接接触：
	•	GRID 原始数据
	•	State / Transition / 原始统计明细
	•	前端 LLM 不得生成：新事实、新数值、新概率、新因果。

⸻

1. 目标（Goal）

在不修改后端、不扩展 API、不接触 GRID 原始数据的前提下，实现前端 LLM 语境解释层，使演示中：
	•	输出“像教练/分析师/复盘人员会说的话”，而不是模板口号；
	•	所有结论、数值、信号强度可回溯；
	•	LLM 关闭或失败时，仍可用 template 稳定演示；
	•	支持跨游戏扩展（VALORANT / LoL / future）。

⸻

2. 交付物（Deliverables）

2.1 核心代码（必须）

新增/修改以下文件（路径冻结）：
	•	frontend/src/llm/renderer.ts
	•	frontend/src/llm/prompt.ts（冻结 Prompt 资产落地处）
	•	frontend/src/llm/client.ts（OpenAI 调用封装，含超时/失败回退）
	•	frontend/src/llm/intents.ts（NarrativeIntent 类型与映射规则）
	•	frontend/src/llm/profiles.ts（Game Profile 资产：VALORANT/LoL）
	•	frontend/src/llm/templates.ts（template 解释文本）
	•	frontend/src/llm/trace.ts（trace_id、溯源字段引用、debug 辅助）
	•	frontend/src/config.ts（renderMode、gameId、API base 等配置）
	•	frontend/src/App.tsx（接线：enrich explanation）

2.2 渲染模式（冻结）

renderMode 三态必须实现：
	•	off：不输出解释文本
	•	template：纯模板解释（零 LLM）
	•	llm-contextual：调用 GPT-4o，失败/超时自动回退 template

2.3 语境资产（必须落地）
	•	Narrative Intent 枚举（见第 4 节）
	•	Context Lexicon / Game Profile（见附件 A）
	•	资产形式：TS 常量（推荐）或 JSON（可选），但必须可版本化审查。

2.4 文档（必须）
	•	frontend/README.md 或顶层 README 增补：
	•	“前端 LLM = 语境解释器”
	•	Scope Guard（越界警戒）
	•	三种 renderMode 说明
	•	环境变量与运行方式

⸻

3. 工作范围（Scope）

3.1 输入（严格受限）

前端 LLM 的输入只允许包含：
	•	Insight / ReviewAgendaItem / WhatIfOutcome（来自 GET /api/demo）
	•	可选：后端提供的“数学隐喻标签”（如 stable/volatile/weak-signal）
不得添加任何来自 State/GRID 的字段。

3.2 输出（严格受限）
	•	仅输出解释文本（string），不改写数值字段。
	•	文本不得出现：
	•	新概率、新数值、新因果
	•	“应该/建议/必须/最优”等指令性措辞
	•	任何“战术建议 / 操作建议 / 时间点指挥”语义

⸻

4. Narrative Intent（核心概念 · 必须实现）

4.1 Intent 定义（冻结）

export type NarrativeIntent =
  | "RESOURCE_SNOWBALL"
  | "OPENING_PHASE_INSTABILITY"
  | "MID_GAME_TIMING_PRESSURE"
  | "OBJECTIVE_TRADE_INEFFICIENCY"
  | "HIGH_VARIANCE_PATTERN"
  | "WEAK_SIGNAL_LOW_CONFIDENCE";

4.2 Intent 来源（确定性映射，必须可审计）
	•	Intent 由前端根据后端字段确定性生成（无 LLM 参与）。
	•	规则必须写进代码（intents.ts）并可单元测试。
	•	最小规则集（示例，允许调整但需测试覆盖）：
	•	confidence < 0.4 → WEAK_SIGNAL_LOW_CONFIDENCE
	•	observed - baseline <= -0.2 → 负向偏离（可用于 snowball/instability 分流）
	•	What-if 中 max(action.winProb) - min(action.winProb) >= 0.2 → 倾向“可分辨差异”（可用于 volatility/pressure 的语气）

备注：如果后端当前不提供 variance / pistol / objective-orb 等字段，前端不得凭空推断；Intent 必须只由现有字段触发。

⸻

5. Game Profile（语境角色化的根源）

5.1 定义（冻结）

export type GameProfile = {
  id: "valorant" | "lol";
  temporalModel: "round-based" | "continuous";
  resourceModel: "hard-econ" | "soft-econ";
  analysisCulture: {
    primaryFocus: string[];
    typicalLanguageTone: string;
  };
  intentFraming: Record<NarrativeIntent, {
    framing: string[];
    explanationBias: string;
  }>;
};

5.2 Game 选择方式（冻结）
	•	gameId 来自：
	1.	context.gameId（若后端提供）
	2.	否则使用前端配置 DEFAULT_GAME_ID
	•	未识别 gameId → fallback 到 valorant（或显式 unknown，但必须有 fallback）。

⸻

6. Template 与 LLM 的关系（关键）

6.1 Template（基线保障）
	•	对每个 NarrativeIntent × GameProfile：至少 2 条模板（防止单句重复）。
	•	模板必须：
	•	引用 value/baseline/sample_size/confidence（原值）
	•	对低置信度自动加不确定性表述
	•	不得含建议语气

6.2 LLM（GPT-4o）职责
	•	在不改变语义、不新增事实的前提下：
	•	提升自然度
	•	提升角色化（Spotify DJ 式“有口吻但不加事实”）
	•	避免重复措辞（同一 Intent 不要反复同一个名词短语）

⸻

7. Scope Guard（必须写入代码注释 + README）
	•	❌ 读取/拼接 GRID 原始数据
	•	❌ 修改任何数值、概率、baseline、confidence
	•	❌ 输出战术建议/操作建议/时间点指挥
	•	❌ 聊天式自由输入/多轮对话
	•	❌ 通过 LLM 推导“应该怎么打”

⸻

8. 技术约束与回退

8.1 OpenAI 调用（冻结）
	•	模型：gpt-4o
	•	Key：VITE_OPENAI_API_KEY（或 OPENAI_API_KEY，二选一但需写死并文档化）
	•	超时：例如 3s–5s（由实现定，但必须存在）
	•	失败/超时：自动回退 template，页面仍能完整演示

8.2 可追溯性（必须）

每条 explanation 必须带上 trace 信息（不一定展示给用户，但需可 debug）：
	•	trace_id（UUID）
	•	intent
	•	game_profile
	•	source_fields（例如 ["insight.confidence","derived_fact.value","derived_fact.baseline"]）

⸻

9. 验收标准（DoD）
	•	template 与 llm-contextual 均能输出游戏语境解释，且不局限于“滚雪球”；
	•	off 模式不展示解释文本但页面不崩；
	•	关闭 LLM 后解释仍成立（template 可演示）；
	•	任意一句话可追溯到输入字段（通过 trace 或 debug 面板/console）；
	•	UI 无聊天入口、无建议语义；
	•	README/注释写明边界；
	•	最少 6 组 snapshot 测试覆盖：2 游戏 × 3 intent（至少）。

⸻

10. Fail Fast（快速失败判定）
	•	LLM 输出新概率/新因果/新事实
	•	出现 “should/must/need/optimal/建议/应该” 等建议语义
	•	无法解释该文本来自哪些字段（trace 缺失）
	•	LLM 失败导致页面空白/卡死/崩溃

⸻

11. 里程碑（Milestones）
	•	M1：落地 template 模式 + Intent + Game Profile（含测试）
	•	M2：接入 GPT-4o，完成 llm-contextual + 回退（含测试与超时）
	•	M3：README/注释/演示脚本完成，冻结

⸻

12. 与后端 LLM 的关系（冻结共识）
	•	后端 LLM：数学/统计 → 抽象隐喻（稳态/波动/信号强度）
	•	前端 LLM（GPT-4o）：隐喻 + Intent + Game Profile → 游戏语境语言
	•	二者不共享上下文、不互相推理；前端只消费后端输出。

⸻

附件 A

DriftCoach — Game Profile 初稿（VALORANT / League of Legends）

用途说明（给开发看的）
Game Profile 不是词表，不是模板集合，而是：
“在这个游戏里，教练/分析师习惯用什么角度理解与讲述同一类事实”

它是前端 LLM 语境化解释层的第二真相源（第一真相源仍是后端结构化分析结果）。

⸻

A.1 Game Profile 总体结构（冻结）

export type GameProfile = {
  id: "valorant" | "lol";
  temporalModel: "round-based" | "continuous";
  resourceModel: "hard-econ" | "soft-econ";
  analysisCulture: AnalysisCulture;
  intentFraming: Record<NarrativeIntent, IntentFraming>;
};


⸻

A.2 NarrativeIntent（跨游戏通用，冻结）

export type NarrativeIntent =
  | "RESOURCE_SNOWBALL"
  | "OPENING_PHASE_INSTABILITY"
  | "MID_GAME_TIMING_PRESSURE"
  | "OBJECTIVE_TRADE_INEFFICIENCY"
  | "HIGH_VARIANCE_PATTERN"
  | "WEAK_SIGNAL_LOW_CONFIDENCE";


⸻

A.3 VALORANT — Game Profile（v1.0）

export const VALORANT_PROFILE: GameProfile = {
  id: "valorant",
  temporalModel: "round-based",
  resourceModel: "hard-econ",

  analysisCulture: {
    primaryFocus: [
      "round economy",
      "opening duels",
      "tempo control",
      "utility trade",
      "man-advantage conversion"
    ],
    typicalLanguageTone: "tactical, round-centric, consequence-driven"
  },

  intentFraming: {
    RESOURCE_SNOWBALL: {
      framing: [
        "经济滚雪球",
        "回合失败后的连锁反应",
        "无法进入完整装备回合"
      ],
      explanationBias: "round-to-round consequence"
    },

    OPENING_PHASE_INSTABILITY: {
      framing: [
        "手枪局丢失",
        "开局节奏不稳定",
        "首轮决斗成功率偏低"
      ],
      explanationBias: "early-round leverage"
    },

    MID_GAME_TIMING_PRESSURE: {
      framing: [
        "中期决策时间偏晚",
        "进攻启动犹豫",
        "被迫在低时间窗口强行执行"
      ],
      explanationBias: "clock pressure"
    },

    OBJECTIVE_TRADE_INEFFICIENCY: {
      framing: [
        "资源交换不理想",
        "地图控制让渡",
        "未能形成有效 trade"
      ],
      explanationBias: "map control vs value"
    },

    HIGH_VARIANCE_PATTERN: {
      framing: [
        "表现波动较大",
        "boom-or-bust 回合结构",
        "缺乏稳定转化"
      ],
      explanationBias: "round volatility"
    },

    WEAK_SIGNAL_LOW_CONFIDENCE: {
      framing: [
        "样本量有限",
        "信号偏弱",
        "暂不具备强结论"
      ],
      explanationBias: "analyst caution"
    }
  }
};


⸻

A.4 League of Legends — Game Profile（v1.0）

export const LOL_PROFILE: GameProfile = {
  id: "lol",
  temporalModel: "continuous",
  resourceModel: "soft-econ",

  analysisCulture: {
    primaryFocus: [
      "early pathing",
      "objective control",
      "gold distribution",
      "map pressure",
      "scaling vs tempo"
    ],
    typicalLanguageTone: "macro-oriented, flow-based, pressure-aware"
  },

  intentFraming: {
    RESOURCE_SNOWBALL: {
      framing: [
        "经济差距逐步放大",
        "滚雪球效应",
        "资源倾斜导致节奏失衡"
      ],
      explanationBias: "gold & tempo accumulation"
    },

    OPENING_PHASE_INSTABILITY: {
      framing: [
        "前期节奏受阻",
        "早期决策效率偏低",
        "未能建立优势起点"
      ],
      explanationBias: "early game leverage"
    },

    MID_GAME_TIMING_PRESSURE: {
      framing: [
        "中期决策窗口把握不足",
        "资源转换效率偏低",
        "关键时间点选择保守"
      ],
      explanationBias: "mid-game window"
    },

    OBJECTIVE_TRADE_INEFFICIENCY: {
      framing: [
        "目标资源控制不理想",
        "换资源时机不佳",
        "地图收益转化不足"
      ],
      explanationBias: "objective economy"
    },

    HIGH_VARIANCE_PATTERN: {
      framing: [
        "状态起伏明显",
        "依赖个别回合/团战",
        "稳定性不足"
      ],
      explanationBias: "performance consistency"
    },

    WEAK_SIGNAL_LOW_CONFIDENCE: {
      framing: [
        "样本有限",
        "趋势尚不稳定",
        "需要更多对局验证"
      ],
      explanationBias: "statistical caution"
    }
  }
};


⸻
附件 B

DriftCoach — GPT-4o 前端 LLM 最终 Prompt（冻结版）

重要说明（必须写进代码注释）
本 Prompt 为 冻结资产。
修改 Prompt ≈ 修改系统语义，必须走工程评审。

⸻

B.1 System Prompt（固定）

You are an esports performance analyst acting as a post-match interpreter.

Your role is NOT to analyze new data, NOT to infer new causes, and NOT to give advice.

You only translate existing, structured analytical results into game-contextual language
that a professional coach or analyst would naturally use.

You must strictly obey the following rules:

- Do NOT introduce new statistics, probabilities, or causes.
- Do NOT modify or reinterpret any numeric values.
- Do NOT give recommendations, suggestions, or commands.
- Do NOT use words like "should", "must", "need to", or "optimal".

If the signal is weak or the sample size is small, you must explicitly express uncertainty.

Your output must be explainable and traceable to the given inputs.


⸻

B.2 User Prompt（动态构造，模板）

Game: {{GAME_ID}}
Game Profile: {{GAME_PROFILE_ID}}

Narrative Intent:
{{NARRATIVE_INTENT}}

Structured Facts (read-only):
{{STRUCTURED_FACTS_JSON}}

Statistical Context:
- baseline: {{BASELINE}}
- observed value: {{VALUE}}
- sample size: {{SAMPLE_SIZE}}
- confidence: {{CONFIDENCE}}

Optional Mathematical Metaphor:
{{MATH_METAPHOR_OR_NONE}}

Task:
Write a short, professional explanation in the language and tone commonly used by coaches
in this game.

The explanation should:
- Stay faithful to the facts above
- Use appropriate game-context terminology
- Reflect uncertainty if confidence or sample size is low

Do NOT add new conclusions or advice.


⸻

B.3 合法输出示例（VALORANT）

“在当前对局中，该选手在非交换阵亡情况下的回合胜率明显低于个人基线。这类失误在回合制结构中往往会迅速放大经济压力，不过由于样本量有限，目前仍更像是阶段性波动，而非稳定趋势。”

✔ 无新事实
✔ 有教练语境
✔ 明确不确定性

⸻

B.4 合法输出示例（LoL）

“数据显示，这名选手在前期参与上路的决策效率低于其常态水平，导致资源转化节奏偏慢。虽然这一模式在当前样本中较为明显，但由于对局数量有限，仍需结合更多比赛判断其长期影响。”

✔ 无建议
✔ 无新因果
✔ 完全可回溯
补充一条必须加的约束（避免“滚雪球”重复）：
	•	“Avoid repeating the same key noun phrase across outputs when possible; vary phrasing while preserving meaning.”

⸻
 