#!/bin/bash
# 触发 Railway 重新部署

echo "==================================="
echo "🚀 Trigger Railway Redeploy"
echo "==================================="
echo ""

echo "📊 当前状态："
echo "   最新 commit: $(git log -1 --oneline)"
echo "   修复包含: DecisionMapper 集成 + 门控优先级"
echo ""

echo "🔄 触发 Railway 重新部署..."
echo ""

# 检查是否有未推送的 commit
UNPUSHED=$(git log origin/nice..HEAD --oneline 2>/dev/null)
if [ -n "$UNPUSHED" ]; then
    echo "📤 发现未推送的 commit，先推送..."
    git push
else
    echo "✅ 所有 commit 已推送"
    echo ""
    echo "💡 Railway 应该会自动检测到新 commit 并重新部署"
    echo "   如果没有自动部署，请："
    echo "   1. 访问: https://dashboard.railway.app"
    echo "   2. 找到项目: DriftCoach-Backend"
    echo "   3. 点击 'Redeploy' 按钮"
fi

echo ""
echo "==================================="
echo "⏳ 等待部署完成（1-3 分钟）"
echo "==================================="
echo ""
echo "📝 部署完成后，运行验证："
echo "   ./verify_railway.sh"
echo ""
echo "🔗 或查看 Railway 部署日志："
echo "   https://dashboard.railway.app/project/<your-project-id>/service/<your-service-id>"
echo ""
