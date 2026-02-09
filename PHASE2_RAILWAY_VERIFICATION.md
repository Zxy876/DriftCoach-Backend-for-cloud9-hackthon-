# Phase 2 Railway 验证指南

## 🚀 当前状态

**Commit**: `6dfab83`
**状态**: ✅ 已推送到 GitHub
**等待**: Railway 自动重新部署（或手动触发）

---

## 🔧 Phase 2 实施内容

### **1. Spec Schema 实现**

**文件**: [driftcoach/specs/spec_schema.py](driftcoach/specs/spec_schema.py)

**核心类**：
- `Spec`: 4字段 schema（Focus, RequiredEvidence, Budget, OutputContract）
- `SpecFocus`: 6个 MVP spec（ECON, RISK, MAP, PLAYER, SUMMARY, MOMENTUM）
- `SpecRecognizer`: 从 intent 导出 spec，过滤 facts

**6 个 MVP Spec**：
1. **ECON_SPEC** - 经济分析（强起/保枪/经济崩盘）
2. **RISK_SPEC** - 风险评估（高风险序列/局势波动）
3. **MAP_SPEC** - 地图分析（点位控制/薄弱点）
4. **PLAYER_SPEC** - 球员分析（选手表现/影响）
5. **SUMMARY_SPEC** - 总结分析（全局回顾/总结）
6. **MOMENTUM_SPEC** - 动能分析（势能变化/阶段对比）

---

### **2. RiskAssessmentHandler 集成 RISK_SPEC**

**文件**: [driftcoach/analysis/intent_handlers.py](driftcoach/analysis/intent_handlers.py)

**修改**：
```python
# 只使用 RISK_SPEC 允许的 fact types
all_facts_by_type = {}
for fact_type in RISK_SPEC.required_evidence.primary_fact_types:
    all_facts_by_type[fact_type] = ctx.get_facts(fact_type)

# 应用 spec budget
max_facts = RISK_SPEC.budget.max_facts_per_type
hrs = all_facts_by_type.get("HIGH_RISK_SEQUENCE", [])[:max_facts]
swings = all_facts_by_type.get("ROUND_SWING", [])[:max_facts]
```

---

### **3. 三条 Query 对比测试**

**文件**: [tests/test_spec_visibility.py](tests/test_spec_visibility.py)

**测试结果**（本地验证通过）：

| Query | Intent | Spec | 看到的 Facts | 输出 |
|-------|--------|------|-------------|------|
| "这是不是一场高风险对局？" | RISK_ASSESSMENT | RISK | 5个 (HIGH_RISK_SEQUENCE, ROUND_SWING) | "这是一场高风险对局，检测到 2 个高风险序列" |
| "经济决策有什么问题？" | ECONOMIC_COUNTERFACTUAL | ECON | 5个 (FORCE_BUY_ROUND, ECO_COLLAPSE_SEQUENCE, ROUND_SWING) | "R3 强起决策可能放大了风险" |
| "这个选手表现如何？" | PLAYER_REVIEW | PLAYER | 4个 (HIGH_RISK_SEQUENCE, ROUND_SWING) | "缺少选手 X 的统计数据" |

**关键突破**：✅ 不同 query 看到不同的 facts 子空间

---

## 🚀 Railway 验证步骤

### **步骤 1：触发 Railway 重新部署**

**方式 A：Railway 控制台（推荐）**
1. 访问：https://dashboard.railway.app
2. 找到项目：`DriftCoach-Backend-for-cloud9-hackthon`
3. 点击 **"Redeploy"** 按钮
4. 等待 1-3 分钟

**方式 B：自动部署**
- 已推送 commit `6dfab83` 到 GitHub
- Railway 可能会自动检测并重新部署
- 如果没有，请使用方式 A

---

### **步骤 2：运行验证脚本**

部署完成后，运行：

```bash
cd "/Users/zxydediannao/ DriftCoach Backend"
./verify_phase2_railway.sh
```

---

### **步骤 3：验证输出**

**预期结果**：

#### **Query 1："这是不是一场高风险对局？"**

