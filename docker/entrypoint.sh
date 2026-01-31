#!/bin/bash
set -e

# 检查配置文件
if [ ! -f "/app/config/config.yaml" ] || [ ! -f "/app/config/frequency_words.txt" ]; then
    echo "❌ 配置文件缺失"
    exit 1
fi

# 保存环境变量
env >> /etc/environment

case "${RUN_MODE:-cron}" in
"once")
    echo "🔄 单次执行"
    exec /usr/local/bin/python -m trendradar
    ;;
"daemon")
    echo "🚀 爬虫守护进程模式"
    DAEMON_ARGS=""
    if [ -n "${CRAWLER_POLL_INTERVAL}" ]; then
        DAEMON_ARGS="$DAEMON_ARGS -i ${CRAWLER_POLL_INTERVAL}"
    fi
    if [ "${CRAWLER_NO_PUSH:-false}" = "true" ]; then
        DAEMON_ARGS="$DAEMON_ARGS --no-push"
    fi
    if [ "${CRAWLER_VERBOSE:-false}" = "true" ]; then
        DAEMON_ARGS="$DAEMON_ARGS --verbose"
    fi
    if [ "${CRAWLER_ENABLE_AI:-false}" = "true" ]; then
        DAEMON_ARGS="$DAEMON_ARGS --enable-ai"
    fi
    if [ "${CRAWLER_USE_CREWAI:-false}" = "true" ]; then
        DAEMON_ARGS="$DAEMON_ARGS --use-crewai"
    fi
    echo "⚙️ 参数: $DAEMON_ARGS"
    exec /usr/local/bin/python scripts/run_crawler_daemon.py $DAEMON_ARGS
    ;;
"cron")
    # 生成 crontab
    echo "${CRON_SCHEDULE:-*/30 * * * *} cd /app && /usr/local/bin/python -m trendradar" > /tmp/crontab
    
    echo "📅 生成的crontab内容:"
    cat /tmp/crontab

    if ! /usr/local/bin/supercronic -test /tmp/crontab; then
        echo "❌ crontab格式验证失败"
        exit 1
    fi

    # 立即执行一次（如果配置了）
    if [ "${IMMEDIATE_RUN:-false}" = "true" ]; then
        echo "▶️ 立即执行一次"
        /usr/local/bin/python -m trendradar
    fi

    # 启动 Web 服务器（如果配置了）
    if [ "${ENABLE_WEBSERVER:-false}" = "true" ]; then
        echo "🌐 启动 Web 服务器..."
        /usr/local/bin/python manage.py start_webserver
    fi

    echo "⏰ 启动supercronic: ${CRON_SCHEDULE:-*/30 * * * *}"
    echo "🎯 supercronic 将作为 PID 1 运行"

    exec /usr/local/bin/supercronic -passthrough-logs /tmp/crontab
    ;;
*)
    exec "$@"
    ;;
esac