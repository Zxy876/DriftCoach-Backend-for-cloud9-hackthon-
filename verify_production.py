#!/usr/bin/env python3
"""
Verify BudgetController is working correctly in production.

Run this after enabling BudgetController to verify:
1. System is responding normally
2. Confidence values are >= 0.7
3. No errors in responses
"""

import requests
import json
from datetime import datetime

API_URL = "https://web-production-a92838.up.railway.app"
SERIES_ID = "2819676"
NUM_TEST_QUERIES = 10

print("=" * 70)
print("🔍 BudgetController Production Verification")
print("=" * 70)
print()

# Initialize session
print("📥 Initializing session...")
init_resp = requests.post(f"{API_URL}/api/coach/init",
    json={"grid_series_id": SERIES_ID},
    headers={"Content-Type": "application/json"}
)

if init_resp.status_code != 200:
    print(f"❌ Failed to initialize session: {init_resp.status_code}")
    print(f"Response: {init_resp.text}")
    exit(1)

session_id = init_resp.json().get("session_id")
print(f"✅ Session: {session_id}")
print()

# Run test queries
print("=" * 70)
print("🧪 Running Test Queries")
print("=" * 70)
print()

results = []
errors = []

for i in range(NUM_TEST_QUERIES):
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

        if resp.status_code != 200:
            print(f"❌ Query {i+1}: HTTP {resp.status_code}")
            errors.append({
                "query": i+1,
                "error": f"HTTP {resp.status_code}",
                "response": resp.text[:200]
            })
            continue

        result = resp.json()
        ans = result.get("answer_synthesis", {})

        confidence = ans.get("confidence")
        verdict = ans.get("verdict")
        facts_count = len(ans.get("support_facts", []))

        status_icon = "✅"
        if confidence is None or confidence < 0.7:
            status_icon = "⚠️"

        print(f"Query {i+1:2d}: Confidence={confidence}, Verdict={verdict}, Facts={facts_count} {status_icon}")

        results.append({
            "query": i+1,
            "confidence": confidence,
            "verdict": verdict,
            "facts_count": facts_count,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        print(f"❌ Query {i+1}: ERROR - {str(e)[:50]}")
        errors.append({
            "query": i+1,
            "error": str(e)
        })

print()
print("=" * 70)
print("📊 Analysis Results")
print("=" * 70)
print()

# Success rate
total = len(results) + len(errors)
success_rate = len(results) / total * 100 if total > 0 else 0
print(f"Total queries: {total}")
print(f"Successful: {len(results)} ({success_rate:.1f}%)")
print(f"Errors: {len(errors)}")
print()

# Confidence analysis
if results:
    confidences = [r["confidence"] for r in results if r["confidence"] is not None]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        min_conf = min(confidences)
        max_conf = max(confidences)
        high_conf = len([c for c in confidences if c >= 0.7])

        print(f"Confidence Analysis:")
        print(f"  Average: {avg_conf:.2f}")
        print(f"  Min: {min_conf:.2f}, Max: {max_conf:.2f}")
        print(f"  High confidence (≥0.7): {high_conf}/{len(confidences)} ({high_conf/len(confidences)*100:.1f}%)")
        print()

# Facts analysis
if results:
    facts = [r["facts_count"] for r in results]
    avg_facts = sum(facts) / len(facts)
    print(f"Facts Usage:")
    print(f"  Average: {avg_facts:.1f}")
    print(f"  Min: {min(facts)}, Max: {max(facts)}")
    print()

# Verdict distribution
if results:
    verdicts = [r["verdict"] for r in results if r["verdict"]]
    if verdicts:
        print(f"Verdict Distribution:")
        for v in set(verdicts):
            count = verdicts.count(v)
            print(f"  {v}: {count}/{len(verdicts)} ({count/len(verdicts)*100:.1f}%)")
        print()

# Errors
if errors:
    print("⚠️  Errors:")
    for err in errors:
        print(f"  Query {err['query']}: {err.get('error', 'Unknown')}")
    print()

# Final verdict
print("=" * 70)
print("🎯 Final Verdict")
print("=" * 70)
print()

checks = []

# Check 1: Success rate
if success_rate >= 95:
    checks.append(("✅", f"Success rate: {success_rate:.1f}% (≥95%)", True))
elif success_rate >= 80:
    checks.append(("⚠️", f"Success rate: {success_rate:.1f}% (80-95%)", False))
else:
    checks.append(("❌", f"Success rate: {success_rate:.1f}% (<80%)", False))

# Check 2: Confidence stability
if confidences:
    high_conf_rate = len([c for c in confidences if c >= 0.7]) / len(confidences) * 100
    if high_conf_rate >= 90:
        checks.append(("✅", f"High confidence rate: {high_conf_rate:.1f}% (≥90%)", True))
    else:
        checks.append(("❌", f"High confidence rate: {high_conf_rate:.1f}% (<90%)", False))

# Check 3: Error count
if len(errors) == 0:
    checks.append(("✅", "No errors", True))
elif len(errors) <= 2:
    checks.append(("⚠️", f"Few errors: {len(errors)}", False))
else:
    checks.append(("❌", f"Many errors: {len(errors)}", False))

# Print results
all_pass = True
for icon, message, passed in checks:
    print(f"{icon} {message}")
    if not passed:
        all_pass = False

print()
print("=" * 70)
print("🚀 Next Steps")
print("=" * 70)
print()

if all_pass:
    print("✅ All checks passed! BudgetController is working correctly.")
    print()
    print("Continue monitoring:")
    print("  - Check Railway logs periodically")
    print("  - Monitor for user feedback")
    print("  - Run this script again in 24 hours")
else:
    print("⚠️  Some checks failed. Review the results above.")
    print()
    print("Possible actions:")
    print("  - Check Railway logs for errors")
    print("  - Consider rollback if problems persist")
    print("  - Run: bash rollback_budget_controller.sh")

print()
print("Railway Dashboard: https://dashboard.railway.app")
print("Railway Logs: Search for 'BC_METRICS' to see performance data")
print()

# Save results
output_file = "production_verification_results.json"
with open(output_file, "w") as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "errors": errors,
        "summary": {
            "total_queries": total,
            "successful": len(results),
            "errors": len(errors),
            "success_rate": success_rate,
            "avg_confidence": avg_conf if confidences else None,
            "all_checks_passed": all_pass
        }
    }, f, indent=2)

print(f"📁 Results saved to: {output_file}")
