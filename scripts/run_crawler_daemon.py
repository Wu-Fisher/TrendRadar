#!/usr/bin/env python3
# coding=utf-8
"""
爬虫守护进程

独立运行的自定义爬虫守护进程，支持：
- 10秒轮询（可配置）
- 即时推送通知
- AI 分析队列（预留）
- 独立于主流程运行

用法:
    python scripts/run_crawler_daemon.py [options]

选项:
    -i, --interval  轮询间隔（秒），默认 10
    -d, --duration  运行时长（秒），0 表示无限运行，默认 0
    --no-push       禁用推送通知
    --once          只运行一次
    --verbose       详细输出
"""

import argparse
import os
import sys
import time
import signal
import queue
import threading
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from trendradar.core.loader import load_config
from trendradar.crawler.runner import CrawlerRunner
from trendradar.crawler.custom import CrawlerNewsItem, FetchStatus


class CrawlerDaemon:
    """爬虫守护进程"""

    def __init__(
        self,
        config: dict,
        poll_interval: int = 10,
        enable_push: bool = True,
        verbose: bool = False,
    ):
        self.config = config
        self.poll_interval = poll_interval
        self.enable_push = enable_push
        self.verbose = verbose

        # 创建运行器
        self.runner = CrawlerRunner(config)

        # 状态
        self._running = False
        self._stop_event = threading.Event()

        # AI 分析队列（预留）
        self.ai_queue: queue.Queue = queue.Queue(maxsize=100)
        self._ai_thread = None

        # 统计
        self.stats = {
            "start_time": None,
            "total_polls": 0,
            "successful_polls": 0,
            "failed_polls": 0,
            "total_new_items": 0,
            "total_pushed": 0,
            "last_poll_time": None,
            "last_new_time": None,
        }

        # 通知器（延迟初始化）
        self._notifier = None

    def _init_notifier(self):
        """初始化通知器"""
        if not self.enable_push:
            return

        try:
            from trendradar.notification.dispatcher import NotificationDispatcher
            from trendradar.notification.splitter import split_content_into_batches
            from trendradar.context import AppContext
            import pytz

            # 创建时间函数
            timezone = self.config.get("TIMEZONE", "Asia/Shanghai")
            tz = pytz.timezone(timezone)

            def get_time_func():
                return datetime.now(tz)

            # 初始化通知器
            self._notifier = NotificationDispatcher(
                config=self.config,
                get_time_func=get_time_func,
                split_content_func=split_content_into_batches,
            )
            print("[Daemon] 通知器初始化成功")
        except Exception as e:
            print(f"[Daemon] 通知器初始化失败: {e}")
            self._notifier = None

    def _start_ai_worker(self):
        """启动 AI 分析后台线程（预留）"""
        def ai_worker():
            while self._running:
                try:
                    # 从队列获取待分析条目
                    item = self.ai_queue.get(timeout=1)
                    if item is None:
                        continue

                    # TODO: 实现 AI 分析逻辑
                    # self._analyze_item(item)

                    self.ai_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    if self.verbose:
                        print(f"[AI Worker] 错误: {e}")

        self._ai_thread = threading.Thread(target=ai_worker, daemon=True, name="ai-worker")
        self._ai_thread.start()
        if self.verbose:
            print("[Daemon] AI 分析线程已启动（预留）")

    def _send_notification(self, new_items: list):
        """发送即时通知"""
        if not self._notifier or not new_items:
            return

        try:
            # 过滤：只推送通过过滤的条目
            items_to_push = [item for item in new_items if not item.filtered_out]

            if not items_to_push:
                if self.verbose:
                    print(f"[Daemon] {len(new_items)} 条新增均被过滤，跳过推送")
                return

            # 构建简化的推送内容
            content = self._build_push_content(items_to_push)

            # 使用通知器发送
            # 这里简化处理，直接调用邮件发送
            if hasattr(self._notifier, 'ctx') and self._notifier.ctx:
                from trendradar.notification.senders import send_email

                email_config = self.config.get("NOTIFICATION", {}).get("EMAIL", {})
                if email_config.get("ENABLED"):
                    subject = f"[同花顺快讯] {len(items_to_push)} 条新消息"
                    send_email(
                        subject=subject,
                        body=content,
                        config=self.config,
                        is_html=True,
                    )
                    self.stats["total_pushed"] += len(items_to_push)
                    print(f"[Daemon] 推送 {len(items_to_push)} 条新消息")

        except Exception as e:
            print(f"[Daemon] 推送失败: {e}")

    def _build_push_content(self, items: list) -> str:
        """构建推送内容"""
        lines = [
            "<html><body>",
            f"<h2>同花顺快讯 - {len(items)} 条新消息</h2>",
            f"<p>时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
            "<hr>",
        ]

        for item in items:
            keywords = ", ".join(item.matched_keywords) if item.matched_keywords else "无"
            lines.append(f"""
            <div style="margin-bottom: 15px; padding: 10px; border-left: 3px solid #1890ff;">
                <strong>{item.title}</strong><br>
                <span style="color: #666; font-size: 12px;">
                    {item.published_at} | 关键词: {keywords}
                </span><br>
                <p style="color: #333; margin: 5px 0;">{item.summary[:200] if item.summary else ''}</p>
                <a href="{item.url}" style="color: #1890ff;">查看原文</a>
            </div>
            """)

        lines.append("</body></html>")
        return "\n".join(lines)

    def run_once(self) -> dict:
        """执行一次爬取"""
        self.stats["total_polls"] += 1
        self.stats["last_poll_time"] = datetime.now().isoformat()

        try:
            results = self.runner.crawl_once()

            # 统计新增
            new_items = []
            for source_id, result in results.items():
                if result.status == FetchStatus.SUCCESS and result.new_count > 0:
                    # 获取新增条目
                    for item in result.items[:result.new_count]:
                        new_items.append(item)

            if new_items:
                self.stats["total_new_items"] += len(new_items)
                self.stats["last_new_time"] = datetime.now().isoformat()

                if self.verbose:
                    print(f"[Daemon] 发现 {len(new_items)} 条新消息")

                # 即时推送
                if self.enable_push:
                    self._send_notification(new_items)

                # 加入 AI 分析队列（预留）
                for item in new_items:
                    try:
                        self.ai_queue.put_nowait(item)
                    except queue.Full:
                        pass

            self.stats["successful_polls"] += 1
            return {"success": True, "new_count": len(new_items), "results": results}

        except Exception as e:
            self.stats["failed_polls"] += 1
            print(f"[Daemon] 爬取错误: {e}")
            return {"success": False, "error": str(e)}

    def run(self, duration: int = 0):
        """运行守护进程

        Args:
            duration: 运行时长（秒），0 表示无限运行
        """
        self._running = True
        self.stats["start_time"] = datetime.now().isoformat()

        print(f"[Daemon] 启动爬虫守护进程")
        print(f"[Daemon] 轮询间隔: {self.poll_interval}s")
        print(f"[Daemon] 推送通知: {'启用' if self.enable_push else '禁用'}")

        # 初始化
        self._init_notifier()
        self._start_ai_worker()

        # 注册信号处理
        def signal_handler(sig, frame):
            print("\n[Daemon] 收到停止信号，正在退出...")
            self._running = False
            self._stop_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        start_time = time.time()

        # 立即执行一次
        self.run_once()

        # 轮询循环
        while self._running:
            # 检查运行时长
            if duration > 0 and (time.time() - start_time) >= duration:
                print(f"[Daemon] 达到运行时长 {duration}s，退出")
                break

            # 等待下一次
            if self._stop_event.wait(timeout=self.poll_interval):
                break

            if not self._running:
                break

            # 执行爬取
            self.run_once()

        # 清理
        self._running = False
        self.runner.cleanup()

        # 输出统计
        self._print_stats()

    def _print_stats(self):
        """打印统计信息"""
        elapsed = 0
        if self.stats["start_time"]:
            start = datetime.fromisoformat(self.stats["start_time"])
            elapsed = (datetime.now() - start).total_seconds()

        print("\n" + "=" * 50)
        print("[Daemon] 运行统计")
        print("=" * 50)
        print(f"运行时长: {elapsed:.0f}s")
        print(f"总轮询次数: {self.stats['total_polls']}")
        print(f"成功次数: {self.stats['successful_polls']}")
        print(f"失败次数: {self.stats['failed_polls']}")
        print(f"发现新消息: {self.stats['total_new_items']} 条")
        print(f"推送消息: {self.stats['total_pushed']} 条")
        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="爬虫守护进程")
    parser.add_argument("-i", "--interval", type=int, default=10, help="轮询间隔（秒）")
    parser.add_argument("-d", "--duration", type=int, default=0, help="运行时长（秒），0 表示无限")
    parser.add_argument("--no-push", action="store_true", help="禁用推送通知")
    parser.add_argument("--once", action="store_true", help="只运行一次")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()

    # 加载配置
    print("[Daemon] 加载配置...")
    config = load_config()

    # 创建守护进程
    daemon = CrawlerDaemon(
        config=config,
        poll_interval=args.interval,
        enable_push=not args.no_push,
        verbose=args.verbose,
    )

    if args.once:
        # 单次运行模式
        result = daemon.run_once()
        print(f"[Daemon] 单次运行完成: {result}")
    else:
        # 守护进程模式
        daemon.run(duration=args.duration)


if __name__ == "__main__":
    main()
