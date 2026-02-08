#!/usr/bin/env python3
"""Quick test for Railway DecisionMapper fix"""

import requests
import json

API_URL = "https://web-production-a92838.up.railway.app"
SERIES_ID = "2819676"
QUERY = "这是不是一场高风险对局？"

print("="*70)
print("🧪 Testing Railway DecisionMapper Fix")
print("="*70)
print()

# Step 1: Init
print("🔄 Step 1: Initializing context...")
init_response = requests.post(
    f"{API_URL}/api/coach/init",
    json={"grid_series_id": SERIES_ID}
)
init_data = init_response.json()
session_id = init_data.get("session_id")
print(f"✅ Context initialized (session_id: {session_id})")
print()

# Step 2: Query
print("🔄 Step 2: Sending query...")
query_response = requests.post(
    f"{API_URL}/api/coach/query",
    json={
        "coach_query": QUERY,
        "session_id": session_id,
        "series_id": SERIES_ID
    }
)

result = query_response.json()
assistant_message = result.get("assistant_message", "")

print()
print("="*70)
print("📊 Result Analysis")
print("="*70)
print()
print(f"💬 Assistant Message:")
print(f"   {assistant_message}")
print()

# Check result
if "证据不足" in assistant_message:
    print("❌ FAILED: Still using old gate logic")
    print("   Message contains '证据不足'")
    print()
    print("🔧 Next steps:")
    print("   1. Railway needs to redeploy")
    print("   2. Visit: https://dashboard.railway.app")
    print("   3. Find DriftCoach-Backend project")
    print("   4. Click 'Redeploy' button")
    print()
    print("   Or run: ./trigger_railway_redeploy.sh")
    exit(1)
elif "基于" in assistant_message and "证据" in assistant_message:
    print("✅ SUCCESS: DecisionMapper is working!")
    print("   Message contains '基于X条证据'")
    print()
    print("🎉 1→2 Breakthrough Complete!")
    print()
    print("📊 Improvement:")
    print(f"   Before: 证据不足 (confidence=0.27)")
    print(f"   After: {assistant_message[:60]}...")
    exit(0)
else:
    print("⚠️  UNKNOWN: Cannot determine")
    print(f"   Message: {assistant_message}")
    exit(2)
