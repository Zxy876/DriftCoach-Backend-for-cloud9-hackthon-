#!/bin/bash
# 简单的 Railway 验证脚本

API_URL="https://web-production-a92838.up.railway.app"
SERIES_ID="2819676"

echo "==================================="
echo "🧪 验证 Railway DecisionMapper"
echo "==================================="
echo ""

# 步骤 1: Init
echo "📥 步骤 1: 初始化..."
INIT_JSON=$(cat <<EOF
{"grid_series_id": "$SERIES_ID"}
EOF
)

INIT_RESULT=$(curl -s -X POST "$API_URL/api/coach/init" \
  -H "Content-Type: application/json" \
  -d "$INIT_JSON" \
  --max-time 30)

echo "Init 响应: $INIT_RESULT"
echo ""

# 提取 session_id
SESSION_ID=$(echo "$INIT_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('session_id', 'error'))" 2>/dev/null)

if [ "$SESSION_ID" = "error" ] || [ -z "$SESSION_ID" ]; then
    echo "❌ 无法获取 session_id"
    echo "   响应: $INIT_RESULT"
    exit 1
fi

echo "✅ Session ID: $SESSION_ID"
echo ""

# 步骤 2: Query
echo "📤 步骤 2: 查询..."
QUERY_JSON=$(cat <<EOF
{"coach_query": "这是不是一场高风险对局？", "session_id": "$SESSION_ID", "series_id": "$SERIES_ID"}
EOF
)

QUERY_RESULT=$(curl -s -X POST "$API_URL/api/coach/query" \
  -H "Content-Type: application/json" \
  -d "$QUERY_JSON" \
  --max-time 30)

echo "查询响应:"
echo "$QUERY_RESULT" | python3 -m json.tool 2>/dev/null || echo "$QUERY_RESULT"
echo ""

# 提取 assistant_message
ASSISTANT_MSG=$(echo "$QUERY_RESULT" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('assistant_message', 'no_message'))" 2>/dev/null)

echo "==================================="
echo "📊 结果分析"
echo "==================================="
echo ""
echo "💬 消息: $ASSISTANT_MSG"
echo ""

if echo "$ASSISTANT_MSG" | grep -q "证据不足"; then
    echo "❌ FAILED - 旧门控逻辑仍在运行"
    echo ""
    echo "🔧 解决方法:"
    echo "   1. 访问: https://dashboard.railway.app"
    echo "   2. 找到 DriftCoach-Backend 项目"
    echo "   3. 点击 'Redeploy' 按钮"
    echo "   4. 等待 1-3 分钟后重新测试"
    exit 1
elif echo "$ASSISTANT_MSG" | grep -q "基于.*证据\|有限证据"; then
    echo "✅ SUCCESS - DecisionMapper 已生效!"
    echo ""
    echo "🎉 1→2 Breakthrough 完成!"
    exit 0
else
    echo "⚠️  UNKNOWN - 无法判断"
    echo "   消息: $ASSISTANT_MSG"
    exit 2
fi
