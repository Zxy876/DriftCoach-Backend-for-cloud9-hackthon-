# Phase 2 快速参考

## 🎯 核心目标

解决"不同问题输出一样"的问题：从"全局 facts 池"到"Spec 收缩的 facts 子空间"

---

## 📊 三条 Query 对比（本地验证）

| Query | Intent | Spec | 看到的 Facts | 输出 |
|-------|--------|------|-------------|------|
| "这是不是一场高风险对局？" | RISK_ASSESSMENT | RISK | 5个 (HIGH_RISK_SEQUENCE×2, ROUND_SWING×3) | "这是一场高风险对局，检测到 2 个高风险序列" |
| "经济决策有什么问题？" | ECONOMIC_COUNTERFACTUAL | ECON | 5个 (FORCE_BUY_ROUND, ECO_COLLAPSE_SEQUENCE, ROUND_SWING×3) | "R3 强起决策可能放大了风险" |
| "这个选手表现如何？" | PLAYER_REVIEW | PLAYER | 4个 (HIGH_RISK_SEQUENCE×2, ROUND_SWING×2) | "缺少选手 X 的统计数据" |

**关键证明**：✅ 不同 spec 看到不同的 facts → 输出不同

---

## 🔧 实施的修改

### **文件 1: driftcoach/specs/spec_schema.py**（新增）
- Spec 4字段 schema
- 6 个 MVP Spec 定义
- SpecRecognizer（intent → spec, filter_facts_by_spec）

### **文件 2: driftcoach/analysis/intent_handlers.py**（修改）
- RiskAssessmentHandler 集成 RISK_SPEC
- 只使用 RISK_SPEC 允许的 fact types
- 应用 RISK_SPEC.budget 限制

### **文件 3: tests/test_spec_visibility.py**（新增）
- 三条 query 对比测试
- 验证可见性收缩成功

---

## 🚀 Railway 验证步骤

### **1. 触发重新部署**
```
访问: https://dashboard.railway.app
找到: DriftCoach-Backend-for-cloud9-hackthon
点击: Redeploy
等待: 1-3 分钟
```

### **2. 运行验证脚本**
```bash
cd "/Users/zxydediannao/ DriftCoach Backend"
./verify_phase2_railway.sh
```

### **3. 检查输出**
```
Query 1 (RISK):     → 应输出"这是一场高风险对局..."
Query 2 (ECON):     → 应输出"R3 强起决策可能放大了风险..."
Query 3 (PLAYER):   → 应输出"选手 X 在 R5, R10 回合有突出表现..."
```

---

## ✅ 验证清单

- [ ] Railway 已重新部署（commit `6dfab83`）
- [ ] Query 1 输出关注"高风险序列、局势反转"
- [ ] Query 2 输出关注"强起决策、经济崩盘"
- [ ] Query 3 输出关注"选手表现、贡献"
- [ ] 三条 query 的输出明显不同

---

## 📁 新增文件

1. [driftcoach/specs/spec_schema.py](driftcoach/specs/spec_schema.py) - Spec 实现
2. [tests/test_spec.py](tests/test_spec.py) - Spec 单元测试
3. [tests/test_spec_visibility.py](tests/test_spec_visibility.py) - 三条 query 对比测试
4. [SPEC_DESIGN.md](SPEC_DESIGN.md) - Spec 设计文档
5. [SPEC_IMPLEMENTATION_SUMMARY.md](SPEC_IMPLEMENTATION_SUMMARY.md) - 实施总结
6. [verify_phase2_railway.sh](verify_phase2_railway.sh) - Railway 验证脚本
7. [PHASE2_RAILWAY_VERIFICATION.md](PHASE2_RAILWAY_VERIFICATION.md) - 验证指南

---

## 💡 核心洞察

### **从"数量"到"带类型的规模"**

```
L3: n = 挖掘指令数
    → 都在全局 facts 池捞 → F(X1)=y, F(X2)=y ❌

L4: n = |Specs(query)| × budget_per_spec
    → Spec 收缩可见性 → F_RISK(X1)=y1, F_ECON(X2)=y2 ✅
```

### **Spec vs GateOutcome**

- ❌ ACCEPT/LOW/REJECT 不是 Spec
- ✅ ACCEPT/LOW/REJECT 是 GateOutcome（门控决策结果）
- ✅ Spec 是"算什么、允许缺什么、上界是多少、输出形态是什么"

---

## 📊 Master Theorem 版本

```
T(query) = Σ_{spec ∈ Specs(query)} T(spec) + O(1)

其中：
- |Specs(query)| ≤ k（max_sub_intents = 3）
- T(spec) 的输入空间被 spec 收缩（只有允许的 facts）
- O(1) = route + combine + persist（常数时间）
```

---

**状态**：✅ Phase 2（最小实施）完成，代码已推送
**下一步**：等待 Railway 重新部署，然后验证效果

---

**Commit**: 6dfab83
**日期**: 2025-02-08
**目标**: 验证 Spec 收缩可见性在 Railway 的效果
