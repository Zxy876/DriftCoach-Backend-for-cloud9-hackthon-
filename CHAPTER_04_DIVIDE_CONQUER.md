# 第四章：分治

## 🎯 学习目标

用分治重构 Evidence Gate 之后的 F，让每一段计算都保持 n ≤ k 的前提不被破坏。

---

## 📊 问题诊断

### **之前的 F 结构（单体式）**

```python
# driftcoach/analysis/answer_synthesizer.py (403 行)
def synthesize_answer(inp: AnswerInput) -> AnswerSynthesisResult:
    intent = inp.intent.upper()

    # ❌ 单体结构：所有逻辑都在一个大函数里
    if intent == "RISK_ASSESSMENT":
        # 50 行逻辑
    elif intent == "ECONOMIC_COUNTERFACTUAL":
        # 50 行逻辑
    elif intent == "MOMENTUM_ANALYSIS":
        # 50 行逻辑
    # ... 10+ 个分支
```

**问题**：
- ❌ T(intent) = O(number_of_intents) - 需要遍历所有 if-elif
- ❌ 无法独立测试每个 intent
- ❌ 添加新 intent 需要修改大函数
- ❌ 容易在 F 内部重新引入"隐性增长"

---

## 🔧 分治重构方案

### **Divide（拆分）：按 Intent 拆分**

```python
class IntentHandler(ABC):
    """每个 intent 的独立处理器"""

    @abstractmethod
    def can_handle(self, intent: str) -> bool:
        """是否能处理这个 intent"""
        pass

    @abstractmethod
    def process(self, ctx: HandlerContext) -> AnswerSynthesisResult:
        """处理逻辑"""
        pass
```

**关键设计**：
- 每个 handler **只负责一种 intent**
- Handler 之间 **完全独立**
- 每个 handler **必须遵守全局 bounds**

---

### **Conquer（独立处理）**

```python
class RiskAssessmentHandler(IntentHandler):
    def can_handle(self, intent: str) -> bool:
        return intent == "RISK_ASSESSMENT"

    def process(self, ctx: HandlerContext) -> AnswerSynthesisResult:
        hrs = ctx.get_facts("HIGH_RISK_SEQUENCE")
        swings = ctx.get_facts("ROUND_SWING")

        if len(hrs) >= 2:
            return AnswerSynthesisResult(
                claim="这是一场高风险对局",
                verdict="YES",
                confidence=0.9,
                support_facts=self.get_support_facts(ctx, ["HIGH_RISK_SEQUENCE"], limit=3),
                ...
            )
        # ✅ 只关注这一种 intent 的逻辑
```

**好处**：
- ✅ **可独立测试**：每个 handler 可以单独验证
- ✅ **可演化**：修改一个 intent 不会影响其他 intent
- ✅ **有界**：每个 handler 必须遵守 bounds

---

### **Combine（合并）：路由器**

```python
class AnswerSynthesizer:
    """
    Divide-and-conquer answer synthesizer.
    """

    def __init__(self, handlers: List[IntentHandler]):
        self.handlers = handlers

    def synthesize(self, inp: AnswerInput, bounds: SystemBounds) -> AnswerSynthesisResult:
        """
        Algorithm:
        1. Divide: 路由到对应 handler
        2. Conquer: Handler 独立处理
        3. Combine: 返回统一格式
        """
        intent = inp.intent.upper()
        ctx = HandlerContext(inp, bounds, intent)

        # Divide + Conquer: O(1) 路由
        for handler in self.handlers:
            if handler.can_handle(intent):
                result = handler.process(ctx)
                # Combine: 强制执行全局 bounds
                result.support_facts = result.support_facts[:bounds.max_support_facts]
                return result

        raise RuntimeError(f"No handler for: {intent}")
```

**性能**：
- 之前：O(number_of_intents) - 遍历所有 if-elif
- 现在：O(1) - 直接路由

---

## 📐 复杂度分析

### **时间复杂度**

```
T(intent) = O(1)  // 路由到 handler
           + O(h)    // handler 处理时间
           + O(b)    // bounds 应用

其中：
- h = handler 特定逻辑（通常是常数）
- b = bounds.max_support_facts（常数，如 3）

总复杂度：O(1)
```

