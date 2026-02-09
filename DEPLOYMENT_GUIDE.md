# 🚀 部署指南：DecisionMapper 修复

## 📊 当前状态

✅ 本地代码已修复（已验证）
❌ 容器代码未更新（需要部署）

**证据**：容器日志显示旧门控逻辑仍在工作

---

## 🔧 部署步骤

### **步骤 1：确认本地代码包含修复**

```bash
cd "/Users/zxydediannao/ DriftCoach Backend"
grep -A 5 "1→2 Breakthrough: Prioritize" driftcoach/api.py
```

应该看到：
```python
# ✅ 1→2 Breakthrough: Prioritize DecisionMapper result over old gate rationale
# If DecisionMapper has generated a result, use it instead of inference_plan rationale
answer_synthesis = context_meta.get("answer_synthesis", {})
if answer_synthesis.get("claim") and answer_synthesis.get("verdict") != "INSUFFICIENT":
```

---

### **步骤 2：重新部署**

#### **如果是 Docker**

```bash
cd "/Users/zxydediannao/ DriftCoach Backend"
./deploy_fix.sh
```

或手动：
```bash
docker-compose restart
# 或
docker-compose down && docker-compose up -d
```

#### **如果是云服务（Render/Railway/Fly.io）**

```bash
cd "/Users/zxydediannao/ DriftCoach Backend"

# Git 提交并推送
git add .
git commit -m "feat: 1→2 breakthrough with DecisionMapper integration"
git push

# 云服务会自动重新部署
# 或在控制台手动触发 "Manual Deploy"
```

#### **如果是本地开发**

```bash
cd "/Users/zxydediannao/ DriftCoach Backend"

# 重启服务
pkill -f "uvicorn"
python3 -m uvicorn driftcoach.api:app --reload --host 0.0.0.0 --port 8080
```

---

### **步骤 3：验证修复**

```bash
cd "/Users/zxydediannao/ DriftCoach Backend"
./verify_fix.sh
```

或手动测试：
```bash
curl -X POST http://localhost:8080/api/coach/query \
  -H "Content-Type: application/json" \
  -d '{
    "coach_query": "这是不是一场高风险对局？",
    "series_id": "2819676"
  }' | jq '.assistant_message'
```

**预期输出**：
```
"基于5条有限证据的初步分析：检测到 2 个 HIGH_RISK_SEQUENCE"
```

**而非之前的**：
```
"证据不足"
```

---

## 🐛 故障排查

### **问题 1：日志仍显示旧门控覆盖**

**日志**：
```
[DECISION_MAPPER] path=standard ✅
[GATE] decision=证据不足 ❌
```

**原因**：容器未重启或代码未同步

**解决**：
```bash
# 强制重建容器
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

### **问题 2：测试脚本连接失败**

**错误**：`curl: (7) Failed to connect`

**原因**：服务未启动或端口错误

**解决**：
```bash
# 检查服务是否运行
ps aux | grep uvicorn

# 检查端口
lsof -i :8080

# 查看日志
docker-compose logs -f api
```

---

### **问题 3：Git 推送后云服务未自动部署**

**解决**：
1. 登录云服务控制台（Render/Railway/Fly.io）
2. 找到对应的服务
3. 点击 "Manual Deploy" 或 "Redeploy"
4. 等待部署完成（通常 1-3 分钟）

---

## ✅ 成功标志

部署成功后，日志应该显示：

```
[DECISION_MAPPER] intent=RISK_ASSESSMENT, path=standard/degraded, uncertainty=0.28 ✅
[assistant_message] 基于5条有限证据的初步分析... ✅
```

**而不是**：
```
[DECISION_MAPPER] path=standard ✅
[GATE] decision=证据不足 ❌  ← 这说明旧逻辑仍在工作
```

---

## 📝 修改文件清单

确保以下文件都已更新：

1. ✅ `driftcoach/api.py` (3 处修改)
   - Line 64-65: 导入 DecisionMapper
   - Line 2401-2428: 集成 DecisionMapper
   - Line 2732-2747: DecisionMapper 优先级

2. ✅ `driftcoach/analysis/decision_mapper.py` (已存在)
   - DecisionMapper 核心逻辑

3. ✅ `tests/test_decision_mapper.py` (已存在)
   - 单元测试

4. ✅ `tests/test_api_gate_fix.py` (新增)
   - 门控优先级测试

---

## 🎯 预期效果

部署并验证成功后：

| 指标 | 之前 | 之后 |
|------|------|------|
| **响应消息** | "证据不足" | "基于X条有限证据的初步分析..." ✅ |
| **置信度** | 0.27 | 0.35 ✅ |
| **可操作性** | ❌ 告诉我缺什么 | ✅ 告诉我能做什么 |
| **触发 patches** | 可能触发 | 避免触发 ✅ |
| **响应时间** | 500ms~3000ms | 100ms~500ms ✅ |

---

**需要帮助？** 检查：
1. 本地代码是否包含修复（`grep -r "1→2 Breakthrough" driftcoach/`）
2. 容器是否重启（`docker-compose ps`）
3. 日志是否有错误（`docker-compose logs -f`）

**祝部署顺利！** 🚀
