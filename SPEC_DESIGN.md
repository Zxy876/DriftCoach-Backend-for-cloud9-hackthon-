# Spec 设计附件：DriftCoach 的"带类型规模"

## 🎯 核心概念

### **从"数量"到"带类型的规模"**

**CLRS 的 n**：问题规模
**DriftCoach 的 n（L3）**：有效的挖掘指令数
**DriftCoach 的 n（L4）**：`|Specs(query)|` × `budget_per_spec`

**关键突破**：
- L3 问题：不同 query 挖掘相同的 facts 池 → `F(X1)=y, F(X2)=y`
- L4 解决：Spec 收缩可见性 → 每个 spec 只看到允许的 facts 子集

---

## 📐 Spec Schema 定义

### **最小四字段 Spec**

```python
@dataclass
class Spec:
    """
    Spec（规格）：定义"算什么、允许缺什么、上界是多少、输出形态是什么"

    核心作用：收缩可见性（search space reduction）
    """

    # 1. Focus: 关心的维度/子空间
    focus: SpecFocus

    # 2. Required evidence: 最小充分证据类型
    required_evidence: RequiredEvidence

    # 3. Budget: 硬上界（per-spec）
    budget: SpecBudget

    # 4. Output contract: 输出形态
    output_contract: OutputContract
```

---

### **字段 1: Focus（规格焦点）**

```python
class SpecFocus(Enum):
    """Spec 关注的维度/子空间"""

    # 6 个 MVP spec
    ECON = "ECON"                    # 经济：强起/保枪/经济崩盘
    RISK = "RISK"                    # 风险：高风险序列/局势波动
    MAP = "MAP"                      # 地图：点位控制/薄弱点
    PLAYER = "PLAYER"                # 球员：选手表现/影响
    SUMMARY = "SUMMARY"              # 总结：全局回顾/总结
    MOMENTUM = "MOMENTUM"            # 动能：势能变化/阶段对比
```

---

### **字段 2: Required Evidence（必需证据）**

```python
@dataclass
class RequiredEvidence:
    """最小充分证据类型 + 允许缺什么"""

    # 必需的证据类型（至少需要一种）
    primary_fact_types: List[str]

    # 可选的证据类型（有更好，没也行）
    optional_fact_types: List[str]

    # 必需的 schema 字段（outcome, teams.score 等）
    required_schema_fields: List[str]

    # 允许缺失的字段
    allowed_missing_fields: List[str]

    # 示例
    #   primary_fact_types = ["HIGH_RISK_SEQUENCE", "ROUND_SWING"]
    #   optional_fact_types = ["ECO_COLLAPSE_SEQUENCE"]
    #   required_schema_fields = []  # 不强制要求 outcome
    #   allowed_missing_fields = ["Series.winner", "teams.score"]
```

---

### **字段 3: Budget（硬上界）**

```python
@dataclass
class SpecBudget:
    """Per-spec 硬上界（防止爆炸）"""

    # Facts 数量限制
    max_facts_total: int = 5          # 总 fact 数量
    max_facts_per_type: int = 3       # 每个 fact 类型数量

    # Events 窗口限制
    max_events_window: Optional[int] = None  # 最多看多少 events

    # Patches 限制
    max_patches: int = 0              # 是否允许补丁（0=不允许）

    # Analysis 方法限制
    max_analysis_methods: int = 2     # 最多运行多少种分析方法

    # 示例
    #   max_facts_total = 5
    #   max_facts_per_type = 3
    #   max_events_window = 1000
    #   max_patches = 0  # 不允许自动补丁
```

---

### **字段 4: Output Contract（输出契约）**

```python
@dataclass
class OutputContract:
    """输出形态：STANDARD/DEGRADED/REJECT 的触发条件"""

    # STANDARD 触发条件
    standard_min_confidence: float = 0.7
    standard_min_facts: int = 2

    # DEGRADED 触发条件
    degraded_max_uncertainty: float = 0.8
    degraded_min_facts: int = 1

    # 必需字段（每种输出形态必须包含）
    required_fields: List[str] = field(default_factory=lambda: [
        "claim", "verdict", "confidence", "support_facts"
    ])

    # 可选字段（有更好）
    optional_fields: List[str] = field(default_factory=lambda: [
        "caveats", "followups", "counter_facts"
    ])

    # 示例
    #   standard_min_confidence = 0.7
    #   degraded_max_uncertainty = 0.8
    #   required_fields = ["claim", "verdict", "confidence", "support_facts"]
```

---

## 🎯 6 个 MVP Spec 定义

### **Spec 1: ECON（经济分析）**

