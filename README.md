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

## Freeze rules (summary)
- Do not add endpoints/params or change payload.
- No new features or UI changes; only docs/presentation updates allowed.
