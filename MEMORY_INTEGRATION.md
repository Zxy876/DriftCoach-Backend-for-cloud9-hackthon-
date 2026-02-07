# Memory & Bounds Integration

## ✅ 已完成的集成

### 1️⃣ 记忆层（Memory Layer）

**位置**: `driftcoach/memory/`

**功能**:
- 存储分析发现（DerivedFindings）
- 存储查询记录（Query → Findings 映射）
- 存储门控决策（Gate Decisions）- 为未来学习准备

**数据库**: SQLite (`driftcoach_memory.db`)

**表结构**:
```sql
findings (
    finding_id, session_id, intent, fact_type,
    content, confidence, created_at, series_id, player_id
)

gate_decisions (
    decision_id, session_id, intent, decision, confidence,
    metrics, rationale, created_at
)

queries (
    query_id, session_id, query_text, intent, findings_ids,
    created_at, series_id, player_id
)
```

---

### 4️⃣ 主流程集成

**位置**: `driftcoach/api.py`

**集成点**:

1. **Hackathon 查询流程** (`/api/coach/query`)
   - 在 `synthesize_answer()` 后自动存储 findings
   - 存储查询记录（query + findings 映射）
   - 应用硬上界约束

2. **Narrative Orchestration**
   - 传递 `bounds=DEFAULT_BOUNDS` 限制子意图数量
   - 每个意图最多 2 个 findings

3. **新增 API 端点**
   - `GET /api/coach/memory` - 查询历史记忆
   - `GET /api/health` - 显示系统状态（包含记忆和上界信息）

---

## 🔧 硬上界配置

**位置**: `driftcoach/config/bounds.py`

**当前约束**:
```python
max_sub_intents = 3              # 每个查询最多 3 个子意图
max_findings_per_intent = 2      # 每意图最多 2 个发现
max_findings_total = 5           # 总共最多 5 个发现
max_support_facts = 3            # 最多 3 个支撑事实
max_counter_facts = 3            # 最多 3 个反例
max_followup_questions = 3       # 最多 3 个追问
```

---

## 📊 使用示例

### 查询历史记忆

```bash
# 获取特定 session 的所有 findings
curl "http://localhost:8000/api/coach/memory?session_id=xxx"

# 获取特定 intent 的历史 findings
curl "http://localhost:8000/api/coach/memory?intent=RISK_ASSESSMENT&limit=5"

# 检查系统状态
curl "http://localhost:8000/api/health"
```

### 响应示例

```json
{
  "status": "ok",
  "findings": [
    {
      "finding_id": "uuid-1",
      "session_id": "session-123",
      "intent": "RISK_ASSESSMENT",
      "fact_type": "HIGH_RISK_SEQUENCE",
      "confidence": 0.9,
      "created_at": "2026-02-07T10:30:00",
      "series_id": "2819676",
      "content": {"round_range": [1, 3], "note": "经济崩盘"}
    }
  ],
  "gate_stats": {
    "historical_hit_rate": 0.85,
    "recent_failure_rate": 0.10,
    "total_decisions": 20
  },
  "count": 1
}
```

---

## 🚦 系统状态

```bash
$ curl http://localhost:8000/api/health
{
  "status": "ok",
  "data_source": "grid",
  "demo_mode": false,
  "demo_series_id": "2819676",
  "memory_enabled": true,      # ✅ 记忆层已启用
  "bounds_enforced": true       # ✅ 硬上界已强制执行
}
```

---

## ⚙️ 环境变量

无需额外配置，系统会自动：
- 创建 `driftcoach_memory.db` SQLite 数据库
- 在每次查询时存储 findings 和 queries
- 应用硬上界约束

---

## 📝 数据持久化

**自动触发**:
- 每次调用 `/api/coach/query` 时自动存储
- 无法手动禁用（可修改代码移除存储逻辑）

**数据清理**:
```python
# 清空特定 session
memory_store.clear_session(session_id)

# 或者直接删除数据库文件
rm driftcoach_memory.db
```

---

## 🔮 未来扩展

### 从 SQLite 迁移到 Redis

```python
# driftcoach/api.py
from driftcoach.memory.store import MemoryStore

# 当前：SQLite
_memory_store = MemoryStore(db_path="driftcoach_memory.db")

# 未来：Redis（需要实现 RedisMemoryStore）
# from driftcoach.memory.redis_store import RedisMemoryStore
# _memory_store = RedisMemoryStore(host="localhost", port=6379)
```

### 启用概率化 Gate（当前未集成）

```python
# 当前：使用旧的硬编码 gate
from driftcoach.llm.orchestrator import evidence_gate

# 未来：使用概率化 gate（带历史学习）
from driftcoach.memory.integration import MemoryEnhancedOrchestrator

orchestrator = MemoryEnhancedOrchestrator(store=_memory_store)
result = orchestrator.orchestrate_query(...)
```

---

## 📂 文件清单

**新增文件**:
```
driftcoach/
├── config/
│   └── bounds.py                    # 硬上界配置
├── llm/
│   └── probabilistic_gate.py        # 概率化 Gate（未启用）
└── memory/
    ├── store.py                     # SQLite 存储
    └── integration.py               # 记忆集成层（未启用）

tests/
├── test_probabilistic_gate.py       # Gate 测试
└── test_memory_store.py             # 记忆层测试

driftcoach_memory.db                 # SQLite 数据库（运行时创建）
```

**修改文件**:
```
driftcoach/
├── api.py                           # ✅ 集成记忆层 + 硬上界
├── llm/orchestrator.py              # ✅ 添加概率化 gate wrapper（向后兼容）
├── narrative/orchestration.py       # ✅ 应用硬上界
└── analysis/answer_synthesizer.py   # ✅ 应用硬上界
```

---

## ⚠️ 注意事项

1. **Gate 决策逻辑未改变**：仍使用旧的硬编码阈值（`states_count < 20`）
2. **概率化 Gate 已实现但未启用**：在 `driftcoach/llm/probabilistic_gate.py`
3. **硬上界已强制执行**：在 `synthesize_answer()` 和 `run_narrative_orchestration()` 中
4. **记忆层已启用**：每次 Hackathon 查询都会自动存储

---

## 🎯 效果对比

### 修复前
```
Query → analyze() → [unlimited findings] → Response
        ↑
        每次冷启动，无历史
```

### 修复后
```
Query → analyze() → [max 5 findings] → Response
        ↓                      ↓
    load history          store to DB
    (future)              (current)
```

---

## 🧪 测试

```bash
# 测试记忆层
python3 tests/test_memory_store.py

# 测试概率化 Gate（未集成）
PYTHONPATH="/Users/zxydediannao/ DriftCoach Backend" \
    python3 tests/test_probabilistic_gate.py

# 启动服务器
python3 -m driftcoach.api
```

---

**总结**：记忆层和硬上界已完全集成到主流程，系统现在会：
- ✅ 存储所有查询和 findings
- ✅ 强制执行硬上界约束
- ⚠️ Gate 决策仍使用旧逻辑（待后续升级）
