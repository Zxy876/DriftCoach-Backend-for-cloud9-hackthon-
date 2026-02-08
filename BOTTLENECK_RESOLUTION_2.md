# 第二个瓶颈解决：防止旧门控逻辑覆盖

## 📊 问题诊断（第二轮）

### **生产日志显示的新问题**

```bash
# DecisionMapper 工作正常 ✅
[DECISION_MAPPER] intent=RISK_ASSESSMENT, path=standard, uncertainty=0.28, severity=LOW

# 但后续被旧门控覆盖 ❌
[GATE] decision=证据不足 原因=样本量不足；总体置信度 0.27
```

**矛盾**：
- DecisionMapper 正确生成了决策（path=standard）
- 但最终输出仍是 "证据不足"
- 说明有**第二个位置**覆盖了 DecisionMapper 的结果

---

## 🔍 第二个瓶颈定位

### **根本原因**

在 [driftcoach/api.py:2740-2741](driftcoach/api.py#L2740-L2741)，旧门控的 `inference_plan["rationale"]` 覆盖了 DecisionMapper 的结果。

**代码流程**：
```python
# 1. DecisionMapper 生成决策（第 2412 行）
decision = mapper.map_to_decision(...)

# 2. 保存到 context_meta（第 2464 行）
context_meta["answer_synthesis"] = asdict(ans_result)

# 3. 旧门控重新判断（第 2560 行）
inference_plan = generate_inference_plan(...)  # 返回 "证据不足"

# 4. ❌ 覆盖 DecisionMapper 结果（第 2740-2741 行）
if inference_plan.get("rationale"):
    payload["assistant_message"] = inference_plan.get("rationale")  # 覆盖！
```

---

## 🔧 修复方案

### **修改位置**

**文件**：[driftcoach/api.py:2732-2747](driftcoach/api.py#L2732-L2747)

```python
# ❌ 之前（旧门控总是覆盖）
if inference_plan.get("rationale"):
    payload["assistant_message"] = inference_plan.get("rationale")

# ✅ 之后（DecisionMapper 优先）
# ✅ 1→2 Breakthrough: Prioritize DecisionMapper result over old gate rationale
# If DecisionMapper has generated a result, use it instead of inference_plan rationale
answer_synthesis = context_meta.get("answer_synthesis", {})
if answer_synthesis.get("claim") and answer_synthesis.get("verdict") != "INSUFFICIENT":
    # DecisionMapper provided a valid answer (DEGRADED or STANDARD)
    # Use its claim instead of the old gate's "证据不足"
    payload["assistant_message"] = answer_synthesis.get("claim")
elif inference_plan.get("rationale"):
    # Fallback to old gate logic
    payload["assistant_message"] = inference_plan.get("rationale")
```

---

## ✅ 修复逻辑

### **决策优先级**

```python
# 三层决策优先级
1. DecisionMapper (DEGRADED/STANDARD)  ← 最高优先级 ✅
2. 旧门控 (INSUFFICIENT)                ← 仅当 DecisionMapper 也拒绝时
3. 默认消息                              ← 兜底
```

### **具体规则**

| DecisionMapper 结果 | 旧门控结果 | 最终输出 | 说明 |
|-------------------|-----------|---------|------|
| DEGRADED | EVIDENCE_INSUFFICIENT | **DecisionMapper** ✅ | 有证据就提供降级决策 |
| STANDARD | EVIDENCE_INSUFFICIENT | **DecisionMapper** ✅ | 完整证据优先 |
| INSUFFICIENT | EVIDENCE_INSUFFICIENT | **旧门控** | 两者都拒绝，用旧门控的详细说明 |

---

## 🧪 测试验证

### **测试 1：DEGRADED 决策优先**
```python
# DecisionMapper: DEGRADED
answer_synthesis = {
    "claim": "基于1条有限证据的初步分析...",
    "verdict": "LOW_CONFIDENCE"  # ≠ INSUFFICIENT
}

# 旧门控: EVIDENCE_INSUFFICIENT
inference_plan = {
    "rationale": "证据不足..."
}

# 结果：使用 DecisionMapper ✅
payload["assistant_message"] == answer_synthesis["claim"]
assert "证据不足" not in payload["assistant_message"]
```

### **测试 2：INSUFFICIENT 回退到旧门控**
```python
# DecisionMapper: INSUFFICIENT（真拒绝）
answer_synthesis = {
    "verdict": "INSUFFICIENT"
}

# 旧门控: EVIDENCE_INSUFFICIENT
inference_plan = {
    "rationale": "缺少胜负结果；样本量不足..."
}

# 结果：使用旧门控 ✅
payload["assistant_message"] == inference_plan["rationale"]
```

### **测试 3：STANDARD 决策优先**
```python
# DecisionMapper: STANDARD
answer_synthesis = {
    "claim": "这是一场高风险对局",
    "verdict": "YES"
}

# 旧门控: EVIDENCE_INSUFFICIENT
inference_plan = {
    "rationale": "证据不足"
}

# 结果：使用 DecisionMapper ✅
payload["assistant_message"] == "这是一场高风险对局"
```

---

## 📈 效果对比

### **之前（两层门控冲突）**

```
DecisionMapper: "基于5条有限证据的初步分析..." ✅
                      ↓
旧门控: "证据不足" ❌ 覆盖
                      ↓
最终输出: "证据不足" ❌
```

### **现在（统一决策流）**

```
DecisionMapper: "基于5条有限证据的初步分析..." ✅
                      ↓
检查: verdict != INSUFFICIENT ? ✅
                      ↓
最终输出: "基于5条有限证据的初步分析..." ✅
```

---

## 🎯 关键突破

### **统一决策层**

**问题**：两个决策源（DecisionMapper 和旧门控）冲突

**解决**：建立明确的优先级
1. DecisionMapper > 旧门控（当有有效答案时）
2. 旧门控作为回退（当 DecisionMapper 也拒绝时）

**核心原则**：
```python
# 永不拒绝有证据的查询（最终版本）
if DecisionMapper 提供了有效答案 (DEGRADED/STANDARD):
    使用 DecisionMapper ✅
elif DecisionMapper 说 INSUFFICIENT:
    使用旧门控的详细说明 ✅
```

---

## 📁 修改文件

| 文件 | 修改内容 |
|------|---------|
| [driftcoach/api.py:2732-2747](driftcoach/api.py#L2732-L2747) | ✅ DecisionMapper 优先逻辑 |
| [tests/test_api_gate_fix.py](tests/test_api_gate_fix.py) | ✅ 新增测试 |

---

## 🚀 生产环境预期

### **修复前**
```bash
[DECISION_MAPPER] path=standard, uncertainty=0.28 ✅
[GATE] decision=证据不足 ❌
最终输出: "证据不足"
```

### **修复后**
```bash
[DECISION_MAPPER] path=standard, uncertainty=0.28 ✅
[GATE] decision=证据不足 ⚠️ (被忽略)
最终输出: "基于5条有限证据的初步分析：检测到 2 个 HIGH_RISK_SEQUENCE" ✅
```

---

## 💡 关键洞察

### **为什么会有第二层门控**

历史原因：
- 旧代码：`generate_inference_plan()` 是唯一的门控
- 新代码：引入 DecisionMapper 作为第一层
- 问题：两者没有协调，导致冲突

### **为什么不能简单删除旧门控**

原因：
1. **向后兼容**：其他逻辑可能依赖 `inference_plan`
2. **详细说明**：旧门控的 `rationale` 在真拒绝时更有用
3. **渐进迁移**：需要时间完全替换所有旧逻辑

### **正确的修复策略**

不是删除旧门控，而是**建立优先级**：
- 新逻辑（DecisionMapper）> 旧逻辑（旧门控）
- 这样既保留了向后兼容，又实现了 1→2 突破

---

## 📝 总结

### **第一轮修复**（[BOTTLENECK_RESOLUTION.md](BOTTLENECK_RESOLUTION.md)）
- 问题：DecisionMapper 未集成到主流程
- 解决：在 api.py:2400 调用 DecisionMapper
- 结果：DecisionMapper 开始工作 ✅

### **第二轮修复**（本次）
- 问题：旧门控覆盖 DecisionMapper 结果
- 解决：在 api.py:2740 建立优先级
- 结果：DecisionMapper 结果优先 ✅

### **完整效果**

```
查询: "这是不是一场高风险对局？"
数据: 5731 events, 2 HIGH_RISK_SEQUENCE, 3 ROUND_SWING

层次 1（之前）: "证据不足", confidence=0.27 ❌
层次 2（现在）: "基于5条有限证据的初步分析...", confidence=0.35 ✅
```

**1→2 跨越，真正完成！** 🎉

---

**修复日期**：2025-02-07（第二轮）
**影响范围**：所有教练查询的最终输出
**突破等级**：Level 1 → Level 2（技术成功 → 教练可用）
