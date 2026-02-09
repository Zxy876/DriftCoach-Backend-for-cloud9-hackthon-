# Spec 实施总结：解决"不同问题输出一样"

## 🎯 问题诊断

### **L3 的核心问题**：`F(X1)=y, F(X2)=y`

```python
# 之前（L3）：所有 query 都看到相同的 facts 池
query_1 = "这是不是一场高风险对局？"
    → 看所有 facts → 返回 y

query_2 = "经济决策有什么问题？"
    → 看所有 facts → 返回 y（和 query_1 几乎一样）

query_3 = "地图哪个点位薄弱？"
    → 看所有 facts → 返回 y（和 query_1, query_2 几乎一样）
```

**根本原因**：
- 没有 Spec（规格）
- 所有 query 都在全局 facts 池里捞
- Input space 相同 → Output 相同

---

## 🔧 Spec 解决方案

### **L4：Spec 收缩可见性**

```python
# 之后（L4）：每个 spec 只看到允许的 facts 子集

RISK_SPEC.allowed_fact_types = {
    "HIGH_RISK_SEQUENCE",
    "ROUND_SWING",
    "ECO_COLLAPSE_SEQUENCE"  # 可选
}

ECON_SPEC.allowed_fact_types = {
    "FORCE_BUY_ROUND",
    "ECO_COLLAPSE_SEQUENCE",
    "ECONOMIC_PATTERN"
}

# 现在：
query_1 (RISK_ASSESSMENT)
    → 只看 RISK 允许的 facts → 返回 y1

query_2 (ECONOMIC_COUNTERFACTUAL)
    → 只看 ECON 允许的 facts → 返回 y2

query_3 (MAP_WEAK_POINT)
    → 只看 MAP 允许的 facts → 返回 y3

# 结果：y1 ≠ y2 ≠ y3 ✅
```

---

## 📊 验证效果

### **Spec 收缩可见性的实际效果**

```python
# 示例：5 个 facts
all_facts = [
    {"fact_type": "HIGH_RISK_SEQUENCE", "round": 5},
    {"fact_type": "ROUND_SWING", "round": 10},
    {"fact_type": "FORCE_BUY_ROUND", "round": 3},
    {"fact_type": "PLAYER_IMPACT_STAT", "player": "X"},
    {"fact_type": "ECO_COLLAPSE_SEQUENCE", "round": 15},
]

# RISK spec 看到的 facts (3个)
risk_facts = SpecRecognizer.filter_facts_by_spec("RISK_ASSESSMENT", all_facts)
# → [HIGH_RISK_SEQUENCE, ROUND_SWING, ECO_COLLAPSE_SEQUENCE]

# ECON spec 看到的 facts (3个)
econ_facts = SpecRecognizer.filter_facts_by_spec("ECONOMIC_COUNTERFACTUAL", all_facts)
# → [ROUND_SWING, FORCE_BUY_ROUND, ECO_COLLAPSE_SEQUENCE]

# PLAYER spec 看到的 facts (2个)
player_facts = SpecRecognizer.filter_facts_by_spec("PLAYER_REVIEW", all_facts)
# → [PLAYER_IMPACT_STAT, ROUND_SWING]
```

**关键洞察**：
- ✅ RISK 和 ECON 都看到 `ROUND_SWING`，但其他 facts 不同
- ✅ PLAYER 只看到 `PLAYER_IMPACT_STAT`（第一个 fact）
- ✅ Input space 不同 → Output 自然不同

---

## 🔄 集成到现有系统

### **与 QuestionState 对齐**

**之前（L3）**：
```python
class QuestionState:
    intent: str          # 如 "RISK_ASSESSMENT"
    scope: Optional[str]  # 如 None, "SUMMARY"
```

**之后（L4）**：
```python
class QuestionState:
    intent: str
    scope: Optional[str]
    spec: Spec            # 新增：从 intent 推导

    def get_spec(self) -> Spec:
        """从 intent 导出 spec"""
        return SpecRecognizer.recognize_spec(self.intent)
```