### **空间复杂度**

```
S(n) = O(k * b)

其中：
- k = number of handlers（常数）
- b = bounds.max_support_facts（常数）

每个 handler 独立，不共享状态 → 空间隔离
```

---

## 🎯 分治的核心收益

### **1. 独立演化**

添加新 intent 不需要修改现有代码：

```python
# 新增 handler
class NewIntentHandler(IntentHandler):
    def can_handle(self, intent: str) -> bool:
        return intent == "NEW_INTENT"

    def process(self, ctx: HandlerContext) -> AnswerSynthesisResult:
        ...

# 注册即可
synthesizer.add_handler(NewIntentHandler())
```

### **2. 独立测试**

每个 handler 可以单独验证：

```python
def test_risk_assessment():
    handler = RiskAssessmentHandler()
    ctx = HandlerContext(...)
    result = handler.process(ctx)
    assert result.verdict == "YES"
```

### **3. 边界保护**

每个 handler 必须遵守 bounds：

```python
def process(self, ctx: HandlerContext) -> AnswerSynthesisResult:
    # Handler 内部也必须遵守 bounds
    support = self.get_support_facts(ctx, ["HIGH_RISK_SEQUENCE"])
    # ↑ 内部已经应用了 bounds.max_support_facts
```

---

## 🚧 实施结果

### **重构前**

```
driftcoach/analysis/answer_synthesizer.py
├── 403 行代码
├── 10+ 个 elif 分支
├── 无法独立测试
└── 添加新 intent 需要修改大函数
```

### **重构后**

```
driftcoach/analysis/
├── intent_handlers.py         # Handler 定义
│   ├── IntentHandler (ABC)
│   ├── RiskAssessmentHandler
│   ├── EconomicCounterfactualHandler
│   ├── MomentumAnalysisHandler
│   ├── StabilityAnalysisHandler
│   ├── CollapseOnsetHandler
│   └── FallbackHandler
├── synthesizer_router.py       # 路由器（Combine）
│   └── AnswerSynthesizer
└── answer_synthesizer.py       # 向后兼容（保留）

tests/
└── test_divide_and_conquer.py  # 分治测试
```

---

## ✅ 验证结果

```bash
$ python3 tests/test_divide_and_conquer.py

✅ High risk assessment
✅ Low confidence with limited evidence
✅ Economic counterfactual
✅ Momentum analysis with swings
✅ Momentum analysis without swings
✅ Bounds enforcement
✅ Handler routing
✅ Fallback handler
✅ Handler independence

All divide-and-conquer tests passed!
```

---

## 🎓 CLRS 第四章核心概念映射

| CLRS 概念 | DriftCoach 实现 |
|----------|---------------|
| **Divide** | 按 Intent 类型拆分问题 |
| **Conquer** | 每个 Handler 独立处理 |
| **Combine** | Router 返回统一格式 |
| **T(n) = aT(n/b) + f(n)** | T(intent) = O(1) + O(h) + O(b) |
| **Master Theorem** | 每个 Handler 独立 → 复杂度不累积 |

---

## 🔮 下一步：递归结构

分治的下一步是**递归**：如果某个 handler 内部仍然太复杂，可以继续应用分治：

```python
class ComplexIntentHandler(IntentHandler):
    def process(self, ctx: HandlerContext) -> AnswerSynthesisResult:
        # 再次分治：拆分为子任务
        sub_tasks = self._divide(ctx)
        results = [self._conquer(task) for task in sub_tasks]
        return self._combine(results)
```

这将在下一章深入。

---

## 💡 关键洞察

**分治的核心不是"拆代码"，而是"拆问题"**：

❌ 错误理解：把一个大函数拆成多个小函数
✅ 正确理解：识别问题的独立子结构，让它们独立解决

对 DriftCoach 来说：
- **子问题**：每种 intent 的分析逻辑
- **独立性**：它们不共享状态、不依赖顺序
- **可合并**：都返回统一的 AnswerSynthesisResult 格式

这就是第四章的核心。