```python
ECON_SPEC = Spec(
    focus=SpecFocus.ECON,

    required_evidence=RequiredEvidence(
        primary_fact_types=[
            "FORCE_BUY_ROUND",         # 强起回合
            "ECO_COLLAPSE_SEQUENCE",   # 经济崩盘
            "ECONOMIC_PATTERN"         # 经济模式
        ],
        optional_fact_types=[
            "FULL_BUY_ROUND",          # 完整买
            "ROUND_SWING"              # 局势反转（可选）
        ],
        required_schema_fields=[],     # 经济分析不强制要求 outcome
        allowed_missing_fields=[
            "Series.winner",
            "teams.score",
            "result"
        ]
    ),

    budget=SpecBudget(
        max_facts_total=5,
        max_facts_per_type=3,
        max_events_window=500,         # 只看最近 500 events
        max_patches=0,                 # 不允许补丁
        max_analysis_methods=2
    ),

    output_contract=OutputContract(
        standard_min_confidence=0.75,
        standard_min_facts=2,
        degraded_max_uncertainty=0.7,
        degraded_min_facts=1
    )
)

# 映射的 intents
ECON_SPEC.intents = [
    "ECONOMIC_COUNTERFACTUAL",
    "ECONOMIC_FAILURE",
    "TACTICAL_EVAL"  # 部分战术评估与经济相关
]
```

---

### **Spec 2: RISK（风险评估）**

```python
RISK_SPEC = Spec(
    focus=SpecFocus.RISK,

    required_evidence=RequiredEvidence(
        primary_fact_types=[
            "HIGH_RISK_SEQUENCE",       # 高风险序列
            "ROUND_SWING"               # 局势反转
        ],
        optional_fact_types=[
            "ECO_COLLAPSE_SEQUENCE",    # 经济崩盘（可选）
            "OBJECTIVE_LOSS_CHAIN"      # 目标丢失链（可选）
        ],
        required_schema_fields=[],
        allowed_missing_fields=[
            "Series.winner",
            "teams.score"
        ]
    ),

    budget=SpecBudget(
        max_facts_total=5,
        max_facts_per_type=3,
        max_events_window=1000,
        max_patches=0,
        max_analysis_methods=2
    ),

    output_contract=OutputContract(
        standard_min_confidence=0.7,
        standard_min_facts=2,
        degraded_max_uncertainty=0.6,  # 风险评估不确定性容忍度低
        degraded_min_facts=1
    )
)

RISK_SPEC.intents = [
    "RISK_ASSESSMENT",
    "STABILITY_ANALYSIS",
    "COLLAPSE_ONSET_ANALYSIS"
]
```

---

### **Spec 3: MAP（地图分析）**

```python
MAP_SPEC = Spec(
    focus=SpecFocus.MAP,

    required_evidence=RequiredEvidence(
        primary_fact_types=[
            "OBJECTIVE_LOSS_CHAIN",     # 目标丢失链
            "HIGH_RISK_SEQUENCE"        # 高风险序列（地图相关）
        ],
        optional_fact_types=[
            "ROUND_SWING",              # 局势反转（可选）
        ],
        required_schema_fields=[],
        allowed_missing_fields=[
            "Series.winner",
            "teams.score"
        ]
    ),

    budget=SpecBudget(
        max_facts_total=4,
        max_facts_per_type=2,
        max_events_window=800,
        max_patches=0,
        max_analysis_methods=2
    ),

    output_contract=OutputContract(
        standard_min_confidence=0.7,
        standard_min_facts=2,
        degraded_max_uncertainty=0.7,
        degraded_min_facts=1
    )
)

MAP_SPEC.intents = [
    "MAP_WEAK_POINT",
    "EXECUTION_VS_STRATEGY"  # 部分执行vs策略与地图相关
]
```

---

### **Spec 4: PLAYER（球员分析）**

```python
PLAYER_SPEC = Spec(
    focus=SpecFocus.PLAYER,

    required_evidence=RequiredEvidence(
        primary_fact_types=[
            "PLAYER_IMPACT_STAT",       # 球员影响统计
            "ROUND_SWING"               # 局势反转（看球员贡献）
        ],
        optional_fact_types=[
            "HIGH_RISK_SEQUENCE"        # 高风险序列（看球员失误）
        ],
        required_schema_fields=[],
        allowed_missing_fields=[
            "Series.winner",
            "teams.score"
        ]
    ),

    budget=SpecBudget(
        max_facts_total=4,
        max_facts_per_type=2,
        max_events_window=1000,
        max_patches=0,
        max_analysis_methods=2
    ),

    output_contract=OutputContract(
        standard_min_confidence=0.7,
        standard_min_facts=2,
        degraded_max_uncertainty=0.75,  # 球员分析允许更高不确定性
        degraded_min_facts=1
    )
)

PLAYER_SPEC.intents = [
    "PLAYER_REVIEW",
    "COUNTERFACTUAL_PLAYER_IMPACT"
]
```

---

### **Spec 5: SUMMARY（总结分析）**

