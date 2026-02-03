#!/bin/bash
# TrendRadar 部署脚本
# 用法: ./deploy.sh [命令]
#
# 命令:
#   build    - 仅构建镜像
#   start    - 启动所有服务
#   stop     - 停止所有服务
#   restart  - 重启所有服务
#   status   - 查看服务状态
#   logs     - 查看服务日志
#   full     - 完整部署 (构建 + 启动)
#   help     - 显示帮助

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Docker 命令包装 (处理权限问题)
docker_cmd() {
    if docker ps &>/dev/null; then
        docker "$@"
    elif sg docker -c "docker ps" &>/dev/null; then
        sg docker -c "docker $*"
    else
        echo -e "${RED}错误: 无法连接 Docker daemon${NC}"
        echo "请确保:"
        echo "  1. Docker 服务已启动"
        echo "  2. 当前用户在 docker 组中"
        exit 1
    fi
}

# Docker Compose 命令包装
compose_cmd() {
    if docker compose version &>/dev/null; then
        docker compose "$@"
    elif sg docker -c "docker compose version" &>/dev/null; then
        sg docker -c "docker compose $*"
    else
        echo -e "${RED}错误: Docker Compose 不可用${NC}"
        exit 1
    fi
}

# 部署 LangBot 插件集成脚本
deploy_langbot_scripts() {
    print_step "部署 LangBot 插件集成脚本..."

    local CONTAINER="langbot_plugin_runtime"
    local TASKTIMER_FUNC_PATH="/app/data/plugins/sheetung__TaskTimer/func"

    # 检查容器是否运行
    if ! docker_cmd ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
        print_warn "容器 ${CONTAINER} 未运行，跳过脚本部署"
        return 0
    fi

    # 检查 TaskTimer 插件是否存在
    if ! docker_cmd exec "$CONTAINER" test -d "$TASKTIMER_FUNC_PATH" 2>/dev/null; then
        print_warn "TaskTimer 插件未安装，跳过脚本部署"
        return 0
    fi

    # 复制 TrendRadar 日报脚本 (使用 docker cp)
    local SRC_SCRIPT="../scripts/langbot_integrations/trendradar_push.py"
    if [ -f "$SRC_SCRIPT" ]; then
        docker_cmd cp "$SRC_SCRIPT" "${CONTAINER}:${TASKTIMER_FUNC_PATH}/"
        print_success "已部署 trendradar_push.py 到 TaskTimer"
    else
        print_warn "脚本文件不存在: $SRC_SCRIPT"
    fi
}

print_header() {
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}  TrendRadar 部署脚本${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}"
}

print_step() {
    echo -e "\n${GREEN}▶ $1${NC}"
}

print_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# 构建镜像
do_build() {
    print_step "构建 TrendRadar 镜像..."
    compose_cmd -f docker-compose-build.yml build trendradar
    print_success "镜像构建完成"
}

# 启动 LangBot 服务
start_langbot() {
    print_step "启动 LangBot + 插件运行时..."
    compose_cmd -f docker-compose-langbot.yml up -d langbot langbot_plugin_runtime
}

# 启动 TrendRadar 服务
start_trendradar() {
    print_step "启动 TrendRadar + 飞书推送..."
    compose_cmd -f docker-compose-build.yml --profile feishu up -d
}

# 启动所有服务
do_start() {
    start_langbot
    start_trendradar

    print_step "等待服务启动..."
    sleep 5

    do_status
    print_success "所有服务已启动"
}

# 停止所有服务
do_stop() {
    print_step "停止 TrendRadar + 飞书推送..."
    compose_cmd -f docker-compose-build.yml --profile feishu down || true

    print_step "停止 LangBot..."
    compose_cmd -f docker-compose-langbot.yml down || true

    print_success "所有服务已停止"
}

