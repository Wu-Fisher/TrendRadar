#!/usr/bin/env python3
# coding=utf-8
"""
TrendRadar 自定义爬虫运行器

独立运行爬虫，支持：
- 10秒轮询
- 增量检测
- 完整内容获取
- 过滤标记
- HTML 报告生成
- 推送通知
"""

import sys
import time
import signal
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from trendradar.core.loader import load_config
from trendradar.crawler.custom import (
    CrawlerManager,
    THSCrawler,
    CrawlerNewsItem,
    CrawlResult,
    FetchStatus,
    filter_news_items,
    load_frequency_words_for_crawler,
)


class CrawlerApp:
    """爬虫应用"""

    def __init__(self, config: Dict):
        self.config = config
        self.running = False

        # 爬虫配置
        crawler_config = config.get("CRAWLER_CUSTOM", {})
        self.enabled = crawler_config.get("ENABLED", True)
        self.poll_interval = crawler_config.get("POLL_INTERVAL", 10)

        # 完整内容配置
        full_content_config = crawler_config.get("FULL_CONTENT", {})
        self.content_enabled = full_content_config.get("ENABLED", True)
        self.content_async = full_content_config.get("ASYNC_MODE", True)
        self.content_fetch_delay = full_content_config.get("FETCH_DELAY", 0.3)

        # 存储配置
        storage_config = crawler_config.get("STORAGE", {})
        self.max_display_items = storage_config.get("MAX_DISPLAY_ITEMS", 100)

        # 过滤配置
        filter_config = crawler_config.get("FILTER", {})
        self.filter_enabled = filter_config.get("ENABLED", True)
        self.show_filter_tag = filter_config.get("SHOW_TAG", True)

        # 数据库路径
        data_dir = config.get("STORAGE", {}).get("LOCAL", {}).get("DATA_DIR", "output")
        db_dir = Path(data_dir) / "crawler"
        db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_dir / "crawler.db")

        # HTML 输出目录
        self.html_dir = Path(data_dir) / "html" / "crawler"
        self.html_dir.mkdir(parents=True, exist_ok=True)

        # 创建管理器
        self.manager = CrawlerManager(
            config={
                "poll_interval": self.poll_interval,
                "full_content": {"enabled": self.content_enabled},
            },
            db_path=self.db_path,
        )

        # 注册爬虫
        self._register_crawlers(crawler_config.get("SOURCES", []))

        # 加载关键词配置
        self.word_groups, self.filter_words, self.global_filters = load_frequency_words_for_crawler()

        # 统计
        self.stats = {
            "total_fetches": 0,
            "total_items": 0,
            "new_items": 0,
            "passed_items": 0,
            "filtered_items": 0,
        }

        # 最近的条目（用于显示）
        self.recent_items: List[Dict] = []

    def _register_crawlers(self, sources: List[Dict]) -> None:
        """注册爬虫"""
        if not sources:
            sources = [{"id": "ths-realtime", "name": "同花顺7x24", "type": "ths", "enabled": True}]

        for source in sources:
            if not source.get("enabled", True):
                continue

            source_type = source.get("type", "ths")
            if source_type == "ths":
                crawler = THSCrawler(config={
                    "timezone": self.config.get("TIMEZONE", "Asia/Shanghai"),
                    "timeout": source.get("timeout", 10),
                    "content_fetch_delay": self.content_fetch_delay,
                })
                self.manager.register(crawler)
                print(f"[爬虫] 注册: {crawler.get_source_name()} ({crawler.get_source_id()})")

    def crawl_once(self) -> Dict[str, CrawlResult]:
        """执行一次爬取"""
        results = self.manager.crawl_all()
        self.stats["total_fetches"] += 1

        for source_id, result in results.items():
            if result.status != FetchStatus.SUCCESS:
                print(f"[爬虫] {source_id} 失败: {result.error_message}")
                continue

            self.stats["total_items"] += result.total_count
            self.stats["new_items"] += result.new_count

            print(f"[爬虫] {source_id}: {result.total_count} 条, 新增 {result.new_count} 条")

            # 获取完整内容（异步）
            if self.content_enabled and result.new_count > 0:
                items_to_fetch = [item for item in result.items if not item.content_fetched]
                if items_to_fetch:
                    print(f"[爬虫] 开始获取 {len(items_to_fetch)} 条新闻完整内容...")
                    self.manager.fetch_full_content(
                        source_id,
                        items_to_fetch,
                        async_mode=self.content_async,
                    )

            # 过滤
            if self.filter_enabled:
                passed, filtered = filter_news_items(
                    result.items,
                    self.word_groups,
                    self.filter_words,
                    self.global_filters,
                )
                self.stats["passed_items"] += len(passed)
                self.stats["filtered_items"] += len(filtered)
                print(f"[爬虫] 过滤结果: 通过 {len(passed)}, 过滤 {len(filtered)}")

            # 更新最近条目
            self._update_recent_items(result.items, result.new_count)

        return results

    def _update_recent_items(self, items: List[CrawlerNewsItem], new_count: int) -> None:
        """更新最近条目列表"""
        now = datetime.now().strftime("%H:%M:%S")

        for i, item in enumerate(items):
            item_dict = {
                "seq": item.seq,
                "title": item.title,
                "summary": item.summary[:100] + "..." if len(item.summary) > 100 else item.summary,
                "full_content": item.full_content,
                "url": item.url,
                "published_at": item.published_at,
                "crawl_time": now,
                "is_new": i < new_count,
                "filtered_out": item.filtered_out,
                "filter_reason": item.filter_reason,
                "matched_keywords": item.matched_keywords,
                "content_fetched": item.content_fetched,
            }

            # 检查是否已存在
            existing = next((x for x in self.recent_items if x["seq"] == item.seq), None)
            if existing:
                # 更新
                existing.update(item_dict)
            else:
                # 添加到开头
                self.recent_items.insert(0, item_dict)

        # 保持最大条目数
        if len(self.recent_items) > self.max_display_items:
            self.recent_items = self.recent_items[:self.max_display_items]

    def generate_html_report(self) -> str:
        """生成 HTML 报告"""
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        filename = now.strftime("%H-%M-%S") + ".html"
        filepath = self.html_dir / filename

        # 生成 HTML
        html = self._render_html(timestamp)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        # 更新 latest.html
        latest_path = self.html_dir / "latest.html"
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"[爬虫] HTML 报告: {filepath}")
        return str(filepath)

    def _render_html(self, timestamp: str) -> str:
        """渲染 HTML"""
        items_html = ""
        for item in self.recent_items:
            # 过滤标签
            if self.show_filter_tag:
                if item["filtered_out"]:
                    filter_tag = f'<span class="filter-tag filtered">🚫 {item["filter_reason"]}</span>'
                elif item["matched_keywords"]:
                    keywords = ", ".join(item["matched_keywords"])
                    filter_tag = f'<span class="filter-tag passed">✓ {keywords}</span>'
                else:
                    filter_tag = '<span class="filter-tag">-</span>'
            else:
                filter_tag = ""

            # 新增标签
            new_tag = '<span class="new-tag">🆕 新增</span>' if item["is_new"] else ""

            # 内容预览
            content_preview = ""
            if item["full_content"]:
                preview = item["full_content"][:300] + "..." if len(item["full_content"]) > 300 else item["full_content"]
                content_preview = f'<div class="content-preview">{preview}</div>'

            items_html += f'''
            <div class="news-item {'new-item' if item['is_new'] else ''} {'filtered-out' if item['filtered_out'] else ''}">
                <div class="item-header">
                    <span class="time">{item['published_at']}</span>
                    {new_tag}
                    {filter_tag}
                </div>
                <div class="title">
                    <a href="{item['url']}" target="_blank">{item['title']}</a>
                </div>
                <div class="summary">{item['summary']}</div>
                {content_preview}
            </div>
            '''

        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrendRadar 爬虫报告 - {timestamp}</title>
    <meta http-equiv="refresh" content="10">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: #fff; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header h1 {{ font-size: 24px; color: #333; margin-bottom: 10px; }}
        .stats {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .stat-item {{ background: #f0f0f0; padding: 10px 15px; border-radius: 4px; }}
        .stat-item .label {{ font-size: 12px; color: #666; }}
        .stat-item .value {{ font-size: 18px; font-weight: bold; color: #333; }}
        .news-list {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .news-item {{ padding: 15px 20px; border-bottom: 1px solid #eee; }}
        .news-item:last-child {{ border-bottom: none; }}
        .news-item.new-item {{ background: #fffbeb; }}
        .news-item.filtered-out {{ opacity: 0.6; background: #f9f9f9; }}
        .item-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
        .time {{ font-size: 12px; color: #999; }}
        .new-tag {{ font-size: 12px; background: #ff9800; color: #fff; padding: 2px 6px; border-radius: 3px; }}
        .filter-tag {{ font-size: 12px; padding: 2px 6px; border-radius: 3px; }}
        .filter-tag.passed {{ background: #e8f5e9; color: #2e7d32; }}
        .filter-tag.filtered {{ background: #ffebee; color: #c62828; }}
        .title {{ font-size: 16px; font-weight: 500; margin-bottom: 5px; }}
        .title a {{ color: #1976d2; text-decoration: none; }}
        .title a:hover {{ text-decoration: underline; }}
        .summary {{ font-size: 14px; color: #666; line-height: 1.5; }}
        .content-preview {{ font-size: 13px; color: #888; margin-top: 8px; padding: 10px; background: #f9f9f9; border-radius: 4px; line-height: 1.6; }}
        .footer {{ text-align: center; margin-top: 20px; color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TrendRadar 爬虫报告</h1>
            <p style="color: #666; margin-bottom: 15px;">更新时间: {timestamp} (每10秒自动刷新)</p>
            <div class="stats">
                <div class="stat-item">
                    <div class="label">总爬取次数</div>
                    <div class="value">{self.stats['total_fetches']}</div>
                </div>
                <div class="stat-item">
                    <div class="label">累计条目</div>
                    <div class="value">{self.stats['total_items']}</div>
                </div>
                <div class="stat-item">
                    <div class="label">新增条目</div>
                    <div class="value">{self.stats['new_items']}</div>
                </div>
                <div class="stat-item">
                    <div class="label">通过过滤</div>
                    <div class="value">{self.stats['passed_items']}</div>
                </div>
                <div class="stat-item">
                    <div class="label">被过滤</div>
                    <div class="value">{self.stats['filtered_items']}</div>
                </div>
                <div class="stat-item">
                    <div class="label">当前显示</div>
                    <div class="value">{len(self.recent_items)}</div>
                </div>
            </div>
        </div>

        <div class="news-list">
            {items_html if items_html else '<div style="padding: 40px; text-align: center; color: #999;">暂无数据</div>'}
        </div>

        <div class="footer">
            <p>TrendRadar Custom Crawler | 轮询间隔: {self.poll_interval}秒 | 最大显示: {self.max_display_items}条</p>
        </div>
    </div>
</body>
</html>
'''
        return html

    def run(self, duration: int = 0) -> None:
        """运行爬虫

        Args:
            duration: 运行时长（秒），0 表示无限运行
        """
        self.running = True
        start_time = time.time()

        print(f"[爬虫] 开始运行，轮询间隔 {self.poll_interval} 秒")
        if duration > 0:
            print(f"[爬虫] 计划运行 {duration} 秒")

        # 首次爬取
        self.crawl_once()
        self.generate_html_report()

        while self.running:
            # 检查运行时长
            if duration > 0 and time.time() - start_time >= duration:
                print("[爬虫] 达到计划运行时长，停止")
                break

            # 等待
            for _ in range(self.poll_interval):
                if not self.running:
                    break
                time.sleep(1)

            if not self.running:
                break

            # 爬取
            self.crawl_once()
            self.generate_html_report()

        print("[爬虫] 已停止")

    def stop(self) -> None:
        """停止运行"""
        self.running = False

    def cleanup(self) -> None:
        """清理资源"""
        self.manager.cleanup()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="TrendRadar 自定义爬虫运行器")
    parser.add_argument("-d", "--duration", type=int, default=0, help="运行时长（秒），0 表示无限运行")
    parser.add_argument("-i", "--interval", type=int, help="轮询间隔（秒），覆盖配置文件")
    parser.add_argument("--once", action="store_true", help="只运行一次")
    args = parser.parse_args()

    # 加载配置
    print("=" * 60)
    print("TrendRadar 自定义爬虫")
    print("=" * 60)

    config = load_config()

    # 命令行参数覆盖
    if args.interval:
        config["CRAWLER_CUSTOM"]["POLL_INTERVAL"] = args.interval

    # 创建应用
    app = CrawlerApp(config)

    # 信号处理
    def signal_handler(sig, frame):
        print("\n[爬虫] 收到停止信号...")
        app.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        if args.once:
            # 只运行一次
            app.crawl_once()
            app.generate_html_report()
        else:
            # 持续运行
            app.run(duration=args.duration)
    finally:
        app.cleanup()


if __name__ == "__main__":
    main()