```
Intent: RISK_ASSESSMENT
输出: 这是一场高风险对局，检测到 2 个高风险序列
```

#### **Query 2："经济决策有什么问题？"**

```
Intent: ECONOMIC_COUNTERFACTUAL
输出: R3 强起决策可能放大了风险，保枪可能更优
```

#### **Query 3："这个选手表现如何？"**

```
Intent: PLAYER_REVIEW
输出: 选手 X 在 R5, R10 回合有突出表现
（或：缺少选手 X 的统计数据）
```

---

## 📊 对比：之前 vs 之后

### **之前（L3）**

```
所有 query 都看相同的 facts 池 → 输出相似 ❌

Query 1 (RISK):     → 看所有 facts → 输出 y
Query 2 (ECON):     → 看所有 facts → 输出 y（相似）
Query 3 (PLAYER):   → 看所有 facts → 输出 y（相似）
```

### **之后（L4）**

```
每个 spec 只看允许的 facts 子集 → 输出不同 ✅

Query 1 (RISK):     → 看 RISK 允许的 facts → 输出 y1
Query 2 (ECON):     → 看 ECON 允许的 facts → 输出 y2（不同）
Query 3 (PLAYER):   → 看 PLAYER 允许的 facts → 输出 y3（不同）
```

---

## ✅ 验证清单

部署完成后，检查以下项目：

- [ ] **Commit**: 验证最新 commit 是否为 `6dfab83`
- [ ] **Query 1**: 输出是否关注"高风险序列、局势反转"
- [ ] **Query 2**: 输出是否关注"强起决策、经济崩盘"
- [ ] **Query 3**: 输出是否关注"选手表现、贡献"
- [ ] **输出不同**: 三条 query 的输出是否明显不同

---

## 🔍 如果输出仍然相同

**可能原因**：
1. Railway 未重新部署（还在运行旧代码）
2. 代码缓存问题（需要完全重启）
3. Spec 配置未生效

**解决方法**：
1. 在 Railway 控制台点击 "Restart"（不只是 Redeploy）
2. 检查环境变量 `LOG_LEVEL` 是否设置为 `WARNING`
3. 查看 Railway 日志，确认使用了新代码

---

## 📝 相关文档

1. **[driftcoach/specs/spec_schema.py](driftcoach/specs/spec_schema.py)** - Spec 实现
2. **[driftcoach/analysis/intent_handlers.py](driftcoach/analysis/intent_handlers.py)** - Handler 集成
3. **[SPEC_DESIGN.md](SPEC_DESIGN.md)** - Spec 设计文档
4. **[SPEC_IMPLEMENTATION_SUMMARY.md](SPEC_IMPLEMENTATION_SUMMARY.md)** - 实施总结
5. **[tests/test_spec_visibility.py](tests/test_spec_visibility.py)** - 本地测试

---

## 🎯 预期效果

**从"不同问题输出一样"到"不同问题输出不同"**：

| 维度 | 之前（L3） | 之后（L4） |
|------|-----------|-----------|
| **Input Space** | 所有 query 看相同 facts 池 | 每个 spec 看不同的 facts 子空间 |
| **Output** | F(X1)=y, F(X2)=y（相似） | F_RISK(X1)=y1, F_ECON(X2)=y2（不同） |
| **n 定义** | 挖掘指令数（数量） | \|Specs(query)\| × budget_per_spec（带类型规模） |

---

## 💡 核心突破

**Spec 的本质**：
- 不是"接受/拒绝"（那是 GateOutcome）
- 而是"算什么、允许缺什么、上界是多少、输出形态是什么"

**Spec 的作用**：
- 收缩可见性（search space reduction）
- 让不同 query 看到不同的 facts 子集
- 解决 `F(X1)=y, F(X2)=y` 的问题

---

**状态**：✅ 代码已推送，等待 Railway 重新部署
**下一步**：在 Railway 控制台点击 "Redeploy" 按钮

---

**需要帮助？**
- 查看 Railway 部署日志
- 检查 commit 历史：`git log --oneline -5`
- 运行本地测试：`python3 tests/test_spec_visibility.py`
