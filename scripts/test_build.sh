#!/bin/bash
# TrendRadar 构建和测试脚本
# 用法: bash scripts/test_build.sh

set -e

echo "=== TrendRadar 构建测试 ==="
echo ""

# 切换到项目根目录
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "项目目录: $PROJECT_ROOT"
echo ""

# 1. 语法检查
echo "1. Python 语法检查..."
python3 -m py_compile scripts/run_crawler_daemon.py
python3 -m py_compile trendradar/core/loader.py
python3 -m py_compile trendradar/ai/analyzers/simple.py
python3 -m py_compile trendradar/ai/analyzers/crew_analyzer.py
python3 -m py_compile trendradar/notification/dispatcher.py
python3 -m py_compile trendradar/constants.py
echo "   语法检查通过"
echo ""

# 2. 模块导入测试
echo "2. 模块导入测试..."
python3 -c "
import sys
sys.path.insert(0, '.')
from trendradar.constants import BatchSizes, Timeouts, Limits
print(f'   BatchSizes.FEISHU={BatchSizes.FEISHU}')
print(f'   Timeouts.AI_ANALYSIS={Timeouts.AI_ANALYSIS}')
from trendradar.core.loader import load_config
print('   loader OK')
config = load_config()
print(f'   EMAIL_ENABLED={config.get(\"EMAIL_ENABLED\")}')
ai_config = config.get('AI', {})
print(f'   AI.MODEL={ai_config.get(\"MODEL\", \"\")}')
print(f'   AI.QUEUE={ai_config.get(\"QUEUE\", {})}')
"
echo "   模块导入测试通过"
echo ""

# 3. Docker 构建
echo "3. Docker 构建..."
cd docker
docker compose -f docker-compose-build.yml build
echo "   Docker 构建完成"
echo ""

# 4. 启动容器
echo "4. 启动容器..."
docker compose -f docker-compose-build.yml up -d
echo "   容器已启动"
echo ""

# 5. 等待容器启动
echo "5. 等待容器启动 (10秒)..."
sleep 10

# 6. 检查容器状态
echo "6. 检查容器状态..."
docker ps --filter "name=trendradar" --format "{{.Names}}\t{{.Status}}"
echo ""

# 7. 查看日志
echo "7. 查看最近日志..."
docker logs trendradar --tail 50
echo ""

echo "=== 测试完成 ==="
echo ""
echo "如需持续查看日志，请执行:"
echo "  docker logs -f trendradar"
echo ""
echo "如需停止容器，请执行:"
echo "  cd docker && docker compose -f docker-compose-build.yml down"
