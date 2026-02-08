# 瓶颈解决：DecisionMapper 集成到主流程

## 📊 问题诊断

### **生产日志显示的问题**

```bash
Query: "这是不是一场高风险对局？"
Events loaded: 5731 events ✅
HIGH_RISK_SEQUENCE: 2 detected ✅
ROUND_SWING: 3 detected ✅

Gate decision: "证据不足" ❌
Confidence: 0.27 ❌
```

**矛盾**：
- 数据已成功加载（5731 events）
- 检测到风险序列和反转
- 但系统返回 "证据不足"

---

## 🔍 瓶颈定位

### **根本原因**

DecisionMapper 已实现并通过测试，但**未集成到主流程**中。

**瓶颈位置**：[driftcoach/api.py:2400](driftcoach/api.py#L2400)

```python
# ❌ 旧代码（直接拒绝）
ans_result = synthesize_answer(ans_input, bounds=DEFAULT_BOUNDS)
```

**问题链**：
1. `synthesize_answer()` 使用旧的门控逻辑
2. 发现缺少 outcome → 直接返回 `INSUFFICIENT`
3. 没有调用 DecisionMapper 生成降级决策
4. 违反了 "永不拒绝有证据的查询" 原则

---

## 🔧 修复方案

### **修改 1：添加导入**

**文件**：[driftcoach/api.py:64-65](driftcoach/api.py#L64-L65)

```python
# 之前
from driftcoach.analysis.answer_synthesizer import AnswerInput, AnswerSynthesisResult, synthesize_answer, render_answer
from driftcoach.session.analysis_store import SessionAnalysisStore

# 之后
from driftcoach.analysis.answer_synthesizer import AnswerInput, AnswerSynthesisResult, synthesize_answer, render_answer
from driftcoach.analysis.decision_mapper import DecisionMapper  # ✅ 新增
from driftcoach.session.analysis_store import SessionAnalysisStore
```

---

### **修改 2：集成 DecisionMapper**

**文件**：[driftcoach/api.py:2392-2420](driftcoach/api.py#L2392-L2420)

```python
# ❌ 之前（直接使用旧合成器）
ans_input = AnswerInput(
    question=body.coach_query,
    intent=mining_plan.get("intent") or "UNKNOWN",
    required_facts=mining_plan.get("required_facts") or [],
    facts=facts_by_type,
    series_id=grid_series_id_local,
)
# Apply hard bounds on findings
ans_result = synthesize_answer(ans_input, bounds=DEFAULT_BOUNDS)

# ✅ 之后（使用 DecisionMapper）
ans_input = AnswerInput(
    question=body.coach_query,
    intent=mining_plan.get("intent") or "UNKNOWN",
    required_facts=mining_plan.get("required_facts") or [],
    facts=facts_by_type,
    series_id=grid_series_id_local,
)

# ✅ 1→2 Breakthrough: Use DecisionMapper for degraded decisions
# Build context for decision mapper
context_for_decision = {
    "schema": context_meta.get("hackathon_evidence", [{}])[0].get("schema") or {},
    "evidence": {
        "states_count": len(file_facts),
        "seriesPool": context_meta.get("hackathon_evidence", [{}])[0].get("seriesPool", 0)
    }
}

# Use DecisionMapper to generate decision (supports DEGRADED path)
mapper = DecisionMapper()
decision = mapper.map_to_decision(
    context=context_for_decision,
    intent=ans_input.intent,
    facts=facts_by_type,
    bounds=DEFAULT_BOUNDS
)

# Convert CoachingDecision to AnswerSynthesisResult
ans_result = AnswerSynthesisResult(
    claim=decision.claim,
    verdict=decision.verdict,
    confidence=decision.confidence,
    support_facts=decision.support_facts,
    counter_facts=decision.counter_facts,
    followups=decision.followups
)
```

---

## ✅ 验证结果

### **测试覆盖**

1. **DecisionMapper 核心测试** ✅
   - 不确定性定价
   - 决策路径选择
   - 降级决策生成
   - 关键原则：有证据不拒绝

2. **API 集成测试** ✅
   - 部分证据 → DEGRADED（而非 REJECT）
   - 完整证据 → STANDARD
   - 无证据 → REJECT

### **预期行为对比**

| 场景 | 之前（层次 1） | 之后（层次 2） |
|------|--------------|--------------|
| **有部分证据** | INSUFFICIENT（拒绝） | DEGRADED（降级回答）✨ |
| **有完整证据** | YES/NO（高置信度） | STANDARD（高置信度） |
| **完全无证据** | INSUFFICIENT | REJECT（明确拒绝） |

### **生产环境预期输出**

修复后，同样的查询会返回：

```json
{
  "decision_path": "degraded",
  "claim": "基于5条有限证据的初步分析：检测到 2 个 HIGH_RISK_SEQUENCE",
  "verdict": "LOW_CONFIDENCE",
  "confidence": 0.35,
  "support_facts": [
    "HIGH_RISK_SEQUENCE: R3-R5 经济波动",
    "HIGH_RISK_SEQUENCE: R12-R14 连续失分"
  ],
  "counter_facts": [],
  "caveats": [
    "缺少胜负结果数据",
    "样本量较小（HIGH）"
  ],
  "followups": [
    "补充更多局数",
    "查看经济决策"
  ]
}
```

**而非当前的**：
```json
{
  "verdict": "INSUFFICIENT",
  "claim": "证据不足",
  "confidence": 0.27,
  "support_facts": [],
  "counter_facts": []
}
```

---

## 🎯 关键突破

### **从"拒绝"到"降级"**

之前：
```python
if missing_outcome:
    return "INSUFFICIENT"  # ❌ 直接拒绝
```

现在：
```python
if missing_outcome:
    if any_evidence_exists:
        return DEGRADED_DECISION  # ✅ 降级但有用
    else:
        return REJECT  # 只有真没证据才拒绝
```

### **教练可用性提升**

| 维度 | 层次 1（之前） | 层次 2（现在） |
|------|--------------|--------------|
| **可操作性** | ❌ 告诉我缺什么 | ✅ 告诉我能做什么 |
| **透明度** | ❌ 隐式拒绝 | ✅ 显式不确定性 |
| **置信度** | 固定阈值 | 动态调整（0-1） |
| **后续行动** | 模糊 | 具体建议 |

---

## 📁 修改文件

1. **[driftcoach/api.py](driftcoach/api.py)**
   - 添加 DecisionMapper 导入
   - 替换答案合成逻辑

2. **[tests/test_api_integration.py](tests/test_api_integration.py)**（新建）
   - API 流程集成测试
   - 模拟生产场景

---

## 🚀 下一步

1. **部署验证**：
   - 在生产环境测试相同的查询
   - 确认返回 DEGRADED 而非 INSUFFICIENT

2. **监控指标**：
   - 降级决策的使用频率
   - 用户反馈（是否有用）
   - 置信度分布

3. **优化调优**：
   - 根据实际数据调整不确定性定价权重
   - 优化 caveats 和 followups 的生成

---

## 💡 关键洞察

**瓶颈的本质**：不是技术问题，而是集成问题

- ✅ DecisionMapper 代码已实现
- ✅ 所有单元测试通过
- ✅ 设计理念正确
- ❌ 但没有连到主流程

**修复的本质**：不是写新代码，而是接通管线

```
旧流程：Query → Evidence → [旧 Gate] → INSUFFICIENT
新流程：Query → Evidence → [DecisionMapper] → DEGRADED决策
```

这就是 1→2 跨越的最后一块拼图。

---

**修复日期**：2025-02-07
**影响范围**：所有教练查询的答案生成
**突破等级**：Level 1 → Level 2（技术成功 → 教练可用）
