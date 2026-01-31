# DriftCoach Demo (Integration Freeze)

Minimal usage for demo-ready, feature-frozen state.

## Quickstart (mock CLI)
- Install deps: `pip install -r requirements.txt`
- Run mock demo: `python3 -m driftcoach.main --explain`

## Run HTTP delivery shell (frozen contract)
- Start API: `./scripts/start_api.sh`
- Endpoint: `GET /api/demo`
- Contract: payload is identical to `frontend/mocks/demo.json`; no query/body params; no extra endpoints.

## Frontend data source switch (manual)
- Mock mode: import `frontend/mocks/demo.json`.
- API mode: fetch from `http://localhost:8000/api/demo`.
- UI, order (1 Insight → 2 Review → 3 What-if), Assumptions, and LLM toggle behaviors must remain unchanged between modes.

## Frontend LLM 语境解释层（冻结）
- 角色：解释器，仅将后端 Insight / Review / What-if 转成游戏语境文本；不新增事实、不改数值、不给建议。
- 渲染模式：
	- `off`：不输出解释文本。
	- `template`（默认）：纯模板解释，零 LLM。
	- `llm-contextual`：调用 OpenAI `gpt-4o`，失败/超时自动回退模板。
- 受控词汇 / Intent / Game Profile 实现在 `frontend/llm/*`。
- 环境变量：`VITE_OPENAI_API_KEY`（或 `OPENAI_API_KEY`）。未设置时自动用模板回退。
- Trace：解释附带 `explanationTrace`（intent、gameProfile、renderMode、sourceFields、fallbackUsed）。

## Run frontend (demo view)
- Install Node deps: `npm install`
- Dev server: `npm run dev` (Vite, serves at http://localhost:5173)
- Build: `npm run build`; Preview: `npm run preview`
- Frontend must consume the same payload as `frontend/mocks/demo.json` or `/api/demo`; no extra endpoints or params.

## Freeze rules (summary)
- Do not add endpoints/params or change payload.
- No new features or UI changes; only docs/presentation updates allowed.
- 前端 LLM 不得：读取 GRID 原始数据、修改数值、输出战术建议、聊天式输入、多轮对话。
