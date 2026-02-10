#!/usr/bin/env python3
"""
Quick verification that Shadow Mode is enabled on Railway.
"""

import requests
import json

API_URL = "https://web-production-a92838.up.railway.app"
SERIES_ID = "2819676"

print("=" * 70)
print("🔍 Verifying Shadow Mode on Railway")
print("=" * 70)
print()

# Initialize
print("📥 Initializing session...")
init_resp = requests.post(f"{API_URL}/api/coach/init",
    json={"grid_series_id": SERIES_ID},
    headers={"Content-Type": "application/json"}
).json()
session_id = init_resp.get("session_id")
print(f"✅ Session: {session_id}")
print()

# Send query
print("📤 Sending query: \"这是不是一场高风险对局？\"")
query_resp = requests.post(f"{API_URL}/api/coach/query",
    json={
        "coach_query": "这是不是一场高风险对局？",
        "session_id": session_id,
        "series_id": SERIES_ID
    },
    headers={"Content-Type": "application/json"}
)

result = query_resp.json()
ans = result.get("answer_synthesis", {})

print()
print("📊 Response:")
print(f"   Claim: {ans.get('claim')}")
print(f"   Verdict: {ans.get('verdict')}")
print(f"   Confidence: {ans.get('confidence')}")
print(f"   Support facts: {len(ans.get('support_facts', []))}")
print()

print("=" * 70)
print("🔍 Shadow Mode Check")
print("=" * 70)
print()
print("✅ If Shadow Mode is enabled, you should see SHADOW_METRICS in Railway logs")
print()
print("To view logs:")
print("   1. Visit https://dashboard.railway.app")
print("   2. Select project: DriftCoach-Backend-for-cloud9-hackthon-")
print("   3. Click 'Logs' tab")
print("   4. Search for 'SHADOW_METRICS'")
print()
print("Expected log entry:")
print("   🔍 SHADOW_MODE_ENABLED: Running both WITH and WITHOUT BudgetController")
print("   🔍 SHADOW_METRICS: {...}")
