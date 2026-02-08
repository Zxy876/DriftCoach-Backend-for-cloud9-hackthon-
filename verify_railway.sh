#!/bin/bash
# 针对 Railway 验证 DecisionMapper 修复

# Railway 服务 URL
API_URL="https://web-production-a92838.up.railway.app"
SERIES_ID="2819676"
QUERY="这是不是一场高风险对局？"

echo "==================================="
echo "🧪 Verify DecisionMapper on Railway"
echo "==================================="
echo ""
echo "📊 配置："
echo "   Service: Railway (web-production-a92838.up.railway.app)"
echo "   Series ID: $SERIES_ID"
echo "   Query: $QUERY"
echo ""

echo "🔄 步骤 1: 初始化 context..."
INIT_RESPONSE=$(curl -s -X POST "$API_URL/api/coach/init" \
  -H "Content-Type: application/json" \
  -d "{
    \"grid_series_id\": \"$SERIES_ID\"
  }")

SESSION_ID=$(echo "$INIT_RESPONSE" | jq -r '.session_id')
echo "✅ Context 已初始化 (session_id: $SESSION_ID)"
echo ""
echo "🔄 步骤 2: 发送查询..."

RESPONSE=$(curl -s -X POST "$API_URL/api/coach/query" \
  -H "Content-Type: application/json" \
  -d "{
    \"coach_query\": \"$QUERY\",
    \"session_id\": \"$SESSION_ID\",
    \"series_id\": \"$SERIES_ID\"
  }")

echo ""
echo "==================================="
echo "📊 完整响应"
echo "==================================="
echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
echo ""

echo "==================================="
echo "📊 结果分析"
echo "==================================="

# 提取 assistant_message
ASSISTANT_MSG=$(echo "$RESPONSE" | jq -r '.assistant_message' 2>/dev/null)

echo ""
echo "💬 Assistant Message:"
echo "   $ASSISTANT_MSG"
echo ""

# 判断是否成功
if echo "$ASSISTANT_MSG" | grep -q "证据不足"; then
    echo "❌ FAILED: 仍在使用旧门控逻辑"
    echo "   消息包含'证据不足'"
    echo ""
    echo "🔧 可能原因："
    echo "   1. Railway 未自动重新部署"
    echo "   2. 需要手动触发部署"
    echo ""
    echo "👉 访问 Railway 控制台触发部署："
    echo "   https://dashboard.railway.app/project/<your-project-id>"
    echo "   或运行: ./trigger_railway_redeploy.sh"
    exit 1
elif echo "$ASSISTANT_MSG" | grep -q "基于.*证据\|检测到.*HIGH_RISK_SEQUENCE\|有限证据"; then
    echo "✅ SUCCESS: DecisionMapper 生效！"
    echo "   消息包含'基于X条证据'"
    echo ""
    echo "🎉 1→2 Breakthrough 完成！"
    echo ""
    echo "📊 改进效果："
    echo "   之前: 证据不足 (confidence=0.27)"
    echo "   现在: $ASSISTANT_MSG"
    exit 0
else
    echo "⚠️  UNKNOWN: 无法判断"
    echo "   消息内容：$ASSISTANT_MSG"
    exit 2
fi
