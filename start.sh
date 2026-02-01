#!/bin/bash
# TrendRadar 一键启动脚本
# 同时启动邮件推送 + 飞书推送

cd "$(dirname "$0")/docker"

echo "🚀 启动 TrendRadar 服务..."
echo ""

# 停止旧容器
echo "📦 停止旧容器..."
docker compose -f docker-compose-build.yml --profile feishu down 2>/dev/null

# 启动新容器
echo "📦 启动新容器..."
docker compose -f docker-compose-build.yml --profile feishu up -d --force-recreate

echo ""
echo "✅ 启动完成！"
echo ""
echo "📊 容器状态:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "NAME|trendradar|feishu"

echo ""
echo "📝 查看日志:"
echo "  docker logs -f trendradar      # 主服务"
echo "  docker logs -f feishu_push     # 飞书推送"
