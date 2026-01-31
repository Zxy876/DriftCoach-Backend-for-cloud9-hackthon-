 

DriftCoach — GRID API Adapter Engineering Goal（Freeze-Safe）

本文件定义 GRID API 接入阶段 的工程目标、边界与验收标准。
目标是在 不破坏现有分析系统与前端 的前提下，用真实 GRID 数据替换 mock 事实来源。

⸻

0. 阶段定位（冻结，不得修改）
	•	本阶段仅实现 事实输入替换（Fact Source Swap）
	•	GRID API 是 只读数据源
	•	不引入任何新分析能力、UI 交互或推理逻辑

核心原则：Analysis 不知道 GRID 的存在

⸻

1. 阶段目标（Goal）

在不改动以下模块的前提下：
	•	❌ Analysis Runtime
	•	❌ ML 模块
	•	❌ LLM Renderer
	•	❌ Frontend UI / Contract

完成：
	1.	从 GRID API 拉取真实比赛数据
	2.	将 GRID 数据转换为内部 State 序列
	3.	使用现有分析内核生成三类输出
	4.	通过既有 GET /api/demo 暴露结果
	5.	前端无需任何改动即可展示真实数据

⸻

2. Scope Guard（严格禁止）

禁止事项（写入代码注释）
	•	❌ 在 Adapter 中 import analysis / ml / llm
	•	❌ 在 Adapter 中计算胜率、概率或结论
	•	❌ 在 API 层新增 query 参数
	•	❌ 直接向前端返回 GRID 原始字段
	•	❌ 为“用起来更方便”修改 State schema

⸻

3. 架构约束（冻结）

GRID API
   ↓
[ adapters/grid ]        ← 本阶段唯一新增
   ↓
State Builder
   ↓
Analysis Runtime
   ↓
Outputs
   ↓
FastAPI /api/demo
   ↓
Frontend


⸻

4. Adapter 职责划分（必须遵守）

Adapter 层只做三件事：
	1.	请求：GraphQL 拉数据（client）
	2.	聚合：整理 series / stats（fetch）
	3.	映射：GRID → State（to_state）

⸻

5. 最小支持用例（Demo 级）

仅需支持：
	•	已结束的 Series
	•	单一 Team 或 Player
	•	固定时间窗（如 last N rounds）

❌ 不要求：
	•	Live series
	•	多赛季
	•	多 tournament 聚合

⸻

6. 输出契约（冻结）

Adapter 的 唯一合法输出：

list[State]

State schema 完全复用现有定义。

⸻

7. 集成方式（唯一允许）

在 api.py / main.py：

if DATA_SOURCE == "grid":
    states = load_states_from_grid(...)
else:
    states = load_states_from_fixtures(...)


⸻

8. 验收标准（DoD）
	•	Adapter 层不 import analysis / ml / llm
	•	使用真实 GRID 数据可生成 State 列表
	•	GET /api/demo 返回结构不变
	•	前端无需改动即可展示真实数据
	•	mock / grid 切换不影响 UI 语义

⸻

9. 冻结声明

本阶段完成后：
	•	❌ 不再新增 GRID 字段
	•	❌ 不扩展 Adapter 责任
	•	仅允许：
	•	文档补充
	•	Demo 讲解优化

⸻

⸻

🧩 adapters/grid/ 完整 Stub 代码（可直接落地）

以下是 最小但正确 的 GRID Adapter 骨架
所有 TODO 都是唯一允许填充的地方

⸻

目录结构（冻结）

driftcoach/
└── adapters/
    └── grid/
        ├── __init__.py
        ├── client.py
        ├── fetch.py
        └── to_state.py


⸻

adapters/grid/client.py

import requests
from typing import Dict, Any


GRID_ENDPOINT = "https://api.grid.gg/graphql"


class GridClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def run_query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Pure IO: run GraphQL query, return raw JSON."""
        resp = requests.post(
            GRID_ENDPOINT,
            json={"query": query, "variables": variables},
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

⚠️ 规则：
	•	不解析字段
	•	不做 fallback
	•	不 catch 业务异常

⸻

adapters/grid/fetch.py

from typing import Dict, Any
from .client import GridClient


class GridFetcher:
    def __init__(self, client: GridClient):
        self.client = client

    def fetch_series(self, series_id: str) -> Dict[str, Any]:
        """Fetch minimal series info (finished match)."""
        query = """
        query GetSeries($id: ID!) {
          series(id: $id) {
            id
            format { name }
            startTimeScheduled
            teams { baseInfo { name } }
          }
        }
        """
        return self.client.run_query(query, {"id": series_id})

    def fetch_player_stats(self, player_id: str) -> Dict[str, Any]:
        query = """
        query PlayerStats($id: ID!) {
          playerStatistics(playerId: $id, filter: { timeWindow: LAST_3_MONTHS }) {
            game { count }
            series { count }
          }
        }
        """
        return self.client.run_query(query, {"id": player_id})


⸻

adapters/grid/to_state.py

from typing import List, Dict, Any
from driftcoach.core.state import State


def series_to_states(
    series_payload: Dict[str, Any],
    stats_payload: Dict[str, Any],
) -> List[State]:
    """
    Convert GRID series + stats into internal State list.

    NOTE:
    - This is a lossy, coarse mapping by design.
    - Do NOT attempt full replay reconstruction.
    """

    states: List[State] = []

    # TODO: replace mock logic with simple derived buckets
    for idx in range(10):  # demo window
        states.append(
            State(
                state_id=f"S_{idx:03d}",
                map="Ascent",
                timestamp=idx * 2.0,
                score_diff=0,
                econ_diff=0,
                alive_diff=0,
                phase="MID_GAME",
            )
        )

    return states

⚠️ 重要注释建议保留：

# Adapter layer intentionally performs lossy mapping.
# Precision is less important than stability & auditability.


⸻

集成示例（api.py）

from driftcoach.adapters.grid.client import GridClient
from driftcoach.adapters.grid.fetch import GridFetcher
from driftcoach.adapters.grid.to_state import series_to_states

def load_states_from_grid():
    client = GridClient(api_key=GRID_API_KEY)
    fetcher = GridFetcher(client)

    series = fetcher.fetch_series(SERIES_ID)
    stats = fetcher.fetch_player_stats(PLAYER_ID)

    return series_to_states(series, stats)


 