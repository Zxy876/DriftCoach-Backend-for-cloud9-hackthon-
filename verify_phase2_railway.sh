#!/bin/bash
# Railway Phase 2 验证：三条 query 对比测试

API_URL="https://web-production-a92838.up.railway.app"
SERIES_ID="2819676"

echo "==================================="
echo "🧪 Railway Phase 2 验证：Spec 收缩可见性"
echo "==================================="
echo ""
echo "📊 Commit: 6dfab83"
echo "🎯 目标: 验证不同 query 看到不同的 facts 子空间"
echo ""

# 步骤 1: 初始化
echo "📥 初始化 context..."
INIT_RESULT=$(curl -s "$API_URL/api/coach/init" \
  -H "Content-Type: application/json" \
  -d "{\"grid_series_id\": \"$SERIES_ID\"}")

SESSION_ID=$(echo "$INIT_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('session_id', 'error'))" 2>/dev/null)

if [ "$SESSION_ID" = "error" ]; then
    echo "❌ 初始化失败"
    exit 1
fi

echo "✅ Session: $SESSION_ID"
echo ""

# 测试三条 query
declare -a queries=(
    "这是不是一场高风险对局？"
    "经济决策有什么问题？"
    "这个选手表现如何？"
)

declare -a intents=(
    "RISK_ASSESSMENT"
    "ECONOMIC_COUNTERFACTUAL"
    "PLAYER_REVIEW"
)

echo "==================================="
echo "📊 三条 Query 对比测试"
echo "==================================="
echo ""

for i in {0..2}; do
    query="${queries[$i]}"
    intent="${intents[$i]}"

    echo "----------------------------------------"
    echo "Query $((i+1)): \"$query\""
    echo "Intent: $intent"
    echo "----------------------------------------"

    # 发送查询
    QUERY_RESULT=$(curl -s "$API_URL/api/coach/query" \
      -H "Content-Type: application/json" \
      -d "{\"coach_query\": \"$query\", \"session_id\": \"$SESSION_ID\", \"series_id\": \"$SERIES_ID\"}")

    # 提取 assistant_message
    ASSISTANT_MSG=$(echo "$QUERY_RESULT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('assistant_message', 'NOT_FOUND'))" 2>/dev/null)

    echo "💬 输出:"
    echo "   $ASSISTANT_MSG"
    echo ""

    # 提取 answer_synthesis 中的 facts（如果有）
    FACTS_COUNT=$(echo "$QUERY_RESULT" | python3 -c "import sys, json; d=json.load(sys.stdin); syn=d.get('answer_synthesis', {}); print(len(syn.get('support_facts', [])))" 2>/dev/null)

    if [ "$FACTS_COUNT" -gt 0 ]; then
        echo "   Support Facts: $FACTS_COUNT 个"
    fi

    echo ""
done

echo "==================================="
echo "📊 对比总结"
echo "==================================="
echo ""

echo "预期效果（Phase 2 Spec 收缩可见性）："
echo ""
echo "Query 1 (RISK_ASSESSMENT):"
echo "  → 应该看到: HIGH_RISK_SEQUENCE, ROUND_SWING"
echo "  → 输出应关注: 高风险序列、局势反转"
echo ""
echo "Query 2 (ECONOMIC_COUNTERFACTUAL):"
echo "  → 应该看到: FORCE_BUY_ROUND, ECO_COLLAPSE_SEQUENCE"
echo "  → 输出应关注: 强起决策、经济崩盘"
echo ""
echo "Query 3 (PLAYER_REVIEW):"
echo "  → 应该看到: PLAYER_IMPACT_STAT, ROUND_SWING"
echo "  → 输出应关注: 选手表现、贡献"
echo ""

echo "🔗 Railway 控制台:"
echo "   https://dashboard.railway.app"
echo ""
echo "📝 部署状态检查:"
echo "   查看最新 commit 是否为 6dfab83"
echo "   等待 1-3 分钟重新部署完成"
echo ""
