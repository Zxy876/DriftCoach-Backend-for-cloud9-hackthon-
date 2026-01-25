"""
FastAPI delivery shell exposing demo payload at GET /api/demo.
- No query/body params.
- Returns JSON structure aligned with frontend/mocks/demo.json.
- Does not alter analysis semantics or add logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException

app = FastAPI(title="DriftCoach Demo API", version="0.1")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEMO_PATH = ROOT / "frontend" / "mocks" / "demo.json"


def load_demo_payload(path: Path = DEFAULT_DEMO_PATH) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Demo payload not found at {path}")
    import json

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/demo")
def get_demo() -> Dict[str, Any]:
    try:
        return load_demo_payload()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Failed to load demo payload") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("driftcoach.api:app", host="0.0.0.0", port=8000, reload=True)
