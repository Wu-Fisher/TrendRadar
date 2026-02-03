"""
TrendRadar 定时推送脚本
供 TaskTimer 插件调用，推送最新财经新闻摘要

使用方法:
1. 将此脚本复制到 TaskTimer 的 func 目录:
   sudo cp scripts/langbot_integrations/trendradar_push.py \
       docker/langbot_data/plugins/sheetung__TaskTimer/func/

2. 在 TaskTimer 的 config/tasks.yaml 中添加:
   - schedule: '0 9 * * *'
     script: 'trendradar_push.py'
     enabled: true
     description: '每天早上9点推送财经新闻日报'
     target_type: 'group'
     target_id: 'oc_xxx'  # 飞书群聊ID
     bot_uuid: 'xxx'      # LangBot 中的 Bot UUID

3. 确保 langbot_plugin_runtime 容器已挂载 trendradar_output 目录
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


# 配置路径 (Docker 容器内 langbot_plugin_runtime)
CONFIG_DIR = Path(os.environ.get("TRENDRADAR_CONFIG_DIR", "/app/trendradar_config"))
OUTPUT_DIR = Path(os.environ.get("TRENDRADAR_OUTPUT_DIR", "/app/trendradar_output"))
QUEUE_DIR = CONFIG_DIR / ".push_queue"
DB_PATH = OUTPUT_DIR / "crawler" / "crawler.db"


async def execute():
    """
    TaskTimer 调用的入口函数
    返回要发送的消息内容 (日报格式)
    """
    try:
        # 获取过去24小时的新闻统计
        news_items = get_recent_news(hours=24)
        stats = get_daily_stats(hours=24)

        if not news_items and not stats:
            return "📰 TrendRadar 日报\n\n暂无新的财经快讯"

        # 格式化日报消息
        message = format_daily_report(news_items, stats)
        return message

    except Exception as e:
        return f"❌ 生成财经日报失败: {str(e)}"


def get_recent_news(hours: int = 12) -> list:
    """从数据库获取最近的新闻"""
    if not DB_PATH.exists():
        return []

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        # 计算时间范围
        since = datetime.now() - timedelta(hours=hours)
        since_str = since.strftime("%Y-%m-%d %H:%M:%S")

        # 查询最近的新闻 (按重要性/AI分析优先)
        cursor.execute("""
            SELECT title, url, source_name, published_at
            FROM crawler_raw
            WHERE published_at > ?
              AND filtered_out = 0
            ORDER BY published_at DESC
            LIMIT 15
        """, (since_str,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "title": row[0],
                "link": row[1],
                "source": row[2],
                "time": row[3]
            }
            for row in rows
        ]

    except Exception as e:
        print(f"查询数据库失败: {e}")
        return []


def get_daily_stats(hours: int = 24) -> dict:
    """获取每日统计数据"""
    if not DB_PATH.exists():
        return {}

    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        since = datetime.now() - timedelta(hours=hours)
        since_str = since.strftime("%Y-%m-%d %H:%M:%S")

        # 统计新闻总数
        cursor.execute("""
            SELECT COUNT(*) FROM crawler_raw WHERE crawl_time > ?
        """, (since_str,))
        total_count = cursor.fetchone()[0]

        # 统计按来源分组
        cursor.execute("""
            SELECT source_name, COUNT(*) as cnt
            FROM crawler_raw
            WHERE crawl_time > ?
            GROUP BY source_name
            ORDER BY cnt DESC
            LIMIT 5
        """, (since_str,))
        source_stats = cursor.fetchall()

        conn.close()

        return {
            "total": total_count,
            "sources": source_stats
        }

    except Exception as e:
        print(f"获取统计数据失败: {e}")
        return {}


def get_processed_count() -> int:
    """获取已处理推送数量"""
    processed_dir = QUEUE_DIR / ".processed"
    if not processed_dir.exists():
        return 0
    return len(list(processed_dir.glob("*.json")))


def format_daily_report(news_items: list, stats: dict) -> str:
    """格式化每日报告"""
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")
    time_str = now.strftime("%H:%M")

    lines = [
        f"📰 **TrendRadar 财经日报**",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📅 {date_str}  🕐 {time_str}",
        ""
    ]

    # 统计摘要
    if stats:
        total = stats.get("total", 0)
        processed = get_processed_count()
        lines.append(f"📊 **今日统计**")
        lines.append(f"   • 抓取新闻: {total} 条")
        lines.append(f"   • 推送消息: {processed} 条")

        sources = stats.get("sources", [])
        if sources:
            source_text = ", ".join([f"{s[0]}({s[1]})" for s in sources[:3]])
            lines.append(f"   • 主要来源: {source_text}")
        lines.append("")

    # 热门新闻
    if news_items:
        lines.append(f"📌 **热门快讯** (最近 {len(news_items)} 条)")
        lines.append("")

        for i, item in enumerate(news_items[:8], 1):
            title = item.get("title", "")
            if len(title) > 45:
                title = title[:45] + "..."
            source = item.get("source", "未知")
            lines.append(f"{i}. {title}")
            lines.append(f"   📍 {source}")

        if len(news_items) > 8:
            lines.append(f"   ... 还有 {len(news_items) - 8} 条")
        lines.append("")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━",
        "💡 输入 `!tr status` 查看详情"
    ])

    return "\n".join(lines)


def format_news_summary(items: list) -> str:
    """格式化新闻摘要 (实时推送用)"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"📰 **TrendRadar 财经快讯**",
        f"━━━━━━━━━━━━━━━━",
        f"🕐 {now}",
        ""
    ]

    for i, item in enumerate(items[:8], 1):
        title = item.get("title", "")[:50]
        source = item.get("source", "未知")
        lines.append(f"{i}. {title}")
        lines.append(f"   📍 {source}")
        lines.append("")

    lines.extend([
        "━━━━━━━━━━━━━━━━",
        "💡 输入 `!tr status` 查看更多"
    ])

    return "\n".join(lines)


# 本地测试
if __name__ == "__main__":
    import asyncio
    result = asyncio.run(execute())
    print(result)
