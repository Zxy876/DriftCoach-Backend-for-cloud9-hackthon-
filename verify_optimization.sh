#!/bin/bash
# 验证优化效果（响应大小 + DecisionMapper）

API_URL="https://web-production-a92838.up.railway.app"
SERIES_ID="2819676"

echo "==================================="
echo "🧪 验证优化效果 + DecisionMapper"
echo "==================================="
echo ""

# 步骤 1: 初始化
echo "📥 初始化..."
INIT_RESULT=$(curl -s "$API_URL/api/coach/init" \
  -H "Content-Type: application/json" \
  -d "{\"grid_series_id\": \"$SERIES_ID\"}" \
  --max-time 30)

SESSION_ID=$(echo "$INIT_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('session_id', 'error'))" 2>/dev/null)

if [ "$SESSION_ID" = "error" ]; then
    echo "❌ 初始化失败"
    exit 1
fi

echo "✅ Session: $SESSION_ID"
echo ""

# 步骤 2: 查询并保存响应
echo "📤 发送查询..."
QUERY_RESULT=$(curl -s "$API_URL/api/coach/query" \
  -H "Content-Type: application/json" \
  -d "{\"coach_query\": \"这是不是一场高风险对局？\", \"session_id\": \"$SESSION_ID\", \"series_id\": \"$SERIES_ID\"}" \
  --max-time 60)

# 保存到文件
echo "$QUERY_RESULT" > /tmp/railway_response.json
RESPONSE_SIZE=$(wc -c < /tmp/railway_response.json)

echo ""
echo "==================================="
echo "📊 响应分析"
echo "==================================="
echo ""
echo "📦 响应大小: $RESPONSE_SIZE bytes"

# 转换为 KB
SIZE_KB=$(echo "scale=2; $RESPONSE_SIZE / 1024" | bc)
echo "   ($SIZE_KB KB)"
echo ""

# 提取 assistant_message
ASSISTANT_MSG=$(echo "$QUERY_RESULT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('assistant_message', 'NOT_FOUND'))" 2>/dev/null)

echo "💬 消息内容:"
echo "   $ASSISTANT_MSG"
echo ""

# 判断优化效果
echo "==================================="
echo "📊 优化效果"
echo "==================================="
echo ""

if [ "$RESPONSE_SIZE" -lt 102400 ]; then  # 小于 100KB
    if [ "$RESPONSE_SIZE" -lt 51200 ]; then  # 小于 50KB
        echo "✅ 优秀! 响应大小: $SIZE_KB KB"
    else
        echo "✅ 良好! 响应大小: $SIZE_KB KB"
    fi
else
    echo "⚠️  仍需优化: $SIZE_KB KB"
fi

echo ""

# 判断 DecisionMapper 是否生效
if echo "$ASSISTANT_MSG" | grep -q "基于.*证据\|有限证据\|初步分析"; then
    echo "✅ DecisionMapper 已生效!"
    echo "   消息格式: 新版（基于证据）"
elif echo "$ASSISTANT_MSG" | grep -q "证据不足"; then
    echo "❌ DecisionMapper 未生效"
    echo "   消息仍返回'证据不足'"
elif echo "$ASSISTANT_MSG" | grep -q "【结论】"; then
    echo "⚠️  DecisionMapper 未生效"
    echo "   消息格式: 旧版（带【】标记）"
else
    echo "⚠️  无法判断格式"
fi

echo ""
echo "==================================="
echo "🎯 下一步"
echo "==================================="
echo ""

if [ "$RESPONSE_SIZE" -gt 102400 ]; then
    echo "⚠️  响应仍较大，检查:"
    echo "   1. Railway 是否已重新部署"
    echo "   2. LOG_LEVEL 环境变量是否设置为 WARNING"
    echo "   3. VERBOSE_RESPONSE 是否为 false"
else
    echo "✅ 优化成功!"
    echo ""
    echo "改进效果:"
    echo "   之前: 109MB (109408256 bytes)"
    echo "   现在: $SIZE_KB KB ($RESPONSE_SIZE bytes)"
    echo "   减少: 99.9%"
fi

echo ""
echo "📝 Commit: 62d7c1d"
echo "🔗 查看日志: https://dashboard.railway.app"
