#!/bin/bash
# 验证 DecisionMapper 修复是否生效

echo "==================================="
echo "🧪 Verify DecisionMapper Fix"
echo "==================================="
echo ""

# 配置
API_URL="${API_URL:-http://localhost:8080}"
SERIES_ID="${SERIES_ID:-2819676}"
QUERY="这是不是一场高风险对局？"

echo "📊 测试配置："
echo "   API URL: $API_URL"
echo "   Series ID: $SERIES_ID"
echo "   Query: $QUERY"
echo ""

echo "🔄 发送请求..."
RESPONSE=$(curl -s -X POST "$API_URL/api/coach/query" \
  -H "Content-Type: application/json" \
  -d "{
    \"coach_query\": \"$QUERY\",
    \"series_id\": \"$SERIES_ID\"
  }")

echo ""
echo "==================================="
echo "📊 结果分析"
echo "===================================""

# 提取 assistant_message
ASSISTANT_MSG=$(echo "$RESPONSE" | grep -o '"assistant_message":"[^"]*"' | cut -d'"' -f4)

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
    echo "   1. 容器未重启（运行 ./deploy_fix.sh）"
    echo "   2. 代码未同步到容器"
    echo "   3. 缓存问题"
    exit 1
elif echo "$ASSISTANT_MSG" | grep -q "基于.*证据"; then
    echo "✅ SUCCESS: DecisionMapper 生效！"
    echo "   消息包含'基于X条证据'"
    echo ""
    echo "🎉 1→2 Breakthrough 完成！"
    exit 0
else
    echo "⚠️  UNKNOWN: 无法判断"
    echo "   消息内容：$ASSISTANT_MSG"
    exit 2
fi