```python
SUMMARY_SPEC = Spec(
    focus=SpecFocus.SUMMARY,

    required_evidence=RequiredEvidence(
        primary_fact_types=[
            "CONTEXT_ONLY"              # 上下文即可
        ],
        optional_fact_types=[
            "ROUND_SWING",              # 任何其他 facts 都是加分
            "HIGH_RISK_SEQUENCE",
            "ECO_COLLAPSE_SEQUENCE"
        ],
        required_schema_fields=[],
        allowed_missing_fields=[
            "Series.winner",
            "teams.score",
            "result"
        ]
    ),

    budget=SpecBudget(
        max_facts_total=3,             # 总结只需要少量 facts
        max_facts_per_type=1,
        max_events_window=2000,         # 可以看更多 events
        max_patches=0,
        max_analysis_methods=1
    ),

    output_contract=OutputContract(
        standard_min_confidence=0.6,    # 总结允许较低置信度
        standard_min_facts=1,
        degraded_max_uncertainty=0.8,    # 高不确定性容忍
        degraded_min_facts=1
    )
)

SUMMARY_SPEC.intents = [
    "MATCH_SUMMARY",
    "MATCH_REVIEW"
]
```

---

### **Spec 6: MOMENTUM（动能分析）**

```python
MOMENTUM_SPEC = Spec(
    focus=SpecFocus.MOMENTUM,

    required_evidence=RequiredEvidence(
        primary_fact_types=[
            "ROUND_SWING"               # 局势反转是核心
        ],
        optional_fact_types=[
            "HIGH_RISK_SEQUENCE",        # 高风险序列（可选）
        ],
        required_schema_fields=[],
        allowed_missing_fields=[
            "Series.winner",
            "teams.score"
        ]
    ),

    budget=SpecBudget(
        max_facts_total=5,
        max_facts_per_type=3,
        max_events_window=1500,         # 动能分析需要看更多事件
        max_patches=0,
        max_analysis_methods=2
    ),

    output_contract=OutputContract(
        standard_min_confidence=0.7,
        standard_min_facts=2,
        degraded_max_uncertainty=0.7,
        degraded_min_facts=1
    )
)

MOMENTUM_SPEC.intents = [
    "MOMENTUM_ANALYSIS",
    "PHASE_COMPARISON"
]
```

---

## 🔄 Intent → Spec 映射表

| Intent | Spec | 原因 |
|--------|------|------|
| **RISK_ASSESSMENT** | RISK | 核心风险分析 |
| **STABILITY_ANALYSIS** | RISK | 稳定性 = 风险的反面 |
| **COLLAPSE_ONSET_ANALYSIS** | RISK | 崩盘起点 = 风险事件 |
| **ECONOMIC_COUNTERFACTUAL** | ECON | 经济反事实 |
| **ECONOMIC_FAILURE** | ECON | 经济失败 |
| **TACTICAL_EVAL** | ECON | 部分战术评估与经济相关 |
| **MAP_WEAK_POINT** | MAP | 地图薄弱点 |
| **EXECUTION_VS_STRATEGY** | MAP | 执行vs策略常涉及点位 |
| **PLAYER_REVIEW** | PLAYER | 选手回顾 |
| **COUNTERFACTUAL_PLAYER_IMPACT** | PLAYER | 选手影响反事实 |
| **MATCH_SUMMARY** | SUMMARY | 比赛总结 |
| **MATCH_REVIEW** | SUMMARY | 比赛回顾（orchestration） |
| **MOMENTUM_ANALYSIS** | MOMENTUM | 动能分析 |
| **PHASE_COMPARISON** | MOMENTUM | 阶段对比 = 动能变化 |

---

## 🔬 Spec 收缩可见性的原理

### **之前（L3）：全局 Facts 池**

```python
# 所有 query 都看到相同的 facts
query_1 = "这是不是一场高风险对局？"    → 看所有 facts
query_2 = "经济决策有什么问题？"        → 看所有 facts
query_3 = "地图哪个点位薄弱？"          → 看所有 facts

# 结果：F(X1) ≈ F(X2) ≈ F(X3) （因为输入空间相同）
```

---

### **之后（L4）：Spec 收缩的 Facts 子集**

```python
# 每个 spec 只看到允许的 facts
RISK_SPEC.allowed_facts = {
    "HIGH_RISK_SEQUENCE",
    "ROUND_SWING"
    # 不包含 ECO_COLLAPSE_SEQUENCE, PLAYER_IMPACT_STAT 等
}

ECON_SPEC.allowed_facts = {
    "FORCE_BUY_ROUND",
    "ECO_COLLAPSE_SEQUENCE",
    "ECONOMIC_PATTERN"
    # 不包含 HIGH_RISK_SEQUENCE, PLAYER_IMPACT_STAT 等
}

# 结果：F_RISK(X1) ≠ F_ECON(X2) （因为输入空间不同）
```

