#!/bin/bash
#
# BudgetController 回滚脚本
#
# 如果在生产环境发现问题，运行此脚本立即禁用 BudgetController
#

echo "========================================================================"
echo "🔄 BudgetController Rollback Script"
echo "========================================================================"
echo ""
echo "⚠️  WARNING: This will DISABLE BudgetController in production"
echo ""
echo "This script will:"
echo "  1. Set BUDGET_CONTROLLER_ENABLED=false"
echo "  2. Remove SHADOW_MODE (if exists)"
echo "  3. Trigger Railway redeploy"
echo ""
read -p "Are you sure you want to proceed? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Rollout cancelled"
    exit 1
fi

echo ""
echo "📍 Step 1: Setting BUDGET_CONTROLLER_ENABLED=false"
railway variables set BUDGET_CONTROLLER_ENABLED false -p DriftCoach-Backend-for-cloud9-hackthon-

if [ $? -ne 0 ]; then
    echo "❌ Failed to set environment variable"
    echo "Please manually set BUDGET_CONTROLLER_ENABLED=false in Railway dashboard"
    exit 1
fi

echo ""
echo "📍 Step 2: Removing SHADOW_MODE (if exists)"
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
echo "✅ Rollback Complete!"
echo "========================================================================"
echo ""
echo "BudgetController has been DISABLED"
echo ""
echo "Next steps:"
echo "  1. Wait 2-3 minutes for deployment"
echo "  2. Verify system is working normally"
echo "  3. Check logs for any errors"
echo ""
echo "Railway Dashboard: https://dashboard.railway.app"
echo ""