# 重启所有服务
do_restart() {
    print_step "重启所有服务..."

    # 重启 LangBot
    compose_cmd -f docker-compose-langbot.yml restart langbot langbot_plugin_runtime || true

    # 重启 TrendRadar
    compose_cmd -f docker-compose-build.yml --profile feishu restart || true

    sleep 5
    do_status
    print_success "所有服务已重启"
}

# 查看服务状态
do_status() {
    print_step "服务状态:"
    echo ""
    docker_cmd ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "NAMES|trendradar|langbot|feishu" || echo "无运行中的服务"
}

# 查看日志
do_logs() {
    local service="${1:-all}"

    case "$service" in
        trendradar|tr)
            print_step "TrendRadar 日志:"
            docker_cmd logs --tail 50 trendradar
            ;;
        feishu|push)
            print_step "飞书推送日志:"
            docker_cmd logs --tail 50 feishu_push
            ;;
        langbot|lb)
            print_step "LangBot 日志:"
            docker_cmd logs --tail 50 langbot
            ;;
        plugin|runtime)
            print_step "插件运行时日志:"
            docker_cmd logs --tail 50 langbot_plugin_runtime
            ;;
        all|*)
            print_step "TrendRadar 日志 (最近 20 行):"
            docker_cmd logs --tail 20 trendradar 2>/dev/null || echo "(容器未运行)"
            echo ""
            print_step "飞书推送日志 (最近 20 行):"
            docker_cmd logs --tail 20 feishu_push 2>/dev/null || echo "(容器未运行)"
            echo ""
            print_step "插件运行时日志 (最近 20 行):"
            docker_cmd logs --tail 20 langbot_plugin_runtime 2>/dev/null || echo "(容器未运行)"
            ;;
    esac
}

# 完整部署
do_full() {
    print_header
    do_build
    deploy_langbot_scripts
    do_start
    echo ""
    print_success "完整部署完成!"
    echo ""
    echo "可用命令:"
    echo "  飞书发送 !tr        - 测试插件"
    echo "  ./deploy.sh logs    - 查看日志"
    echo "  ./deploy.sh status  - 查看状态"
}

# 部署 LangBot 集成
do_deploy_scripts() {
    print_header
    deploy_langbot_scripts
    print_success "LangBot 集成脚本部署完成"
}

# 显示帮助
do_help() {
    cat << EOF
TrendRadar 部署脚本

用法: ./deploy.sh [命令] [参数]

命令:
  build              构建 TrendRadar Docker 镜像
  start              启动所有服务
  stop               停止所有服务
  restart            重启所有服务
  status             查看服务状态
  logs [服务名]      查看日志 (trendradar/feishu/langbot/plugin/all)
  deploy-scripts     部署 LangBot 集成脚本 (TaskTimer 日报等)
  full               完整部署 (构建 + 部署脚本 + 启动)
  help               显示此帮助信息

示例:
  ./deploy.sh full              # 首次部署或代码更新后
  ./deploy.sh restart           # 重启所有服务
  ./deploy.sh logs trendradar   # 查看爬虫日志
  ./deploy.sh logs plugin       # 查看插件日志
  ./deploy.sh deploy-scripts    # 仅部署 LangBot 集成脚本

服务说明:
  trendradar              爬虫守护进程 + AI 分析
  feishu_push             推送队列 → 飞书 (实时)
  langbot                 飞书机器人主服务
  langbot_plugin_runtime  插件系统 (!tr 命令)

EOF
}

# 主入口
main() {
    local cmd="${1:-help}"
    shift || true

    case "$cmd" in
        build)
            print_header
            do_build
            ;;
        start)
            print_header
            do_start
            ;;
        stop)
            print_header
            do_stop
            ;;
        restart)
            print_header
            do_restart
            ;;
        status)
            do_status
            ;;
        logs)
            do_logs "$@"
            ;;
        deploy-scripts)
            do_deploy_scripts
            ;;
        full)
            do_full
            ;;
        help|--help|-h)
            do_help
            ;;
        *)
            print_error "未知命令: $cmd"
            echo ""
            do_help
            exit 1
            ;;
    esac
}

main "$@"