---

## 🔗 与现有系统的对齐

### **QuestionState / ScopeReducer 如何对齐到 Spec**

**当前系统**：
```python
class QuestionState:
    intent: str          # 如 "RISK_ASSESSMENT"
    scope: Optional[str]  # 如 None, "SUMMARY"
    # ...
```

**对齐方案**：
```python
class QuestionState:
    intent: str
    spec: Spec            # 新增：从 intent 推导出的 spec

    @property
    def spec(self) -> Spec:
        """从 intent 推导 spec"""
        return INTENT_TO_SPEC_MAP.get(self.intent, SUMMARY_SPEC)
```

---

### **DerivedFindings Pool 如何尊重 Spec**

**当前系统**：
```python
# DerivedFindings 存储时带 intent
finding = DerivedFinding(
    intent="RISK_ASSESSMENT",
    fact_type="HIGH_RISK_SEQUENCE",
    # ...
)
```

**对齐方案**：
```python
# DerivedFindings 存储时带 spec
finding = DerivedFinding(
    spec_focus="RISK",             # 新增：spec focus
    intent="RISK_ASSESSMENT",
    fact_type="HIGH_RISK_SEQUENCE",
    # ...
)

# 查询时只检索该 spec 允许的 facts
def get_facts_for_spec(spec: Spec, all_facts: List[Fact]):
    """只返回 spec 允许的 facts"""
    allowed_types = spec.required_evidence.primary_fact_types
    return [f for f in all_facts if f.fact_type in allowed_types]
```

---

## 📊 Spec 的 Master Theorem 版本

```
T(query) = Σ_{spec ∈ Specs(query)} T(spec) + O(1)_{route+combine+persist}

其中：
- |Specs(query)| ≤ k（bounds.max_sub_intents = 3）
- T(spec) 的输入空间被 spec 收缩：
  · 只有 spec.allowed_fact_types 的 facts
  · 只有 spec.max_events_window 的 events
  · 只有 spec.max_facts_total 的 facts
- O(1) 来自：
  · spec_recognition（O(1) 查表）
  · routing（O(1) handler 路由）
  · combine（DecisionMapper / Narrative，常数时间）
  · persistence（MemoryStore 写入，常数时间）
```

---

## ✅ 实施优先级

### **Phase 1: Spec Schema（立即实施）**

1. ✅ 定义 `Spec` dataclass
2. ✅ 定义 6 个 MVP spec
3. ✅ 创建 `INTENT_TO_SPEC_MAP`

### **Phase 2: Spec Recognizer（下一步）**

1. 创建 `SpecRecognizer` 模块：
   ```python
   def recognize_spec(query: str, intent: str) -> Spec:
       """从 query 和 intent 推导出 spec"""
       return INTENT_TO_SPEC_MAP.get(intent, SUMMARY_SPEC)
   ```

2. 集成到 mining pipeline：
   ```python
   spec = recognize_spec(query, intent)
   facts = get_facts_for_spec(spec, all_facts)  # 只看允许的 facts
   ```

### **Phase 3: Per-spec Budget（后续）**

1. `mining_plan_generator` 根据 spec 生成计划：
   ```python
   plan = plan_for(spec)  # 不是全局模板
   ```

2. `DerivedFindingBuilder` 只消费 spec 允许的事实：
   ```python
   findings = build_facts_for_spec(spec, evidence)
   ```

---

## 🎯 预期效果

### **解决"不同问题输出一样"**

| Query | Spec（L4） | 可见 Facts | 输出 |
|-------|-----------|-----------|------|
| "这是不是一场高风险对局？" | RISK | HIGH_RISK_SEQUENCE, ROUND_SWING | "这是一场高风险对局" |
| "经济决策有什么问题？" | ECON | FORCE_BUY_ROUND, ECO_COLLAPSE_SEQUENCE | "强起决策放大了风险" |
| "地图哪个点位薄弱？" | MAP | OBJECTIVE_LOSS_CHAIN, HIGH_RISK_SEQUENCE | "R15-A 点位控制薄弱" |

**之前（L3）**：三个 query 输出相似（都在全局 facts 池捞）
**之后（L4）**：三个 query 输出不同（spec 收缩了可见性）

---

## 📝 总结

**Spec 的本质**：
- 不是"接受/拒绝"（那是 GateOutcome）
- 而是"算什么、允许缺什么、上界是多少、输出形态是什么"

**Spec 的作用**：
- 收缩可见性（search space reduction）
- 让不同 query 看到不同的 facts 子集
- 解决 `F(X1)=y, F(X2)=y` 的问题

**下一步**：
- 实现 `SpecRecognizer`
- 集成到 mining/analysis pipeline
- 让所有模块尊重 spec 的约束
