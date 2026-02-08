#!/bin/bash
# 触发云服务重新部署

echo "==================================="
echo "🚀 Trigger Cloud Service Redeploy"
echo "==================================="
echo ""

# 检查 Git 状态
echo "📊 Git Status:"
git status --short
echo ""

# 检查最新 commit
echo "📝 Latest Commit:"
git log -1 --oneline
echo ""

# 创建一个小的变更触发部署
echo "🔄 Triggering redeploy..."

# 方案 1: 更新 deployment guide（推荐）
echo "## Last Deploy" >> DEPLOYMENT_GUIDE.md
echo "- Date: $(date)" >> DEPLOYMENT_GUIDE.md
echo "- Commit: $(git rev-parse HEAD)" >> DEPLOYMENT_GUIDE.md

git add DEPLOYMENT_GUIDE.md
git commit -m "chore: trigger redeploy with DecisionMapper fix (1→2 breakthrough)"
git push

echo ""
echo "==================================="
echo "✅ Redeploy Triggered!"
echo "==================================="
echo ""
echo "📊 Next Steps:"
echo "   1. 访问云服务控制台查看部署状态"
echo "   2. 等待 1-3 分钟部署完成"
echo "   3. 运行验证: ./verify_fix.sh"
echo ""
echo "🔗 常见云服务控制台:"
echo "   Render: https://dashboard.render.com"
echo "   Railway: https://dashboard.railway.app"
echo "   Fly.io: https://fly.io/apps"
