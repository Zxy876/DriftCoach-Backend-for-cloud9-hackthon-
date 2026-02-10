# Shadow Mode 验证指南

**目标**: 在 Railway 生产环境验证 BudgetController

**方法**: Shadow 模式（同时运行 WITH 和 WITHOUT，记录 metrics）

---

## 🚀 部署步骤（手动）

### Step 1: 设置环境变量

1. 访问 Railway Dashboard: https://dashboard.railway.app
2. 选择项目: `DriftCoach-Backend-for-cloud9-hackthon-`
3. 进入 "Variables" 标签
4. 添加新变量:
   - Name: `SHADOW_MODE`
   - Value: `true`

### Step 2: 触发重新部署

1. 在 Railway Dashboard 中点击 "Redeploy"
2. 等待 1-3 分钟直到状态变为 "Running"

### Step 3: 验证 Shadow Mode 已启用

运行测试查询：
```bash
python3 verify_shadow_mode.py
```

应该看到日志中包含：
```
🔍 SHADOW_MODE_ENABLED: Running both WITH and WITHOUT BudgetController
🔍 SHADOW_METRICS: {...}
```

---

## 📊 数据收集（15-30 分钟）

### 运行测试脚本

```bash
python3 collect_shadow_metrics.py
```

或手动发送请求：

```python
import requests

API_URL = "https://web-production-a92838.up.railway.app"
SERIES_ID = "2819676"

# Initialize
init = requests.post(f"{API_URL}/api/coach/init",
    json={"grid_series_id": SERIES_ID}).json()
session_id = init["session_id"]

# Send 100 queries
for i in range(100):
    resp = requests.post(f"{API_URL}/api/coach/query",
        json={
            "coach_query": "这是不是一场高风险对局？",
            "session_id": session_id,
            "series_id": SERIES_ID
        }
    )
    print(f"Query {i+1}/100")
    time.sleep(2)  # 2 seconds between queries
```

### 查看日志

在 Railway Dashboard -> Logs 中，搜索 `SHADOW_METRICS`：

```
🔍 SHADOW_METRICS: {
    "without_bc": {
        "facts_used": 3,
        "hrs": 2,
        "swings": 1
    },
    "with_bc": {
        "facts_used": 2,
        "hrs": 2,
        "swings": 0,
        "confidence": 0.9,
        "steps": 2,
        "stopped_early": true
    },
    "efficiency": {
        "facts_saved": 1
    }
}
```

---

## 📈 分析 3 个关键指标

### 指标 1: Facts 节省率

```
facts_saved = without_bc.facts_used - with_bc.facts_used
efficiency = facts_saved / without_bc.facts_used
```

**通过判据**: 平均节省率 > 20%

---

### 指标 2: Confidence 稳定性

```
confidence_stable = (with_bc.confidence >= 0.7)
```

**通过判据**: > 90% 的请求 confidence >= 0.7

---

### 指标 3: Verdict 一致性

```
verdict_consistent = (verdict_without == verdict_with)
```

**通过判据**: > 95% 的请求 verdict 一致

---

## ✅ 决策规则

### 如果满足所有 3 个通过判据

→ 切换到 `BUDGET_CONTROLLER_ENABLED=true`
→ 移除 `SHADOW_MODE`

### 如果不满足

→ 记录失败形态（CLRS 第五章的收获）
→ 回滚到 `BUDGET_CONTROLLER_ENABLED=false`
→ 分析失败原因并优化

---

## 🔧 Railway CLI 方法（可选）

如果安装了 Railway CLI：

```bash
npm install -g @railway/cli

# 设置环境变量
railway variables set SHADOW_MODE true

# 触发重新部署
railway up

# 查看日志
railway logs
```

---

## 📁 相关文件

- `driftcoach/analysis/intent_handlers.py` - Shadow mode 实现
- `deploy_shadow_mode.py` - 自动部署脚本
- `verify_shadow_mode.py` - 验证脚本
- `collect_shadow_metrics.py` - 数据收集脚本

---

## 🎯 成功标准

Shadow Mode 验证成功，如果：

1. ✅ 收集到 ≥100 个 SHADOW_METRICS 记录
2. ✅ Facts 节省率 > 20%
3. ✅ Confidence 稳定率 > 90%
4. ✅ Verdict 一致率 > 95%

满足所有条件 → 可以在生产环境启用 BudgetController
