#!/usr/bin/env python3
# coding=utf-8
"""
爬虫守护进程

独立运行的自定义爬虫守护进程，支持：
- 10秒轮询（可配置）
- 即时推送通知（Phase 1）
- AI 分析队列 + 增强推送（Phase 2）
- 支持 SimpleAnalyzer 或 CrewAI 分析器
- 独立于主流程运行

用法:
    python scripts/run_crawler_daemon.py [options]

选项:
    -i, --interval  轮询间隔（秒），默认 10
    -d, --duration  运行时长（秒），0 表示无限运行，默认 0
    --no-push       禁用推送通知
    --enable-ai     启用 AI 分析（Phase 2 增强推送）
    --use-crewai    使用 CrewAI 分析器（默认使用 SimpleAnalyzer）
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
import requests
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Callable

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from trendradar.logging import setup_logging, get_logger
from trendradar.core.loader import load_config
from trendradar.core.config_manager import ConfigManager
from trendradar.crawler.runner import CrawlerRunner
from trendradar.crawler.custom import CrawlerNewsItem, FetchStatus
from trendradar.notification.simple_senders import (
    send_simple_feishu,
    send_simple_dingtalk,
    send_simple_wework,
    send_simple_telegram,
)
from trendradar.constants import Timeouts

# 初始化日志器
logger = get_logger("daemon")


class CrawlerDaemon:
    """爬虫守护进程"""

    def __init__(
        self,
        config: dict,
        poll_interval: int = 10,
        enable_push: bool = True,
        enable_ai: bool = False,
        use_crewai: bool = False,
        verbose: bool = False,
    ):
        self.config = config
        self.cfg = ConfigManager(config)  # 类型安全的配置访问
        self.poll_interval = poll_interval
        self.enable_push = enable_push
        self.enable_ai = enable_ai
        self.use_crewai = use_crewai
        self.verbose = verbose

        # 创建运行器
        self.runner = CrawlerRunner(config)

        # 状态
        self._running = False
        self._stop_event = threading.Event()

        # AI 分析组件
        self._ai_analyzer = None
        self._ai_queue = None
        self._ai_thread = None

        # 统计
        self.stats = {
            "start_time": None,
            "total_polls": 0,
            "successful_polls": 0,
            "failed_polls": 0,
            "total_new_items": 0,
            "total_pushed": 0,
            "total_ai_analyzed": 0,
            "total_ai_pushed": 0,
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
            timezone = self.cfg.app.timezone
            tz = pytz.timezone(timezone)

            def get_time_func():
                return datetime.now(tz)

            # 初始化通知器
            self._notifier = NotificationDispatcher(
                config=self.config,
                get_time_func=get_time_func,
                split_content_func=split_content_into_batches,
            )
            logger.info("通知器初始化成功")
        except Exception as e:
            logger.error("通知器初始化失败: %s", e)
            self._notifier = None

    def _init_ai(self):
        """初始化 AI 分析组件"""
        if not self.enable_ai:
            return

        try:
            from trendradar.ai.queue.manager import AIQueueManager

            # 根据配置选择分析器
            if self.use_crewai:
                try:
                    from trendradar.ai.analyzers import CREWAI_AVAILABLE, create_crew_analyzer
                    if not CREWAI_AVAILABLE:
                        raise ImportError("CrewAI 未安装")
                    self._ai_analyzer = create_crew_analyzer(self.config, multi_agent=False)
                    logger.info("CrewAI 分析器初始化成功，模型: %s", self._ai_analyzer.model)
                except ImportError as e:
                    logger.warning("CrewAI 不可用，回退到 SimpleAnalyzer: %s", e)
                    from trendradar.ai.analyzers.simple import SimpleAnalyzer
                    self._ai_analyzer = SimpleAnalyzer(self.config)
                    logger.info("AI 分析器初始化成功，模型: %s", self._ai_analyzer.model)
            else:
                from trendradar.ai.analyzers.simple import SimpleAnalyzer
                self._ai_analyzer = SimpleAnalyzer(self.config)
                logger.info("AI 分析器初始化成功，模型: %s", self._ai_analyzer.model)

            # 创建队列管理器（使用 ConfigManager 类型安全访问）
            queue_cfg = self.cfg.ai.queue
            self._ai_queue = AIQueueManager(
                max_size=queue_cfg.max_size,
                max_workers=queue_cfg.workers,
                max_retries=queue_cfg.retry_count,
            )

            # 设置处理函数
            self._ai_queue.set_processor(self._process_ai_item)
            self._ai_queue.set_result_callback(self._on_ai_result)

            # 启动队列
            self._ai_queue.start()
            logger.info("AI 队列已启动")

        except Exception as e:
            logger.error("AI 初始化失败: %s", e)
            self._ai_analyzer = None
            self._ai_queue = None
            self.enable_ai = False

    def _process_ai_item(self, item: CrawlerNewsItem):
        """处理单条新闻的 AI 分析"""
        if not self._ai_analyzer:
            return None

        content = item.full_content or item.summary or ""
        if not content:
            return None

        result = self._ai_analyzer.analyze(
            news_id=item.seq,
            title=item.title,
            content=content
        )

        return {
            "item": item,
            "result": result,
        }

    def _on_ai_result(self, task_id: str, data: dict, success: bool):
        """AI 分析完成回调"""
        if not success or not data:
            return

        self.stats["total_ai_analyzed"] += 1

        item = data.get("item")
        result = data.get("result")

        if not result or not result.success:
            return

        if self.verbose:
            logger.debug("分析完成: %s... -> %s...", item.title[:30], result.summary[:30])

        # Phase 2: 发送增强推送
        if self.enable_push:
            self._send_ai_enhanced_notification(item, result)

    def _send_ai_enhanced_notification(self, item: CrawlerNewsItem, result):
        """发送 AI 增强推送（Phase 2，支持多账号）"""
        try:
            # 构建增强内容
            keywords_str = ", ".join(result.keywords) if result.keywords else "无"
            sentiment_emoji = {"positive": "📈", "negative": "📉", "neutral": "➡️"}.get(result.sentiment, "➡️")

            # 格式化发布时间
            pub_time = item.published_at if item.published_at else "未知"

            text_content = f"""🤖 AI 分析报告

