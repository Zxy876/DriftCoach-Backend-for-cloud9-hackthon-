#!/bin/bash
#
# BudgetController 启用脚本
#
# 渐进发布：启用 BudgetController，禁用 Shadow Mode
#

echo "========================================================================"
echo "🚀 BudgetController Enable Script"
echo "========================================================================"
echo ""
echo "This script will:"
echo "  1. Set BUDGET_CONTROLLER_ENABLED=true"
echo "  2. Remove SHADOW_MODE (exit shadow mode)"
echo "  3. Trigger Railway redeploy"
echo ""
echo "⚠️  Make sure you have completed shadow mode validation!"
echo ""
read -p "Proceed with enabling BudgetController? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Enable cancelled"
    exit 1
fi

echo ""
echo "📍 Step 1: Setting BUDGET_CONTROLLER_ENABLED=true"
railway variables set BUDGET_CONTROLLER_ENABLED=true -p DriftCoach-Backend-for-cloud9-hackthon-

if [ $? -ne 0 ]; then
    echo "❌ Failed to set environment variable"
    echo "Please manually set BUDGET_CONTROLLER_ENABLED=true in Railway dashboard"
    exit 1
fi

echo ""
echo "📍 Step 2: Removing SHADOW_MODE (exit shadow mode)"
railway variables remove SHADOW_MODE -p DriftCoach-Backend-for-cloud9-hackthon-

# Ignore errors if variable doesn't exist
if [ $? -ne 0 ]; then
    echo "⚠️  SHADOW_MODE variable not found (this is okay)"
fi

echo ""
echo "📍 Step 3: Triggering Railway redeploy"
railway up -p DriftCoach-Backend-for-cloud9-hackthon-

if [ $? -ne 0 ]; then
    echo "❌ Failed to trigger redeploy"
    echo "Please manually trigger redeploy in Railway dashboard"
    exit 1
fi

echo ""
echo "========================================================================"
echo "✅ BudgetController Enabled!"
echo "========================================================================"
echo ""
echo "Configuration:"
echo "  ✅ BUDGET_CONTROLLER_ENABLED=true"
echo "  ✅ SHADOW_MODE=removed"
echo ""
echo "Monitoring checklist:"
echo "  □ Check Railway logs for errors"
echo "  □ Verify confidence values >= 0.7"
echo "  □ Monitor response times"
echo "  □ Collect user feedback"
echo ""
echo "Railway Dashboard: https://dashboard.railway.app"
echo "Railway Logs: https://dashboard.railway.app -> Logs"
echo ""
echo "Search for these keywords in logs:"
echo "  - 'BC_METRICS' - BudgetController performance"
echo "  - 'ERROR' - Any errors"
echo "  - 'confidence' - Confidence values"
echo ""
echo "📊 Quick verification test:"
echo "  Run: python3 verify_production.py"
echo ""
