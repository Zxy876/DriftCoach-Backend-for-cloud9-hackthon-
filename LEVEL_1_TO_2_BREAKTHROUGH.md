# 1→2 跨越：降级决策层实现

## 🎯 核心突破

**从 Context_State → Coaching_Decision 的关键跨越**

### **之前（层次 1）：计算性成功，但不可用**
```python
# 输出 y（Context_State）
{
  "states": 36,
  "series_pool": 0,
  "hasOutcome": false,
  "outcome_field": "NOT_FOUND"
}
```

**问题**：虽然可计算，但教练无法使用

---

### **之后（层次 2）：决策级输出**
```python
# 输出 y（Coaching_Decision）
{
  "decision_path": "degraded",
  "claim": "基于2条有限证据的初步分析：检测到 2 个 HIGH_RISK_SEQUENCE",
  "verdict": "LOW_CONFIDENCE",
  "confidence": 0.35,
  "support_facts": ["HIGH_RISK_SEQUENCE: R3-R5 经济波动"],
  "caveats": ["缺少胜负结果数据", "样本量较小（HIGH）"],
  "followups": ["补充更多局数", "查看经济决策"]
}
```

**突破**：基于任何可用证据给出可操作建议

---

## 🔧 核心实现：Decision Mapper

### **三态决策路径**

```python
class DecisionPath(Enum):
    STANDARD = "standard"       # 完整证据 → 正常结论（0.7+ 置信度）
    DEGRADED = "degraded"       # 部分证据 → 降级结论（0.25-0.45 置信度）
    REJECT = "reject"           # 无证据 → 明确拒绝（<0.25 置信度）
```

---

### **不确定性定价**

```python
class UncertaintyMetrics:
    total: float              # 总不确定性 (0-1)
    missing_outcome: float     # 缺少 outcome 的影响 (0.4)
    small_sample: float        # 小样本的影响 (0-0.3)
    no_comparison: float       # 缺少对比的影响 (0.2)

    @property
    def severity(self) -> str:
        if total >= 0.8: return "CRITICAL"
        if total >= 0.5: return "HIGH"
        if total >= 0.3: return "MEDIUM"
        return "LOW"
```

**关键设计**：
- 不确定性被**量化**（而非二元）
- 每种缺失都有明确的**代价**
- 可以根据总不确定性选择决策路径

---

## 📊 决策路径选择

```
if total_facts == 0:
    → REJECT（完全无证据）

elif uncertainty >= 0.8:
    → REJECT（不确定性太高）

elif uncertainty >= 0.4:
    → DEGRADED（降级但有价值）
    ✅ 核心突破：有证据就不拒绝

else:
    → STANDARD（正常分析）
```

---

## 🎯 关键原则

### **原则 1：永不拒绝有证据的查询**

```python
# ❌ 之前（层次 1）
if not enough_evidence:
    return "INSUFFICIENT"  # 拒绝

# ✅ 现在（层次 2）
if not enough_evidence:
    if any_evidence_exists:
        return DEGRADED_DECISION  # 降级回答
    else:
        return REJECT  # 真的没证据才拒绝
```

### **原则 2：不确定性必须显式声明**

```python
# DEGRADED 决策包含：
caveats: [
    "缺少胜负结果数据",
    "样本量较小（HIGH）",
    "缺少对比数据"
]

# 这样教练知道：
# - 有结论，但要谨慎解读
# - 哪些地方数据缺失
# - 如何改进（followups）
```

### **原则 3：置信度反映不确定性**

```python
# 置信度计算：
base_confidence = 0.5
degraded_confidence = base_confidence * (1.0 - uncertainty.total)

# 示例：
# uncertainty = 0.2 → confidence = 0.4
# uncertainty = 0.5 → confidence = 0.25
# uncertainty = 0.8 → confidence = 0.1
```

---

## 🧪 验证结果

```bash
$ python3 tests/test_decision_mapper.py

✅ Complete context: uncertainty=0.00, severity=LOW
✅ Incomplete context: uncertainty=0.82, severity=CRITICAL

✅ No facts → reject
✅ High uncertainty (0.85) → reject
✅ Medium uncertainty (0.5) + facts → degraded  ← 关键
✅ Low uncertainty (0.2) → standard

✅ Degraded decision:
   Path: degraded
   Claim: 基于1条有限证据的初步分析
   Confidence: 0.25
   Caveats: ['缺少胜负结果数据', '样本量较小（HIGH）']
   Support: ['fact: 经济波动']

✅ Key principle: NEVER refuse when evidence exists
   Path: degraded (not REJECT)  ← 1→2 突破
```