---

### **与 DerivedFindings Pool 对齐**

**之前（L3）**：
```python
# 存储时带 intent
finding = DerivedFinding(
    intent="RISK_ASSESSMENT",
    fact_type="HIGH_RISK_SEQUENCE",
)

# 查询时返回所有 facts
facts = store.get_facts()  # 返回所有 intents 的 facts
```

**之后（L4）**：
```python
# 存储时带 spec focus（更细粒度）
finding = DerivedFinding(
    spec_focus="RISK",         # 新增
    intent="RISK_ASSESSMENT",
    fact_type="HIGH_RISK_SEQUENCE",
)

# 查询时只返回该 spec 允许的 facts
spec = SpecRecognizer.recognize_spec(intent)
allowed_types = spec.required_evidence.primary_fact_types
facts = store.get_facts(fact_types=allowed_types)  # 只返回允许的类型
```

---

## 🎯 6 个 MVP Spec 的设计

| Spec | Focus | Intents | Primary Facts | Max Facts |
|------|-------|---------|---------------|-----------|
| **ECON** | 经济 | ECONOMIC_COUNTERFACTUAL, ECONOMIC_FAILURE | FORCE_BUY_ROUND, ECO_COLLAPSE_SEQUENCE | 5 |
| **RISK** | 风险 | RISK_ASSESSMENT, STABILITY_ANALYSIS | HIGH_RISK_SEQUENCE, ROUND_SWING | 5 |
| **MAP** | 地图 | MAP_WEAK_POINT, EXECUTION_VS_STRATEGY | OBJECTIVE_LOSS_CHAIN, HIGH_RISK_SEQUENCE | 4 |
| **PLAYER** | 球员 | PLAYER_REVIEW, COUNTERFACTUAL_PLAYER_IMPACT | PLAYER_IMPACT_STAT, ROUND_SWING | 4 |
| **SUMMARY** | 总结 | MATCH_SUMMARY, MATCH_REVIEW | CONTEXT_ONLY | 3 |
| **MOMENTUM** | 动能 | MOMENTUM_ANALYSIS, PHASE_COMPARISON | ROUND_SWING | 5 |

---

## 📈 Master Theorem 版本

```
T(query) = Σ_{spec ∈ Specs(query)} T(spec) + O(1)

其中：
- |Specs(query)| ≤ k（max_sub_intents = 3）
- T(spec) 的输入空间被 spec 收缩：
  · 只有 spec.allowed_fact_types 的 facts
  · 只有 spec.max_events_window 的 events
  · 只有 spec.max_facts_total 的 facts
- O(1) = route + combine + persist（常数时间）
```

---

## ✅ 实施优先级

### **Phase 1: Spec Schema（已完成）** ✅

- [x] 定义 `Spec` dataclass
- [x] 定义 6 个 MVP spec
- [x] 创建 `INTENT_TO_SPEC_MAP`
- [x] 实现 `SpecRecognizer`

**文件**：
- `driftcoach/specs/spec_schema.py` - Spec 实现代码
- `SPEC_DESIGN.md` - Spec 设计文档

---

### **Phase 2: 集成到 Mining Pipeline（下一步）**

1. **Mining Plan Generator** 根据 spec 生成计划：
   ```python
   # 之前（L3）：返回全局模板
   plan = generate_mining_plan(query)  # 返回所有 facts 的模板

   # 之后（L4）：根据 spec 生成计划
   spec = SpecRecognizer.recognize_spec(intent)
   plan = generate_mining_plan_for_spec(query, spec)  # 只包含 spec 允许的 facts
   ```

2. **Evidence Filtering** 只保留 spec 允许的 facts：
   ```python
   all_facts = mine_facts_from_events(events)
   spec_facts = SpecRecognizer.filter_facts_by_spec(intent, all_facts)
   ```

