# TrendRadar PushQueue Plugin - 事件监听器
# 监听 .push_queue 目录，处理推送消息
from __future__ import annotations

import os
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.platform import message as platform_message

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('PushQueue')


class PushQueueEventListener(EventListener):
    """推送队列监听器"""

    def __init__(self):
        super().__init__()
        self.bot_uuid = None
        self.target_type = "group"
        self.target_id = None
        self.queue_dir = None
        self.processed_dir = None
        self.poll_interval = 2  # 轮询间隔（秒）
        self._running = False
        self._poll_task = None

        # 统计
        self.stats = {
            "processed": 0,
            "sent": 0,
            "failed": 0,
            "start_time": None
        }

    async def initialize(self):
        await super().initialize()
        print("[PushQueue] initialize() 开始执行")

        # 从插件配置获取参数
        config = self.plugin.get_config()
        print(f"[PushQueue] 配置: {config}")
        self.bot_uuid = config.get("bot_uuid")
        self.target_type = config.get("target_type", "group")
        self.target_id = config.get("target_id")
        self.poll_interval = config.get("poll_interval", 2)

        # 队列目录
        queue_path = config.get("queue_dir", "/app/trendradar_config/.push_queue")
        self.queue_dir = Path(queue_path)
        self.processed_dir = self.queue_dir / ".processed"

        # 确保目录存在
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"PushQueue 插件初始化")
        logger.info(f"  bot_uuid: {self.bot_uuid}")
        logger.info(f"  target_type: {self.target_type}")
        logger.info(f"  target_id: {self.target_id}")
        logger.info(f"  queue_dir: {self.queue_dir}")
        logger.info(f"  poll_interval: {self.poll_interval}s")

        if not self.bot_uuid or not self.target_id:
            print("[PushQueue] 错误: 缺少必要配置 (bot_uuid 或 target_id)")
            logger.error("PushQueue: 缺少必要配置 (bot_uuid 或 target_id)")
            return

        # 启动轮询任务
        self._running = True
        self.stats["start_time"] = datetime.now().isoformat()
        self._poll_task = asyncio.create_task(self._poll_queue())
        print("[PushQueue] 队列轮询已启动")
        logger.info("PushQueue: 队列轮询已启动")

    async def _poll_queue(self):
        """轮询队列目录"""
        print(f"[PushQueue] _poll_queue 开始运行, queue_dir={self.queue_dir}")
        while self._running:
            try:
                await self._process_queue()
            except Exception as e:
                print(f"[PushQueue] 轮询错误: {e}")
                logger.error(f"PushQueue: 轮询错误 - {e}")

            await asyncio.sleep(self.poll_interval)

    async def _process_queue(self):
        """处理队列中的所有文件"""
        if not self.queue_dir.exists():
            return

        # 获取所有待处理文件
        files = sorted([
            f for f in self.queue_dir.glob("*.json")
            if not f.name.startswith(".") and not f.name.startswith("error_")
        ])

        if files:
            print(f"[PushQueue] 发现 {len(files)} 个待处理文件")

        for file_path in files:
            await self._process_file(file_path)

    async def _process_file(self, file_path: Path):
        """处理单个推送文件"""
        print(f"[PushQueue] 处理文件: {file_path.name}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 构建消息
            message_chain = self._build_message(data)

            if message_chain:
                # 通过 LangBot 发送消息
                await self.plugin.send_message(
                    bot_uuid=self.bot_uuid,
                    target_type=self.target_type,
                    target_id=self.target_id,
                    message_chain=message_chain,
                )
                logger.info(f"PushQueue: 发送成功 - {file_path.name}")
                self.stats["sent"] += 1

            # 移动到已处理目录
            processed_path = self.processed_dir / file_path.name
            file_path.rename(processed_path)
            self.stats["processed"] += 1

        except Exception as e:
            logger.error(f"PushQueue: 处理失败 {file_path.name} - {e}")
            self.stats["failed"] += 1

            # 移动到错误文件
            try:
                error_path = self.processed_dir / f"error_{file_path.name}"
                file_path.rename(error_path)
            except:
                pass

    def _build_message(self, data: Dict[str, Any]) -> platform_message.MessageChain:
        """根据数据构建消息"""
        push_type = data.get("type", "raw")

        if push_type == "ai_analysis":
            return self._build_ai_message(data)
        elif push_type == "daily_report":
            return self._build_daily_report(data)
        else:
            return self._build_raw_message(data)

    def _build_raw_message(self, data: Dict[str, Any]) -> platform_message.MessageChain:
        """构建原始消息"""
        lines = []
        subject = data.get("subject", "新消息")
        items = data.get("items", [])

        lines.append(f"📰 {subject}")
        lines.append("━" * 20)

        for i, item in enumerate(items[:10], 1):
            title = item.get("title", "")
            url = item.get("url", "")
            published_at = item.get("published_at", "")
            keywords = item.get("matched_keywords", [])
            keyword_tag = f" 【{', '.join(keywords)}】" if keywords else ""

            lines.append(f"\n{i}. {title}{keyword_tag}")
            if published_at:
                lines.append(f"   🕐 {published_at}")
            if url:
                lines.append(f"   🔗 {url}")

        if len(items) > 10:
            lines.append(f"\n... 还有 {len(items) - 10} 条消息")

        text = "\n".join(lines)
        return platform_message.MessageChain([platform_message.Plain(text=text)])

    def _build_ai_message(self, data: Dict[str, Any]) -> platform_message.MessageChain:
        """构建 AI 分析消息"""
        lines = []
        ai_result = data.get("ai_result", {})
        items = data.get("items", [])

        lines.append("🤖 AI 分析报告")
        lines.append("━" * 20)

        # 新闻标题
        if items:
            item = items[0]
            lines.append(f"📰 {item.get('title', 'AI分析')}")
            if item.get("published_at"):
                lines.append(f"🕐 发布时间: {item['published_at']}")
            if item.get("url"):
                lines.append(f"🔗 {item['url']}")
            lines.append("")

        # AI 分析结果
        if ai_result.get("summary"):
            lines.append(f"📝 摘要: {ai_result['summary']}")

        if ai_result.get("keywords"):
            lines.append(f"🏷️ 关键词: {', '.join(ai_result['keywords'])}")

        if ai_result.get("sentiment"):
            emoji = {"positive": "📈", "negative": "📉", "neutral": "➡️"}.get(
                ai_result["sentiment"], "➡️"
            )
            lines.append(f"{emoji} 情感: {ai_result['sentiment']}")

        if ai_result.get("importance"):
            lines.append(f"⭐ 重要性: {'⭐' * ai_result['importance']}")

        text = "\n".join(lines)
        return platform_message.MessageChain([platform_message.Plain(text=text)])

    def _build_daily_report(self, data: Dict[str, Any]) -> platform_message.MessageChain:
        """构建日报消息"""
        # 如果有预格式化消息，直接使用
        message = data.get("message", "")
        if message:
            return platform_message.MessageChain([platform_message.Plain(text=message)])

        # 否则从 items 构建
        lines = []
        items = data.get("items", [])
        subject = data.get("subject", "TrendRadar 日报")

        lines.append(f"📰 {subject}")
        lines.append("━" * 20)

        for i, item in enumerate(items[:10], 1):
            title = item.get("title", "")
            source = item.get("source", "未知")
            lines.append(f"{i}. {title}")
            lines.append(f"   📍 {source}")

        text = "\n".join(lines)
        return platform_message.MessageChain([platform_message.Plain(text=text)])

    async def terminate(self):
        """停止插件"""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        # 输出统计
        logger.info("=" * 40)
        logger.info("PushQueue 运行统计")
        logger.info("=" * 40)
        logger.info(f"处理消息: {self.stats['processed']}")
        logger.info(f"发送成功: {self.stats['sent']}")
        logger.info(f"发送失败: {self.stats['failed']}")
        logger.info("=" * 40)

        await super().terminate()
