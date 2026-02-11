# BudgetController 渐进发布计划

## 🎯 发布策略

采用**环境变量控制的渐进发布**，确保可以快速回滚。

---

## 📋 发布阶段

### Phase 1: 准备阶段（当前状态）

**环境变量设置：**
```
SHADOW_MODE=true
BUDGET_CONTROLLER_ENABLED=true
```

**行为：**
- ✅ 同时运行 WITH 和 WITHOUT BudgetController
- ✅ 记录对比数据到日志
- ✅ 返回 WITHOUT 结果（baseline）给用户
- ✅ 所有验证指标通过

**状态：** ✅ 完成

---

### Phase 2: 灰度阶段 - 10% 流量

**目标：** 对少量真实用户启用 BudgetController，监控稳定性

**环境变量设置：**
```bash
# 在 Railway Dashboard 设置
BUDGET_CONTROLLER_ENABLED=true
BUDGET_CONTROLLER_ROLLOUT_PERCENTAGE=10
SHADOW_MODE=disabled
```

**代码修改：** 需要添加百分比控制逻辑

**监控指标：**
- 错误率（目标：< 5%）
- 响应时间（目标：无显著增加）
- Confidence 分布（目标：≥ 90% >= 0.7）
- 用户反馈（目标：无负面反馈）

**持续时间：** 24-48 小时

**回滚条件：**
- 错误率 > 10%
- 大量用户投诉
- Confidence < 0.7 的比例 > 20%

---

### Phase 3: 扩大阶段 - 50% 流量

**前提条件：** Phase 2 无严重问题

**环境变量设置：**
```bash
BUDGET_CONTROLLER_ENABLED=true
BUDGET_CONTROLLER_ROLLOUT_PERCENTAGE=50
SHADOW_MODE=disabled
```

**监控指标：**
- 同 Phase 2
- 额外关注：不同查询类型的性能

**持续时间：** 48-72 小时

---

### Phase 4: 全量发布 - 100% 流量

**前提条件：** Phase 3 稳定运行

**环境变量设置：**
```bash
BUDGET_CONTROLLER_ENABLED=true
BUDGET_CONTROLLER_ROLLOUT_PERCENTAGE=100
# 或直接移除 BUDGET_CONTROLLER_ROLLOUT_PERCENTAGE
```

**监控：** 持续监控上述指标

---

## 🔧 实现方案

### 方案 A：简单开关（推荐，快速）

**优点：**
- 实现简单
- 立即生效
- 快速回滚

**环境变量：**
```bash
# 第 1 步：禁用 Shadow Mode，启用 BudgetController
SHADOW_MODE=removed  # 或直接删除这个变量
BUDGET_CONTROLLER_ENABLED=true

# 第 2 步：监控 24-48 小时

# 第 3 步：如果出问题，立即回滚
BUDGET_CONTROLLER_ENABLED=false
```

**代码修改：** 无需修改，现有代码已支持

**风险：** 全量发布，如果出问题影响所有用户

---

### 方案 B：百分比控制（更安全）

**优点：**
- 渐进式发布
- 风险可控
- AB 测试能力

**需要修改代码：**

在 `intent_handlers.py` 中添加百分比控制：

```python
def process(self, ctx: HandlerContext) -> AnswerSynthesisResult:
    # ... existing code ...

    # 百分比控制
    rollout_percentage = int(os.getenv("BUDGET_CONTROLLER_ROLLOUT_PERCENTAGE", "0"))
    should_use_budget_controller = (
        budget_controller_enabled and
        (rollout_percentage >= 100 or
         hash(ctx.session_id) % 100 < rollout_percentage)
    )

    if shadow_mode:
        # Shadow mode logic
        ...
    elif should_use_budget_controller:
        # BudgetController logic
        ...
    else:
        # Baseline logic
        ...
```

**缺点：**
- 需要修改代码
- 增加复杂度
- 需要测试

---

## 🎯 推荐方案

### **采用方案 A（简单开关）+ 监控预案**

**理由：**
1. ✅ Shadow Mode 已经充分验证（100+ 样本）
2. ✅ 所有指标通过（效率 60%，稳定性 100%）
3. ✅ 代码已经稳定运行
4. ✅ 可以立即回滚（改一个环境变量）

**发布步骤：**

#### Step 1: 禁用 Shadow Mode，启用 BudgetController

在 Railway Dashboard：
1. 删除环境变量 `SHADOW_MODE`
2. 确认 `BUDGET_CONTROLLER_ENABLED=true`
3. 点击 "Redeploy"

#### Step 2: 监控 24-48 小时

**监控指标：**
```python
# 日志中应该看到：
- 没有更多 SHADOW_METRICS（shadow mode 已禁用）
- 正常的查询处理
- Confidence 值应该 ≥ 0.7
```

**Railway Logs 搜索关键字：**
- `ERROR` - 检查是否有错误
- `WARNING` - 检查是否有警告
- `confidence` - 检查 confidence 分布

#### Step 3: 如果出现问题，立即回滚

在 Railway Dashboard：
1. 设置 `BUDGET_CONTROLLER_ENABLED=false`
2. 点击 "Redeploy"

回滚时间：~2 分钟

---

## 📊 监控方案

### 1. Railway Logs 监控

**每日检查：**
```bash
# 错误数量
grep ERROR <logs> | wc -l

# Confidence 分布（需要添加日志）
grep "confidence=" <logs> | awk -F'=' '{print $2}' | sort -n | uniq -c
```

### 2. 添加生产监控日志

在 `intent_handlers.py` 中添加：

```python
# 当 BudgetController 启用时，记录简单统计
if budget_controller_enabled and not shadow_mode:
    logger.warning(f"📊 BC_METRICS: facts_used={len(mined_hrs)+len(mined_swings)}, confidence={final_confidence:.2f}, stopped_early={stopped_early}")
```

### 3. 性能对比

如果有 APM 工具（如 Railway 的内置监控），关注：
- P50 响应时间
- P95 响应时间
- 错误率

---

## 🚀 立即行动

### 如果你同意方案 A（简单开关）：

**我可以立即帮你：**

1. ✅ 删除 `SHADOW_MODE` 环境变量说明
2. ✅ 更新代码注释（标记 Shadow Mode 已完成）
3. ✅ 添加生产监控日志
4. ✅ 创建回滚脚本

**你需要做：**

1. 在 Railway Dashboard 删除 `SHADOW_MODE` 变量
2. 确认 `BUDGET_CONTROLLER_ENABLED=true`
3. 点击 "Redeploy"
4. 等待 2-3 分钟
5. 运行测试查询验证

---

## 📋 检查清单

发布前：
- [ ] Shadow Mode 验证完成（✅ 已完成）
- [ ] 所有指标通过（✅ 已完成）
- [ ] 回滚方案准备就绪
- [ ] 监控方案就绪

发布后：
- [ ] 禁用 SHADOW_MODE
- [ ] 启用 BUDGET_CONTROLLER_ENABLED
- [ ] 验证功能正常
- [ ] 监控错误日志
- [ ] 监控 performance
- [ ] 收集用户反馈

---

**你想采用哪个方案？**
- **方案 A**：简单开关（推荐，快速）
- **方案 B**：百分比控制（更安全，需要开发）