📰 {item.title}
🕐 发布时间: {pub_time}

📝 摘要: {result.summary}

🏷️ 关键词: {keywords_str}
{sentiment_emoji} 情感: {result.sentiment}
⭐ 重要性: {'⭐' * result.importance}

🔗 {item.url}
"""
            subject = "AI 分析报告"

            # 发送到各渠道
            pushed = False
            notif = self.cfg.notification  # 类型安全的通知配置

            # 飞书推送
            if notif.feishu_webhook_url:
                if send_simple_feishu(
                    notif.feishu_webhook_url,
                    subject, text_content,
                    verbose=self.verbose
                ):
                    pushed = True

            # 钉钉推送
            if notif.dingtalk_webhook_url:
                if send_simple_dingtalk(
                    notif.dingtalk_webhook_url,
                    subject, text_content,
                    verbose=self.verbose
                ):
                    pushed = True

            # 企业微信推送
            if notif.wework_webhook_url:
                if send_simple_wework(
                    notif.wework_webhook_url,
                    subject, text_content,
                    msg_type=notif.wework_msg_type,
                    verbose=self.verbose
                ):
                    pushed = True

            # Telegram 推送
            if notif.telegram_bot_token and notif.telegram_chat_id:
                if send_simple_telegram(
                    notif.telegram_bot_token,
                    notif.telegram_chat_id,
                    subject, text_content,
                    verbose=self.verbose
                ):
                    pushed = True

            # 写入推送队列供 LangBot 读取
            self._write_push_queue(
                push_type="ai_analysis",
                subject=f"AI分析：{item.title}",
                text_content=text_content,
                items=[item],
                ai_result=result
            )

            if pushed:
                self.stats["total_ai_pushed"] += 1
                if self.verbose:
                    logger.debug("AI 增强推送成功")

        except Exception as e:
            logger.error("AI 增强推送失败: %s", e)

    def _write_push_queue(self, push_type: str, subject: str, text_content: str,
                          html_content: str = None, items: list = None, ai_result=None):
        """写入推送队列供 LangBot 读取"""
        import json
        import uuid

        try:
            queue_dir = Path(self.config.get("CONFIG_DIR", "/app/config")) / ".push_queue"
            queue_dir.mkdir(exist_ok=True)

            push_data = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "type": push_type,  # "raw" | "ai_analysis"
                "subject": subject,
                "text_content": text_content,
                "html_content": html_content,
                "status": "pending"
            }

            if items:
                push_data["items"] = [
                    {
                        "title": getattr(i, 'title', ''),
                        "url": getattr(i, 'url', ''),
                        "summary": getattr(i, 'summary', '')[:200] if getattr(i, 'summary', '') else '',
                        "published_at": getattr(i, 'published_at', ''),
                        "matched_keywords": getattr(i, 'matched_keywords', [])
                    }
                    for i in items
                ]

            if ai_result:
                push_data["ai_result"] = {
                    "summary": getattr(ai_result, 'summary', ''),
                    "keywords": getattr(ai_result, 'keywords', []),
                    "sentiment": getattr(ai_result, 'sentiment', ''),
                    "importance": getattr(ai_result, 'importance', 0),
                    "category": getattr(ai_result, 'category', ''),
                    "entities": getattr(ai_result, 'entities', []),
                    "tags": getattr(ai_result, 'tags', []),
                    # BatchAnalysisResult 字段 (如果有)
                    "core_trends": getattr(ai_result, 'core_trends', ''),
                    "sentiment_controversy": getattr(ai_result, 'sentiment_controversy', ''),
                    "signals": getattr(ai_result, 'signals', ''),
                    "rss_insights": getattr(ai_result, 'rss_insights', ''),
                    "outlook_strategy": getattr(ai_result, 'outlook_strategy', ''),
                }

            # 原子写入：先写临时文件，再重命名
            filename = f"{push_data['timestamp'].replace(':', '-')}_{push_data['id'][:8]}.json"
            tmp_path = queue_dir / f".tmp_{filename}"
            final_path = queue_dir / filename

            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(push_data, f, ensure_ascii=False, indent=2)
            tmp_path.rename(final_path)

            if self.verbose:
                logger.debug("推送队列写入: %s", filename)

        except Exception as e:
            if self.verbose:
                logger.debug("推送队列写入失败: %s", e)

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
                        logger.debug("AI Worker 错误: %s", e)

        self._ai_thread = threading.Thread(target=ai_worker, daemon=True, name="ai-worker")
        self._ai_thread.start()
        if self.verbose:
            logger.debug("AI 分析线程已启动（预留）")

    def _send_notification(self, new_items: list):
        """发送即时通知（支持多渠道、多账号）"""
        if not new_items:
            return

        try:
            # 过滤：只推送通过过滤的条目
            items_to_push = [item for item in new_items if not item.filtered_out]

            if not items_to_push:
                if self.verbose:
                    logger.debug("%d 条新增均被过滤，跳过推送", len(new_items))
                return

            # 构建推送内容
            html_content = self._build_push_content(items_to_push)
            text_content = self._build_text_content(items_to_push)
            subject = f"[同花顺快讯] {len(items_to_push)} 条新消息"

            pushed = False
            notif = self.cfg.notification  # 类型安全的通知配置

            # 邮件推送（使用简化的直接发送）
            if notif.email_enabled and notif.email_from and notif.email_to:
                try:
                    self._send_email_direct(subject, html_content)
                    pushed = True
                    if self.verbose:
                        logger.debug("邮件推送成功")
                except Exception as e:
                    logger.error("邮件推送失败: %s", e)

            # 飞书推送
            if notif.feishu_webhook_url:
                if send_simple_feishu(
                    notif.feishu_webhook_url,
                    subject, text_content,
                    verbose=self.verbose
                ):
                    pushed = True

            # 钉钉推送
            if notif.dingtalk_webhook_url:
                if send_simple_dingtalk(
                    notif.dingtalk_webhook_url,
                    subject, text_content,
                    verbose=self.verbose
                ):
                    pushed = True

            # 企业微信推送
            if notif.wework_webhook_url:
                if send_simple_wework(
                    notif.wework_webhook_url,
                    subject, text_content,
                    msg_type=notif.wework_msg_type,
                    verbose=self.verbose
                ):
                    pushed = True

            # Telegram 推送
            if notif.telegram_bot_token and notif.telegram_chat_id:
                if send_simple_telegram(
                    notif.telegram_bot_token,
                    notif.telegram_chat_id,
                    subject, text_content,
                    verbose=self.verbose
                ):
                    pushed = True

            # 写入推送队列供 LangBot 读取
            self._write_push_queue(
                push_type="raw",
                subject=subject,
                text_content=text_content,
                html_content=html_content,
                items=items_to_push
            )

            if pushed:
                self.stats["total_pushed"] += len(items_to_push)
                logger.info("推送 %d 条新消息", len(items_to_push))
            elif self.verbose:
                logger.debug("未配置任何推送渠道")

        except Exception as e:
            logger.error("推送失败: %s", e)

    def _build_text_content(self, items: list) -> str:
        """构建纯文本推送内容（用于飞书/钉钉等）"""
        lines = [
            f"📰 同花顺快讯 - {len(items)} 条新消息",
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "━" * 30,
        ]

        for i, item in enumerate(items, 1):
            keywords = ", ".join(item.matched_keywords) if item.matched_keywords else ""
            keyword_tag = f" 【{keywords}】" if keywords else ""
            lines.append(f"\n{i}. {item.title}{keyword_tag}")
            lines.append(f"   {item.published_at}")
            if item.summary:
                summary = item.summary[:100] + "..." if len(item.summary) > 100 else item.summary
                lines.append(f"   {summary}")
            lines.append(f"   🔗 {item.url}")

        return "\n".join(lines)

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

    def _send_email_direct(self, subject: str, html_content: str):
        """直接发送邮件（不依赖文件）"""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        notif = self.cfg.notification  # 类型安全的邮件配置
        from_email = notif.email_from
        password = notif.email_password
        to_email = notif.email_to
        smtp_server = notif.email_smtp_server
        smtp_port = notif.email_smtp_port

        if not all([from_email, password, to_email]):
            raise ValueError("邮件配置不完整")

        # 自动识别 SMTP 服务器
        if not smtp_server:
            domain = from_email.split("@")[-1].lower()
            smtp_servers = {
                "qq.com": ("smtp.qq.com", 465),
                "163.com": ("smtp.163.com", 465),
                "126.com": ("smtp.126.com", 465),
                "gmail.com": ("smtp.gmail.com", 587),
                "outlook.com": ("smtp.office365.com", 587),
                "hotmail.com": ("smtp.office365.com", 587),
            }
            if domain in smtp_servers:
                smtp_server, smtp_port = smtp_servers[domain]
            else:
                smtp_server = f"smtp.{domain}"
                smtp_port = 465

        smtp_port = int(smtp_port) if smtp_port else 465

        # 构建邮件
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email

        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(html_part)

        # 发送
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=Timeouts.SMTP_CONNECT) as server:
                server.login(from_email, password)
                server.sendmail(from_email, to_email.split(","), msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=Timeouts.SMTP_CONNECT) as server:
                server.starttls()
                server.login(from_email, password)
                server.sendmail(from_email, to_email.split(","), msg.as_string())

    def run_once(self) -> dict:
        """执行一次爬取"""
        # 延迟初始化 AI（支持 --once 模式）
        if self.enable_ai and self._ai_analyzer is None:
            self._init_ai()

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
                    logger.debug("发现 %d 条新消息", len(new_items))

                # 即时推送
                if self.enable_push:
                    self._send_notification(new_items)

                # 加入 AI 分析队列
                if self.enable_ai and self._ai_queue:
                    for item in new_items:
                        if not item.filtered_out:  # 只分析通过过滤的条目
                            try:
                                self._ai_queue.enqueue(item)
                            except Exception as e:
                                if self.verbose:
                                    logger.debug("AI 入队失败: %s", e)

            self.stats["successful_polls"] += 1
            return {"success": True, "new_count": len(new_items), "results": results}

        except Exception as e:
            self.stats["failed_polls"] += 1
            logger.error("爬取错误: %s", e)
            return {"success": False, "error": str(e)}

    def run(self, duration: int = 0):
        """运行守护进程

        Args:
            duration: 运行时长（秒），0 表示无限运行
        """
        self._running = True
        self.stats["start_time"] = datetime.now().isoformat()

        logger.info("启动爬虫守护进程")
        logger.info("轮询间隔: %ds", self.poll_interval)
        logger.info("推送通知: %s", "启用" if self.enable_push else "禁用")
        logger.info("AI 分析: %s", "启用" if self.enable_ai else "禁用")

        # 初始化
        self._init_notifier()
        if self.enable_ai:
            self._init_ai()

        # 注册信号处理
        def signal_handler(sig, frame):
            logger.info("收到停止信号，正在退出...")
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
                logger.info("达到运行时长 %ds，退出", duration)
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

        # 停止 AI 队列
        if self._ai_queue:
            logger.info("停止 AI 分析队列...")
            self._ai_queue.stop(wait=True, timeout=10.0)

        # 输出统计
        self._print_stats()

    def _print_stats(self):
        """打印统计信息"""
        elapsed = 0
        if self.stats["start_time"]:
            start = datetime.fromisoformat(self.stats["start_time"])
            elapsed = (datetime.now() - start).total_seconds()

        logger.info("")
        logger.info("=" * 50)
        logger.info("运行统计")
        logger.info("=" * 50)
        logger.info("运行时长: %.0fs", elapsed)
        logger.info("总轮询次数: %d", self.stats['total_polls'])
        logger.info("成功次数: %d", self.stats['successful_polls'])
        logger.info("失败次数: %d", self.stats['failed_polls'])
        logger.info("发现新消息: %d 条", self.stats['total_new_items'])
        logger.info("推送消息: %d 条", self.stats['total_pushed'])
        if self.enable_ai:
            logger.info("-" * 50)
            logger.info("AI 分析完成: %d 条", self.stats['total_ai_analyzed'])
            logger.info("AI 推送消息: %d 条", self.stats['total_ai_pushed'])
        logger.info("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="爬虫守护进程")
    parser.add_argument("-i", "--interval", type=int, default=10, help="轮询间隔（秒）")
    parser.add_argument("-d", "--duration", type=int, default=0, help="运行时长（秒），0 表示无限")
    parser.add_argument("--no-push", action="store_true", help="禁用推送通知")
    parser.add_argument("--enable-ai", action="store_true", help="启用 AI 分析")
    parser.add_argument("--use-crewai", action="store_true", help="使用 CrewAI 分析器（默认使用 SimpleAnalyzer）")
    parser.add_argument("--once", action="store_true", help="只运行一次")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    args = parser.parse_args()

    # 初始化日志系统
    log_level = 'DEBUG' if args.verbose else 'INFO'
    setup_logging(level=log_level)

    # 加载配置
    logger.info("加载配置...")
    config = load_config()

    # 创建守护进程
    daemon = CrawlerDaemon(
        config=config,
        poll_interval=args.interval,
        enable_push=not args.no_push,
        enable_ai=args.enable_ai,
        use_crewai=args.use_crewai,
        verbose=args.verbose,
    )

    if args.once:
        # 单次运行模式
        result = daemon.run_once()
        logger.info("单次运行完成: %s", result)
    else:
        # 守护进程模式
        daemon.run(duration=args.duration)


if __name__ == "__main__":
    main()
