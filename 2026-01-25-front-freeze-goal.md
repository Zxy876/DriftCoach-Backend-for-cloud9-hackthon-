DriftCoach — Frontend / Backend Integration Engineering Goal（Demo-Ready & Freeze）

本文件将联调冻结阶段转为可执行的工程目标、交付物与验收条目。完成后系统进入 Demo-Ready / No-New-Feature 状态。

⸻

0. 阶段定位（不可修改）
- 集成验证（Integration Verification），不是功能开发。CLI → HTTP：仅换输出通道，不改语义、不加能力。
- 目标：前端在不感知后端细节的前提下，稳定消费后端固定 Demo 输出。

⸻

1. 阶段目标（单一）
- 在不改分析逻辑、不扩 API、不接 GRID 的前提下，完成：
  1) 后端通过 HTTP 暴露固定 Demo 结果。
  2) 前端通过 HTTP 获取并完整渲染。
  3) 前端可在 Mock JSON / API 响应间无缝切换。
  4) 切换前后行为、语义、边界完全一致。

⸻

2. 范围与禁区（Scope Guard）
- 允许：开启 FastAPI/Uvicorn；新增只读 Demo API；返回固定结构结果；前端仅切换数据源。
- 禁止：新增分析方法/参数；搜索/筛选/自由输入；LLM 接入 API；改动前端展示语义或 Demo 顺序；接入真实 GRID；“顺手加一个参数”。

⸻

3. API 契约（冻结）
- Endpoint：`GET /api/demo`（无 query/body）。
- 响应结构（字段级同 `frontend/mocks/demo.json`）：
```
{
  "context": {...},
  "insights": [...],
  "review": [...],
  "whatIf": {...}
}
```
- 要求：字段名与语义一致；不增删字段；不返回 State/Transition/DerivedFact 细节。

⸻

4. 后端实现约束
- FastAPI 仅作 Delivery Shell；可直接返回 demo.json 或调用现有分析内核生成同构结果。
- 不得新建分析路径、不得引入请求参数、不得在 API 层做计算或判定。

⸻

5. 前端集成约束
- Mock 与 API 仅切换数据源，UI/渲染/解释层行为不变；保持顺序 1 Insight → 2 Review → 3 What-if；Assumptions 常显。
- 禁止因 API 接入修改结构；不加聊天/实时语义；loading/retry 仅最小 fallback。

⸻

6. 交付物（工程落地）
- 后端：`/api/demo` 返回与 `frontend/mocks/demo.json` 同构 JSON；uvicorn 可启动。
- 前端：数据源切换开关（mock/api）；使用 API 时渲染结果与 mock 模式一致；Assumptions & Limits 常显；renderMode (off/template/llm) 行为不变。
- 文档：README 增补“Integration freeze”声明与 API 契约；说明禁止项。

⸻

7. 验收清单（DoD）
- 后端：`/api/demo` 200，payload 同构，零参数；本地启动脚本可一键跑通。
- 前端：切换为 API 模式后，页面输出与 mock 模式字段和值一致；顺序与 Assumptions 均保持；LLM 开关与回退如前。
- 系统级：无新功能、无聊天/推荐/agent 语义；3 分钟内可讲清 Demo。

⸻

8. 冻结条件
- 以上 DoD 全部通过即冻结：
  - ❌ 不再新增 API / 请求参数
  - ❌ 不改前端组件结构或文案
  - 仅允许文档、讲稿、Q&A 预案补充

⸻

9. 失败判定（越界信号）
- 前端因 API 接入“需要重构”；API 响应与 mock 不同构；需要新增参数才能“合理”；数据源切换导致行为差异。

⸻

10. README 声明（建议落地）
- 追加段落：已完成前后端联调，系统 Demo-ready & feature-frozen；后续仅限文档/呈现。记录 `/api/demo` 契约与禁止事项。

 