---

## 📈 对比：层次 1 → 层次 2

| 维度 | 层次 1（之前） | 层次 2（现在） |
|------|--------------|--------------|
| **输出类型** | Context_State | Coaching_Decision |
| **有部分证据** | INSUFFICIENT（拒绝） | DEGRADED（降级回答）✨ |
| **无证据** | INSUFFICIENT | REJECT（明确拒绝） |
| **不确定性** | 隐式（无量化） | 显式（0-1 定价） |
| **置信度** | 固定阈值 | 动态调整 |
| **可操作性** | ❌ 告诉我缺什么 | ✅ 告诉我能做什么 |

---

## 🔧 架构集成

### **完整流程**

```
用户查询
    ↓
[第三章] Evidence Gate
    ├─ 控制 n ≤ k
    └─ 概率化决策
    ↓
[第四章] Handler Router（分治）
    ├─ Divide: 路由到 Handler
    ├─ Conquer: Handler 处理
    └─ Combine: 统一格式
    ↓
[1→2] Decision Mapper（降级层）
    ├─ 定价不确定性
    ├─ 选择路径（STANDARD/DEGRADED/REJECT）
    └─ 生成可操作决策
    ↓
Coaching Decision（教练可用）
```

---

## 📁 新增文件

**核心实现**：
- [driftcoach/analysis/decision_mapper.py](driftcoach/analysis/decision_mapper.py) - Decision Mapper 核心逻辑
- [tests/test_decision_mapper.py](tests/test_decision_mapper.py) - 完整测试套件

**集成点**：
- [driftcoach/analysis/intent_handlers.py](driftcoach/analysis/intent_handlers.py) - Handler 使用 Decision Mapper

---

## 🎓 理论基础

### **从 CLRS 视角**

这是分治的自然延伸：

```
分治（第四章）：T(n) = aT(n/b) + f(n)
                ↓
降级决策：当 f(n) 很大（数据缺失），如何仍能提供有价值的输出？
                ↓
答案：降低质量，但保持可计算性
```

### **从 DriftCoach 视角**

```
f(x) = y

层次 0：F(x) → ERROR  （不可计算）
层次 1：F(x) → Context_State  （可计算但不可用）
层次 2：F(x) → Coaching_Decision  （可计算 + 可用）✨
```

---

## 💡 关键洞察

### **1→2 的本质**

**不是代码量的增加，而是决策哲学的改变**

```python
# 之前（层次 1）：
"完美的证据 → 回答"
"不完美的证据 → 拒绝"

# 现在（层次 2）：
"完美的证据 → 标准回答"
"不完美的证据 → 降级回答 + 告知不确定性"
"完全无证据 → 明确拒绝"
```

### **为什么这是关键突破**

1. **从不完整数据中提取价值**
   - 之前：缺少 outcome → 无法分析
   - 现在：缺少 outcome → 基于经济事件给出降级分析

2. **明确告知不确定性**
   - Caveats 告诉教练哪些地方数据缺失
   - Followups 告诉如何改进

3. **动态置信度**
   - 不再是固定的 0.7 或 0.3
   - 而是根据不确定性动态调整

---

## 🚀 下一步

现在你已经完成了：
1. ✅ 第三章：控制增长（n ≤ k）
2. ✅ 第四章：分治结构（Handler 架构）
3. ✅ 1→2 跨越：降级决策层

**下一步可以做的**：

1. **优化不确定性定价**：
   - 根据实际数据调优权重
   - 学习哪些缺失更致命

2. **Handler 完整实现**：
   - 补全剩余的 Handler
   - 为每个 Handler 添加降级逻辑

3. **集成到主流程**：
   - 在 api.py 中使用 Decision Mapper
   - 返回 Coaching_Decision 而非 AnswerSynthesisResult

---

## 🎉 总结

**1→2 跨越的本质**：

```
从：技术成功（可计算）
到：教练可用（可操作）

关键：降级决策层
核心：永不拒绝有证据的查询
```

这就是你系统从"合格但未成熟"到"教练可用"的关键一步。