3. **Derived Finding Builder** 只消费 spec 允许的 facts：
   ```python
   findings = build_findings_for_spec(spec, spec_facts)
   ```

---

### **Phase 3: 集成到 Analysis Pipeline（后续）**

1. **IntentHandler** 尊重 spec 的 budget：
   ```python
   class RiskAssessmentHandler(IntentHandler):
       def process(self, ctx: HandlerContext):
           spec = SpecRecognizer.recognize_spec(ctx.intent)

           # 只使用 spec 允许的 facts
           risk_facts = ctx.get_facts("HIGH_RISK_SEQUENCE")[:spec.budget.max_facts_per_type]

           # 应用 spec 的 output contract
           if len(risk_facts) >= spec.output_contract.standard_min_facts:
               return standard_decision(...)
           elif len(risk_facts) >= spec.output_contract.degraded_min_facts:
               return degraded_decision(...)
   ```

---

## 🚀 预期效果

### **解决"不同问题输出一样"**

| Query | Intent | Spec | 可见 Facts | 输出 |
|-------|--------|------|-----------|------|
| "这是不是一场高风险对局？" | RISK_ASSESSMENT | RISK | HIGH_RISK_SEQUENCE, ROUND_SWING | "这是一场高风险对局，R3-R5 和 R12-R14 连续失分" |
| "经济决策有什么问题？" | ECONOMIC_COUNTERFACTUAL | ECON | FORCE_BUY_ROUND, ECO_COLLAPSE_SEQUENCE | "R3 强起决策放大了风险，保枪可能更优" |
| "地图哪个点位薄弱？" | MAP_WEAK_POINT | MAP | OBJECTIVE_LOSS_CHAIN, HIGH_RISK_SEQUENCE | "R15-A 点位控制薄弱，连续丢失目标" |
| "这个选手表现如何？" | PLAYER_REVIEW | PLAYER | PLAYER_IMPACT_STAT, ROUND_SWING | "选手 X 在 R5, R10 关键回合贡献突出" |

**之前（L3）**：四个 query 输出相似（都在全局 facts 池捞）
**之后（L4）**：四个 query 输出不同（spec 收缩了可见性）

---

## 💡 关键洞察

### **从"数量"到"带类型的规模"**

**L3（之前）**：
```python
n = 有效的挖掘指令数
# 不同 query 的 n 可能相同，但属于不同"子空间"
# 没有 spec → n 退化成"总挖掘量" → 输出一样
```

**L4（现在）**：
```python
n = |Specs(query)| × budget_per_spec
# 每个 spec 有自己的 focus + allowed_facts + budget
# 不同 query → 不同 spec → 不同的 facts 子空间 → 输出不同
```

---

### **Spec vs GateOutcome**

**常见混淆**：
- ❌ ACCEPT/LOW/REJECT 是 spec
- ✅ ACCEPT/LOW/REJECT 是 GateOutcome（门控决策结果）

**正确理解**：
- **Spec**：算什么、允许缺什么、上界是多少、输出形态是什么
- **GateOutcome**：能不能算、怎么降级

**时序关系**：
```
Query → SpecRecognition → Mine(spec) → BuildFindings(spec) → GateOutcome → Decision/Narrative
         ↓                                                      ↓
      决定"算什么"                                          决定"能不能算"
```

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
- ✅ Spec Schema 已实现
- ⏳ 集成到 Mining Pipeline（Phase 2）
- ⏳ 集成到 Analysis Pipeline（Phase 3）

---

**文件清单**：
1. [driftcoach/specs/spec_schema.py](driftcoach/specs/spec_schema.py) - Spec 实现
2. [SPEC_DESIGN.md](SPEC_DESIGN.md) - Spec 设计文档
3. [SPEC_IMPLEMENTATION_SUMMARY.md](SPEC_IMPLEMENTATION_SUMMARY.md) - 本文档

---

**状态**：✅ Spec Schema 已完成
**下一步**：集成到 Mining Pipeline
