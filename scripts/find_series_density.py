"""
Central-Data Evidence Density Scanner (B-phase)

Design Principles:
- Central-data only (official fact universe)
- No assumption of outcome / rounds / timeline
- No illegal fields, no TLS disabling
- Rate-limit aware, low infra pressure
- Moneyball-style: density & contrast > completeness

This script is NOT a planner.
It is a safe evidence scanner to answer:
"Does central-data contain analyzable structure?"
"""

import os
import sys
import time
import datetime as dt
from typing import Dict, Any, List

import requests

# =========================================================
# Configuration (Frozen for B-phase)
# =========================================================

GRID_ENDPOINT = os.getenv(
    "GRID_GRAPHQL_URL",
    "https://api-op.grid.gg/central-data/graphql"
)
API_KEY = os.getenv("GRID_API_KEY")

if not API_KEY:
    print("ERROR: GRID_API_KEY is required", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json",
    "User-Agent": "DriftCoach/B-phase-evidence-scan"
}

# Infra safety limits
MAX_EDGES = 200          # absolute central-data safety cap
PAGE_SIZE = 50           # central-data typical safe page
ANCHOR_LIMIT = 25        # B-phase sample size (do NOT increase lightly)
RETRY = 3
BACKOFF_BASE = 2.0       # seconds
POOL_SLEEP = 0.4         # throttle between pool queries

# =========================================================
# GraphQL Queries (Safe Field Set Only)
# =========================================================

SERIES_FIELDS = """
    id
    startTimeScheduled
    tournament { name }
    format { nameShortened }
"""

SERIES_WINDOW_QUERY = f"""
query SeriesWindow($filter: SeriesFilter, $first: Int, $after: String) {{
  allSeries(filter: $filter, first: $first, after: $after) {{
    edges {{
      node {{
        {SERIES_FIELDS}
      }}
    }}
    pageInfo {{
      hasNextPage
      endCursor
    }}
  }}
}}
"""

POOL_QUERY = """
query SeriesPool($filter: SeriesFilter, $first: Int) {
  allSeries(filter: $filter, first: $first) {
    edges {
      node {
        id
        format { nameShortened }
      }
    }
  }
}
"""

# =========================================================
# Utilities
# =========================================================

def iso(dt_obj: dt.datetime) -> str:
    """UTC ISO8601 string, central-data safe"""
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=dt.timezone.utc)
    return (
        dt_obj.astimezone(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def safe_post(query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safe GraphQL POST:
    - TLS enabled
    - PERMISSION_DENIED is tolerated
    - UNAVAILABLE / rate limit => exponential backoff
    - Fatal schema errors fail fast
    """
    for attempt in range(RETRY):
        resp = requests.post(
            GRID_ENDPOINT,
            headers=HEADERS,
            json={"query": query, "variables": variables},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()

        errors = payload.get("errors") or []
        retryable = False
        fatal = []

        for e in errors:
            etype = e.get("extensions", {}).get("errorType")
            if etype == "UNAVAILABLE":
                retryable = True
            elif etype == "PERMISSION_DENIED":
                continue
            else:
                fatal.append(e)

        if fatal:
            raise RuntimeError(fatal)

        if retryable:
            sleep = BACKOFF_BASE * (attempt + 1)
            print(f"[RATE LIMIT] backing off {sleep:.1f}s")
            time.sleep(sleep)
            continue

        return payload.get("data") or {}

    raise RuntimeError("GRID API retry exhausted")


def bucket_counts(series: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Minimal contrast buckets for Moneyball reasoning
    """
    buckets = {"BO1": 0, "BO3": 0, "OTHER": 0}
    for s in series:
        fmt = ((s.get("format") or {}).get("nameShortened") or "").upper()
        if fmt == "BO1":
            buckets["BO1"] += 1
        elif fmt == "BO3":
            buckets["BO3"] += 1
        else:
            buckets["OTHER"] += 1
    return buckets

# =========================================================
# Main
# =========================================================

def main():
    now = dt.datetime.now(dt.timezone.utc)

    # -----------------------------------------------------
    # 1. Anchor window (bounded, no full-scan)
    # -----------------------------------------------------
    base_filter = {
        "startTimeScheduled": {
            "gte": iso(now - dt.timedelta(days=200)),
            "lte": iso(now + dt.timedelta(days=7)),
        }
    }

    anchors: List[Dict[str, Any]] = []
    after = None

    while True:
        data = safe_post(
            SERIES_WINDOW_QUERY,
            {"filter": base_filter, "first": PAGE_SIZE, "after": after},
        ).get("allSeries", {})

        edges = data.get("edges") or []
        for e in edges:
            node = e.get("node")
            if node:
                anchors.append(node)
                if len(anchors) >= MAX_EDGES:
                    break

        if len(anchors) >= MAX_EDGES:
            break

        page = data.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        after = page.get("endCursor")

    anchors = anchors[:ANCHOR_LIMIT]
    print(f"[BASE] anchor_series={len(anchors)}")

    # -----------------------------------------------------
    # 2. Pool density scan (single page per anchor)
    # -----------------------------------------------------
    results = []

    for idx, s in enumerate(anchors):
        start_raw = s.get("startTimeScheduled")
        if not start_raw:
            continue

        try:
            start_dt = dt.datetime.fromisoformat(
                start_raw.replace("Z", "+00:00")
            )
        except Exception:
            continue

        pool_filter = {
            "startTimeScheduled": {
                "gte": iso(start_dt - dt.timedelta(days=180)),
                "lte": iso(start_dt + dt.timedelta(days=180)),
            }
        }

        pdata = safe_post(
            POOL_QUERY,
            {"filter": pool_filter, "first": PAGE_SIZE},
        ).get("allSeries", {})

        edges = pdata.get("edges") or []
        pool = [e["node"] for e in edges if e.get("node")]

        results.append({
            "series_id": s.get("id"),
            "format": (s.get("format") or {}).get("nameShortened"),
            "tournament": (s.get("tournament") or {}).get("name"),
            "start": start_raw,
            "pool_size": len(pool),
            "buckets": bucket_counts(pool),
        })

        time.sleep(POOL_SLEEP)

    # -----------------------------------------------------
    # 3. Output signal candidates
    # -----------------------------------------------------
    low = sorted(
        [r for r in results if r["pool_size"] < 10],
        key=lambda x: x["pool_size"]
    )[:5]

    high = sorted(
        [r for r in results if r["pool_size"] >= 30],
        key=lambda x: -x["pool_size"]
    )[:5]

    print("\n=== Low density candidates (<10) ===")
    for r in low:
        print(r)

    print("\n=== High density candidates (>=30) ===")
    for r in high:
        print(r)


if __name__ == "__main__":
    main()