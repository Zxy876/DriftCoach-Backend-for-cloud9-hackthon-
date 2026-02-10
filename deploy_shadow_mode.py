#!/usr/bin/env python3
"""
Railway Shadow Mode 部署脚本

Steps:
1. Set SHADOW_MODE=true environment variable on Railway
2. Trigger redeploy
3. Wait for deployment
4. Run test queries
5. Collect and analyze shadow metrics
"""

import subprocess
import time
import json
import sys

RAILWAY_PROJECT = "DriftCoach-Backend-for-cloud9-hackthon-"
SERIES_ID = "2819676"
API_URL = "https://web-production-a92838.up.railway.app"


def run_command(cmd, description):
    """Run a shell command."""
    print(f"\n🔧 {description}")
    print(f"   Command: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Error: {result.stderr}")
        return False
    print(f"✅ Success")
    return True


def wait_for_deployment(duration=90):
    """Wait for Railway deployment to complete."""
    print(f"\n⏳ Waiting {duration}s for Railway deployment...")
    print("   (You can monitor progress at https://dashboard.railway.app)")
    for i in range(duration, 0, -10):
        print(f"   {i}s remaining...")
        time.sleep(10)
    print("✅ Deployment should be complete")


def run_shadow_test():
    """Run a test query and collect shadow metrics."""
    print("\n" + "=" * 70)
    print("🧪 Running Shadow Mode Test")
    print("=" * 70)

    # Initialize session
    import requests

    print("\n📥 Initializing session...")
    init_resp = requests.post(f"{API_URL}/api/coach/init",
        json={"grid_series_id": SERIES_ID},
        headers={"Content-Type": "application/json"}
    )
    session_id = init_resp.json().get("session_id")
    print(f"✅ Session: {session_id}")

    # Send query
    print("\n📤 Sending query...")
    query_resp = requests.post(f"{API_URL}/api/coach/query",
        json={
            "coach_query": "这是不是一场高风险对局？",
            "session_id": session_id,
            "series_id": SERIES_ID
        },
        headers={"Content-Type": "application/json"}
    )

    result = query_resp.json()

    # Extract answer_synthesis
    ans = result.get("answer_synthesis", {})
    print(f"\n📊 Result:")
    print(f"   Claim: {ans.get('claim')}")
    print(f"   Verdict: {ans.get('verdict')}")
    print(f"   Confidence: {ans.get('confidence')}")
    print(f"   Support facts: {len(ans.get('support_facts', []))}")

    # Note: Shadow metrics will be in Railway logs, not in response
    print("\n🔍 Shadow Metrics:")
    print("   Check Railway logs for SHADOW_METRICS entries")
    print("   https://dashboard.railway.app")

    return {
        "claim": ans.get("claim"),
        "verdict": ans.get("verdict"),
        "confidence": ans.get("confidence"),
        "support_facts_count": len(ans.get("support_facts", [])),
    }


def main():
    """Main deployment workflow."""
    print("=" * 70)
    print("🚀 Railway Shadow Mode Deployment")
    print("=" * 70)
    print()
    print("⚠️  IMPORTANT:")
    print("   This script requires Railway CLI to be installed")
    print("   Install: npm install -g @railway/cli")
    print()
    print("   Steps:")
    print("   1. Set SHADOW_MODE=true on Railway")
    print("   2. Trigger redeploy")
    print("   3. Run test queries")
    print("   4. Analyze shadow metrics from logs")
    print()

    # Step 1: Set environment variable
    print("\n" + "=" * 70)
    print("Step 1: Set SHADOW_MODE=true")
    print("=" * 70)

    success = run_command(
        f"railway variables set SHADOW_MODE true -p {RAILWAY_PROJECT}",
        "Setting SHADOW_MODE=true on Railway"
    )

    if not success:
        print("\n❌ Failed to set environment variable")
        print("   Please manually set SHADOW_MODE=true in Railway dashboard:")
        print("   https://dashboard.railway.app")
        return 1

    # Step 2: Trigger redeploy
    print("\n" + "=" * 70)
    print("Step 2: Trigger Redeploy")
    print("=" * 70)

    success = run_command(
        f"railway up -p {RAILWAY_PROJECT}",
        "Triggering Railway redeploy"
    )

    if not success:
        print("\n❌ Failed to trigger redeploy")
        print("   Please manually trigger redeploy in Railway dashboard")
        return 1

    # Step 3: Wait for deployment
    wait_for_deployment(90)

    # Step 4: Run test
    result = run_shadow_test()

    print("\n" + "=" * 70)
    print("✅ Shadow Mode Deployed!")
    print("=" * 70)
    print()
    print("Next Steps:")
    print("1. Run multiple queries (100+) over 15-30 minutes")
    print("2. Check Railway logs for SHADOW_METRICS entries")
    print("3. Analyze the 3 key metrics:")
    print("   - Facts used (WITH vs WITHOUT)")
    print("   - Confidence stability")
    print("   - Verdict consistency")
    print()
    print("Railway Dashboard: https://dashboard.railway.app")
    print("Railway Logs: https://dashboard.railway.app -> Logs")
    print()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
