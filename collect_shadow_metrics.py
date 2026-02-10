#!/usr/bin/env python3
"""
Collect Shadow Metrics from Railway production environment.

Run this for 15-30 minutes to collect ≥100 shadow mode samples.
"""

import requests
import time
import json
from datetime import datetime
from pathlib import Path

API_URL = "https://web-production-a92838.up.railway.app"
SERIES_ID = "2819676"
NUM_QUERIES = 100
QUERY_DELAY = 2  # seconds between queries

print("=" * 70)
print("📊 Shadow Metrics Collection")
print("=" * 70)
print()
print(f"Target: {NUM_QUERIES} queries")
print(f"Delay: {QUERY_DELAY}s between queries")
print(f"Estimated time: {NUM_QUERIES * QUERY_DELAY / 60:.1f} minutes")
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

# Collect metrics
metrics = []
start_time = datetime.now()

print("=" * 70)
print("🚀 Starting collection...")
print("=" * 70)
print()
print("   Query | Confidence | Verdict    | Facts | Status")
print("   " + "-" * 60)

for i in range(NUM_QUERIES):
    try:
        resp = requests.post(f"{API_URL}/api/coach/query",
            json={
                "coach_query": "这是不是一场高风险对局？",
                "session_id": session_id,
                "series_id": SERIES_ID
            },
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        result = resp.json()
        ans = result.get("answer_synthesis", {})

        metric = {
            "query_num": i + 1,
            "timestamp": datetime.now().isoformat(),
            "claim": ans.get("claim"),
            "verdict": ans.get("verdict"),
            "confidence": ans.get("confidence"),
            "support_facts_count": len(ans.get("support_facts", [])),
            "status": "success"
        }

        metrics.append(metric)

        status_icon = "✅"
        print(f"   {i+1:4d}  | {ans.get('confidence'):10} | {ans.get('verdict'):10} | {len(ans.get('support_facts', [])):5} | {status_icon}")

    except Exception as e:
        print(f"   {i+1:4d}  | ERROR: {str(e)[:40]}")
        metrics.append({
            "query_num": i + 1,
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e)
        })

    # Delay between queries
    if i < NUM_QUERIES - 1:
        time.sleep(QUERY_DELAY)

end_time = datetime.now()
duration = (end_time - start_time).total_seconds()

print()
print("=" * 70)
print("✅ Collection Complete!")
print("=" * 70)
print()
print(f"   Total queries: {NUM_QUERIES}")
print(f"   Duration: {duration / 60:.1f} minutes")
print(f"   Success rate: {len([m for m in metrics if m['status'] == 'success']) / NUM_QUERIES * 100:.1f}%")
print()

# Save metrics
output_file = Path("shadow_metrics.json")
with open(output_file, "w") as f:
    json.dump(metrics, f, indent=2)

print(f"📁 Metrics saved to: {output_file}")
print()

# Analysis
print("=" * 70)
print("📊 Quick Analysis")
print("=" * 70)
print()

success_metrics = [m for m in metrics if m['status'] == 'success']

if success_metrics:
    # Confidence distribution
    confidences = [m['confidence'] for m in success_metrics if m.get('confidence')]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        high_conf = len([c for c in confidences if c >= 0.7])
        print(f"Confidence:")
        print(f"   Average: {avg_conf:.2f}")
        print(f"   High (≥0.7): {high_conf}/{len(confidences)} ({high_conf/len(confidences)*100:.1f}%)")
        print()

    # Verdict distribution
    verdicts = [m['verdict'] for m in success_metrics if m.get('verdict')]
    if verdicts:
        print(f"Verdict distribution:")
        for v in set(verdicts):
            count = verdicts.count(v)
            print(f"   {v}: {count}/{len(verdicts)} ({count/len(verdicts)*100:.1f}%)")
        print()

    # Facts distribution
    facts = [m['support_facts_count'] for m in success_metrics if m.get('support_facts_count') is not None]
    if facts:
        avg_facts = sum(facts) / len(facts)
        print(f"Facts used:")
        print(f"   Average: {avg_facts:.1f}")
        print(f"   Min: {min(facts)}, Max: {max(facts)}")
        print()

print()
print("=" * 70)
print("🎯 Next Steps")
print("=" * 70)
print()
print("1. Check Railway logs for SHADOW_METRICS entries:")
print("   https://dashboard.railway.app -> Logs")
print("   Search: 'SHADOW_METRICS'")
print()
print("2. Analyze the 3 key metrics:")
print("   - Facts saved (efficiency)")
print("   - Confidence stability (≥0.7)")
print("   - Verdict consistency")
print()
print("3. If all metrics pass → Enable BudgetController")
print("   If any metric fails → Analyze and optimize")
