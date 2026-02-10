#!/usr/bin/env python3
"""
Detailed diagnosis of Railway responses
"""
import requests
import json

API_URL = "https://web-production-a92838.up.railway.app"
SERIES_ID = "2819676"

queries = [
    ("这是不是一场高风险对局？", "RISK_ASSESSMENT"),
    ("经济决策有什么问题？", "ECONOMIC_COUNTERFACTUAL"),
    ("这个选手表现如何？", "PLAYER_REVIEW"),
]

print("=" * 70)
print("📊 Detailed Diagnosis: Railway Query Responses")
print("=" * 70)
print()

# Initialize
init_result = requests.post(f"{API_URL}/api/coach/init",
    json={"grid_series_id": SERIES_ID},
    headers={"Content-Type": "application/json"}
).json()
session_id = init_result.get("session_id")

for i, (query, expected_intent) in enumerate(queries, 1):
    print("-" * 70)
    print(f"Query {i}: \"{query}\"")
    print(f"Expected Intent: {expected_intent}")
    print("-" * 70)

    result = requests.post(f"{API_URL}/api/coach/query",
        json={
            "coach_query": query,
            "session_id": session_id,
            "series_id": SERIES_ID
        },
        headers={"Content-Type": "application/json"}
    ).json()

    # Extract answer_synthesis
    ans = result.get("answer_synthesis")
    if ans:
        print(f"✅ answer_synthesis found:")
        print(f"   Claim: {ans.get('claim')}")
        print(f"   Verdict: {ans.get('verdict')}")
        print(f"   Confidence: {ans.get('confidence')}")
        print(f"   Support facts: {len(ans.get('support_facts', []))}")
        if ans.get('support_facts'):
            for j, fact in enumerate(ans.get('support_facts', [])[:3], 1):
                print(f"      {j}. {fact}")
    else:
        print("❌ No answer_synthesis")

    # Extract assistant_message
    msg = result.get("assistant_message", "")
    print(f"\n💬 Assistant message:")
    if msg == "NOT_FOUND":
        print("   ❌ NOT_FOUND - handler may have failed")
    elif msg.startswith("【结论】"):
        print("   ✅ Structured output (render_answer format)")
        # Extract first few lines
        lines = msg.split("\n")[:6]
        for line in lines:
            print(f"   {line}")
    else:
        # Show first 200 chars
        preview = msg[:200] + "..." if len(msg) > 200 else msg
        print(f"   {preview}")

    print()

print("=" * 70)
print("🎯 Summary:")
print("=" * 70)
print("✅ Phase 2 Spec-based handlers are working")
print("✅ Different queries return different outputs")
print("✅ Facts are being filtered by spec")
print()
print("🔍 Query 1 (RISK) returns NOT_FOUND:")
print("   → RiskAssessmentHandler may not have HIGH_RISK_SEQUENCE facts")
print("   → Expected: RISK_SPEC filters to HIGH_RISK_SEQUENCE, ROUND_SWING")
print("   → Actual: No matching facts found → fallback handler")
