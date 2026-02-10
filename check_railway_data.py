#!/usr/bin/env python3
"""
Check what facts Railway is actually returning
"""
import requests
import json

API_URL = "https://web-production-a92838.up.railway.app"
SERIES_ID = "2819676"

print("=" * 70)
print("🔍 Checking Railway facts data")
print("=" * 70)
print()

# Step 1: Initialize
print("Step 1: Initialize context...")
init_result = requests.post(f"{API_URL}/api/coach/init",
    json={"grid_series_id": SERIES_ID},
    headers={"Content-Type": "application/json"}
).json()

session_id = init_result.get("session_id")
print(f"✅ Session: {session_id}")
print()

# Step 2: Send query and get full response
print("Step 2: Send query and inspect facts...")
query_result = requests.post(f"{API_URL}/api/coach/query",
    json={
        "coach_query": "这是不是一场高风险对局？",
        "session_id": session_id,
        "series_id": SERIES_ID
    },
    headers={"Content-Type": "application/json"}
).json()

# Extract answer_synthesis
answer_synthesis = query_result.get("answer_synthesis")
if answer_synthesis:
    print("✅ Found answer_synthesis:")
    print(json.dumps(answer_synthesis, indent=2, ensure_ascii=False))
else:
    print("❌ No answer_synthesis found")

# Extract context.meta.answer_synthesis
meta_ans = query_result.get("context", {}).get("meta", {}).get("answer_synthesis")
if meta_ans:
    print("\n✅ Found context.meta.answer_synthesis:")
    print(json.dumps(meta_ans, indent=2, ensure_ascii=False))
else:
    print("\n❌ No context.meta.answer_synthesis found")

# Extract evidence
evidence = query_result.get("context", {}).get("evidence", {})
print("\n📊 Evidence summary:")
print(f"  States count: {evidence.get('states', 0)}")
print(f"  Series pool: {evidence.get('seriesPool', 0)}")
print(f"  By type: {list(evidence.get('byType', {}).keys())}")

# Extract hackathon_evidence
hack_ev = query_result.get("context", {}).get("hackathon_evidence", [])
print(f"\n📁 Hackathon evidence: {len(hack_ev)} items")
if hack_ev:
    fact_types = {}
    for e in hack_ev:
        ft = e.get("fact_type") or e.get("type") or "unknown"
        fact_types[ft] = fact_types.get(ft, 0) + 1
    print(f"  Types: {fact_types}")

print()
print("=" * 70)
print("🎯 Diagnosis:")
print("=" * 70)

if not answer_synthesis and not meta_ans:
    print("❌ No answer_synthesis found - handlers may not be executing")
elif answer_synthesis and answer_synthesis.get("verdict") == "INSUFFICIENT":
    print("⚠️  Handlers executed but returned INSUFFICIENT")
    print("   → This means facts are empty, not a code bug")
else:
    print("✅ Handlers executed and returned a result")

# Check if facts are actually empty
if evidence.get("states", 0) == 0 and evidence.get("seriesPool", 0) == 0:
    print("\n🔴 ROOT CAUSE: No facts available for this series")
    print("   → Try a different series_id with actual data")
else:
    print("\n✅ Facts are available, issue may be in handler logic")
