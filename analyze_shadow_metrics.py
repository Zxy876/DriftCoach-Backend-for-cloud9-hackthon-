#!/usr/bin/env python3
"""
Analyze Shadow Metrics from Railway production data.

After collecting shadow metrics with collect_shadow_metrics.py,
analyze the 3 key metrics to decide: enable or rollback BudgetController.
"""

import json
import sys
from pathlib import Path

METRICS_FILE = Path("shadow_metrics.json")

# Pass criteria
TARGET_FACTS_EFFICIENCY = 0.20  # 20% savings
TARGET_CONFIDENCE_STABILITY = 0.90  # 90% >= 0.7
TARGET_VERDICT_CONSISTENCY = 0.95  # 95% consistency


def load_metrics():
    """Load shadow metrics from file."""
    if not METRICS_FILE.exists():
        print(f"❌ Metrics file not found: {METRICS_FILE}")
        print(f"   Run collect_shadow_metrics.py first")
        sys.exit(1)

    with open(METRICS_FILE) as f:
        return json.load(f)


def analyze_efficiency(metrics):
    """
    Analyze Facts Saved (Efficiency) metric.

    Target: >20% facts saved on average
    """
    print("=" * 70)
    print("📊 Metric 1: Facts Saved (Efficiency)")
    print("=" * 70)
    print()

    # Note: Shadow metrics are in Railway logs, not in response
    # We can only analyze what we see in the response (baseline WITHOUT BC)
    # To get true shadow comparison, need to check Railway logs

    print("⚠️  NOTE: This metric requires checking Railway logs for SHADOW_METRICS")
    print()
    print("Expected in logs:")
    print('  "efficiency": {"facts_saved": N}')
    print()
    print("Pass criterion: Average facts_saved_rate > 20%")
    print()
    print("To collect:")
    print("  1. Go to Railway Dashboard -> Logs")
    print("  2. Search 'SHADOW_METRICS'")
    print("  3. Extract 'efficiency.facts_saved' values")
    print("  4. Calculate average: sum(facts_saved) / count")
    print()

    return "MANUAL_CHECK_REQUIRED"


def analyze_confidence_stability(metrics):
    """
    Analyze Confidence Stability metric.

    Target: >90% of queries with confidence >= 0.7
    """
    print("=" * 70)
    print("📊 Metric 2: Confidence Stability (Target: ≥0.7)")
    print("=" * 70)
    print()

    success_metrics = [m for m in metrics if m['status'] == 'success']
    confidences = [m['confidence'] for m in success_metrics if m.get('confidence') is not None]

    if not confidences:
        print("❌ No confidence data found")
        return None

    total = len(confidences)
    high_conf = len([c for c in confidences if c >= 0.7])
    rate = high_conf / total if total > 0 else 0

    print(f"Total queries: {total}")
    print(f"High confidence (≥0.7): {high_conf}")
    print(f"Stability rate: {rate * 100:.1f}%")
    print()

    if rate >= TARGET_CONFIDENCE_STABILITY:
        print(f"✅ PASS: Stability rate ({rate * 100:.1f}%) >= target ({TARGET_CONFIDENCE_STABILITY * 100:.0f}%)")
        return True
    else:
        print(f"❌ FAIL: Stability rate ({rate * 100:.1f}%) < target ({TARGET_CONFIDENCE_STABILITY * 100:.0f}%)")
        return False


def analyze_verdict_consistency(metrics):
    """
    Analyze Verdict Consistency metric.

    Target: >95% of queries show verdict consistency
    """
    print("=" * 70)
    print("📊 Metric 3: Verdict Consistency")
    print("=" * 70)
    print()

    print("⚠️  NOTE: This metric requires checking Railway logs for SHADOW_METRICS")
    print()
    print("Expected in logs:")
    print('  Comparing verdict_without vs verdict_with')
    print()
    print("Pass criterion: Consistency rate > 95%")
    print()
    print("To collect:")
    print("  1. Go to Railway Dashboard -> Logs")
    print("  2. Search 'SHADOW_METRICS'")
    print("  3. Check if verdict values match")
    print()
    print("For now, we can only check verdict distribution in baseline:")
    print()

    success_metrics = [m for m in metrics if m['status'] == 'success']
    verdicts = [m['verdict'] for m in success_metrics if m.get('verdict')]

    if verdicts:
        print(f"Total verdicts: {len(verdicts)}")
        for v in set(verdicts):
            count = verdicts.count(v)
            print(f"  {v}: {count}/{len(verdicts)} ({count/len(verdicts)*100:.1f}%)")
        print()

    return "MANUAL_CHECK_REQUIRED"


def analyze_response_quality(metrics):
    """
    Analyze Response Quality (secondary metric).
    """
    print("=" * 70)
    print("📊 Metric 4: Response Quality (Secondary)")
    print("=" * 70)
    print()

    success_metrics = [m for m in metrics if m['status'] == 'success']
    errors = [m for m in metrics if m['status'] == 'error']

    print(f"Total queries: {len(metrics)}")
    print(f"Successful: {len(success_metrics)}")
    print(f"Errors: {len(errors)}")
    print()

    if success_metrics:
        facts = [m['support_facts_count'] for m in success_metrics if m.get('support_facts_count') is not None]
        if facts:
            print(f"Facts used (baseline WITHOUT BC):")
            print(f"  Average: {sum(facts) / len(facts):.1f}")
            print(f"  Min: {min(facts)}, Max: {max(facts)}")
            print()

    return True


def main():
    """Main analysis."""
    print("=" * 70)
    print("📊 Shadow Metrics Analysis")
    print("=" * 70)
    print()

    # Load metrics
    metrics = load_metrics()

    print(f"✅ Loaded {len(metrics)} query results")
    print()

    # Analyze metrics
    efficiency_result = analyze_efficiency(metrics)
    confidence_result = analyze_confidence_stability(metrics)
    verdict_result = analyze_verdict_consistency(metrics)
    quality_result = analyze_response_quality(metrics)

    # Summary
    print()
    print("=" * 70)
    print("🎯 Analysis Summary")
    print("=" * 70)
    print()

    print("Metric 1: Facts Saved (Efficiency)")
    if efficiency_result == "MANUAL_CHECK_REQUIRED":
        print("  ⚠️  MANUAL CHECK REQUIRED")
        print("  → Check Railway logs for SHADOW_METRICS.efficiency.facts_saved")
    else:
        print(f"  {efficiency_result}")
    print()

    print("Metric 2: Confidence Stability")
    if confidence_result is None:
        print("  ❌ INSUFFICIENT DATA")
    elif confidence_result:
        print(f"  ✅ PASS")
    else:
        print(f"  ❌ FAIL")
    print()

    print("Metric 3: Verdict Consistency")
    if verdict_result == "MANUAL_CHECK_REQUIRED":
        print("  ⚠️  MANUAL CHECK REQUIRED")
        print("  → Check Railway logs for SHADOW_METRICS verdict comparison")
    else:
        print(f"  {verdict_result}")
    print()

    print("=" * 70)
    print("🚀 Next Steps")
    print("=" * 70)
    print()
    print("1. Check Railway logs for SHADOW_METRICS:")
    print("   https://dashboard.railway.app -> Logs")
    print("   Search: 'SHADOW_METRICS'")
    print()
    print("2. Extract efficiency and verdict data from logs")
    print()
    print("3. Decision:")
    print("   - If ALL 3 metrics pass → Enable BudgetController")
    print("   - If ANY metric fails → Analyze and optimize")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
