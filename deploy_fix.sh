#!/bin/bash
# 部署 DecisionMapper 修复到容器

echo "==================================="
echo "🚀 Deploying 1→2 Breakthrough Fix"
echo "==================================="
echo ""

# 检查环境
if [ -f "Dockerfile" ] || [ -f "docker-compose.yml" ]; then
    echo "📦 检测到 Docker 配置"
    echo "执行：docker-compose restart"
    docker-compose restart
    echo "✅ Docker 容器已重启"
elif [ -n "$RENDER_SERVICE_NAME" ] || [ -n "$RAILWAY_SERVICE_NAME" ]; then
    echo "☁️  检测到云服务环境"
    echo "请通过 Git 推送触发重新部署："
    echo "  git add ."
    echo "  git commit -m 'feat: 1→2 breakthrough with DecisionMapper'"
    echo "  git push"
else
    echo "💻 本地开发环境"
    echo "请手动重启服务："
    echo "  pkill -f 'uvicorn'"
    echo "  python3 -m uvicorn driftcoach.api:app --reload --host 0.0.0.0 --port 8080"
fi

echo ""
echo "==================================="
echo "✅ 部署完成！"
echo "==================================="
echo ""
echo "🧪 测试验证："
echo 'curl -X POST http://localhost:8080/api/coach/query \'
echo '  -H "Content-Type: application/json" \'
echo '  -d '{"coach_query":"这是不是一场高风险对局？","series_id":"2819676"}'
echo ""
echo "预期输出："
echo '  "assistant_message": "基于X条有限证据的初步分析..."'
echo "  (而非: 证据不足)"
