# TrendRadar PushQueue Plugin - 事件监听器
# 监听 .push_queue 目录，处理推送消息并发送到飞书
"""
配置项 (通过 LangBot WebUI 设置):
- bot_uuid: LangBot Bot UUID
- target_type: 目标类型 (group/person)
- target_id: 飞书群 chat_id
- queue_dir: 推送队列目录
- poll_interval: 轮询间隔（秒）
- feishu_app_id: 飞书应用 App ID
- feishu_app_secret: 飞书应用 App Secret
"""
from __future__ import annotations

import json
import asyncio
import logging
import time
import httpx
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from langbot_plugin.api.definition.components.common.event_listener import EventListener

logger = logging.getLogger('PushQueue')


class FeishuDirectSender:
    """飞书 API 消息发送器"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: Optional[str] = None
        self._token_expire: float = 0

    async def _get_token(self) -> str:
        """获取 tenant_access_token（带缓存）"""
        if self._token and time.time() < self._token_expire - 300:
            return self._token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret}
            )
            data = resp.json()
            if data.get("code") == 0:
                self._token = data["tenant_access_token"]
                self._token_expire = time.time() + data.get("expire", 7200)
                return self._token
            raise Exception(f"获取飞书 token 失败: {data}")

    async def send_message(self, chat_id: str, text: str) -> Dict[str, Any]:
        """发送文本消息"""
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": chat_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text})
                }
            )
            data = resp.json()
            if data.get("code") == 0:
                return data
            raise Exception(f"飞书消息发送失败: {data}")

    async def send_post_message(self, chat_id: str, title: str, content_elements: list) -> Dict[str, Any]:
        """发送富文本消息 (post 格式，与 LangBot 相同)"""
        token = await self._get_token()
        post_content = {
            "zh_cn": {
                "title": title,
                "content": content_elements  # [[{"tag": "text", "text": "..."}, {"tag": "a", "href": "...", "text": "链接"}]]
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": chat_id,
                    "msg_type": "post",
                    "content": json.dumps(post_content)
                }
            )
            data = resp.json()
            if data.get("code") == 0:
                return data
            raise Exception(f"飞书富文本消息发送失败: {data}")

    async def send_card_message(self, chat_id: str, card_content: dict) -> Dict[str, Any]:
        """发送卡片消息 (interactive 格式)"""
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": chat_id,
                    "msg_type": "interactive",
                    "content": json.dumps(card_content)
                }
            )
            data = resp.json()
            if data.get("code") == 0:
                return data
            raise Exception(f"飞书卡片消息发送失败: {data}")


class PushQueueEventListener(EventListener):
    """推送队列监听器 - 轮询目录并发送消息到飞书"""

    def __init__(self):
        super().__init__()
        self.target_id: Optional[str] = None
        self.queue_dir: Optional[Path] = None
        self.processed_dir: Optional[Path] = None
        self.poll_interval: int = 2
        self.default_msg_format: str = "card"  # 默认消息格式
        self._running: bool = False
        self._poll_task: Optional[asyncio.Task] = None
        self.feishu_sender: Optional[FeishuDirectSender] = None
        self.stats = {"processed": 0, "sent": 0, "failed": 0}

    async def initialize(self):
        await super().initialize()
        config = self.plugin.get_config()

        # 配置
        self.target_id = config.get("target_id")
        self.poll_interval = config.get("poll_interval", 2)
        self.default_msg_format = config.get("default_msg_format", "card")  # 从配置读取
        queue_path = config.get("queue_dir", "/app/trendradar_config/.push_queue")
        self.queue_dir = Path(queue_path)
        self.processed_dir = self.queue_dir / ".processed"

        # 飞书直连
        feishu_app_id = config.get("feishu_app_id")
        feishu_app_secret = config.get("feishu_app_secret")
        if feishu_app_id and feishu_app_secret:
            self.feishu_sender = FeishuDirectSender(feishu_app_id, feishu_app_secret)
            logger.info("PushQueue: 飞书直连模式已启用")
        else:
            logger.warning("PushQueue: 未配置飞书凭证")
            return

        if not self.target_id:
            logger.error("PushQueue: 缺少 target_id 配置")
            return

        # 确保目录存在
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        # 启动轮询
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_queue())
        logger.info(f"PushQueue: 已启动 (queue={self.queue_dir}, interval={self.poll_interval}s)")

    async def _poll_queue(self):
        """轮询队列目录"""
        while self._running:
            try:
                await self._process_queue()
            except Exception as e:
                logger.error(f"PushQueue: 轮询错误 - {e}")
            await asyncio.sleep(self.poll_interval)

    async def _process_queue(self):
        """处理队列中的所有文件"""
        if not self.queue_dir or not self.queue_dir.exists():
            return

        files = sorted([
            f for f in self.queue_dir.glob("*.json")
            if not f.name.startswith(".") and not f.name.startswith("error_")
        ])

        for file_path in files:
            await self._process_file(file_path)

    async def _process_file(self, file_path: Path):
        """处理单个推送文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not self.feishu_sender or not self.target_id:
                return

            # 支持指定消息格式: card (默认), post (富文本), text (纯文本)
            # 优先使用消息中指定的格式，否则使用配置的默认格式
            msg_format = data.get("msg_format", self.default_msg_format)

            if msg_format == "card":
                card_content = self._build_card_content(data)
                await self.feishu_sender.send_card_message(self.target_id, card_content)
                logger.info(f"PushQueue: 发送卡片消息成功")
            elif msg_format == "post":
                title, elements = self._build_post_content(data)
                await self.feishu_sender.send_post_message(self.target_id, title, elements)
                logger.info(f"PushQueue: 发送富文本消息成功")
            else:
                message_text = self._build_message_text(data)
                if message_text:
                    await self.feishu_sender.send_message(self.target_id, message_text)

            self.stats["sent"] += 1

            # 移动到已处理目录
            (self.processed_dir / file_path.name).unlink(missing_ok=True)
            file_path.rename(self.processed_dir / file_path.name)
            self.stats["processed"] += 1

        except Exception as e:
            logger.error(f"PushQueue: 处理失败 {file_path.name} - {e}")
            self.stats["failed"] += 1
            try:
                file_path.rename(self.processed_dir / f"error_{file_path.name}")
            except Exception:
                pass

    def _build_message_text(self, data: Dict[str, Any]) -> str:
        """构建消息文本"""
        push_type = data.get("type", "raw")
        if push_type == "ai_analysis":
            return self._build_ai_text(data)
        elif push_type == "daily_report":
            return self._build_daily_text(data)
        return self._build_raw_text(data)

    def _build_post_content(self, data: Dict[str, Any]) -> tuple:
        """构建富文本 (post) 消息内容，返回 (title, content_elements)"""
        push_type = data.get("type", "raw")
        title = data.get("subject", "TrendRadar 推送")
        elements = []

        if push_type == "ai_analysis":
            ai = data.get("ai_result", {})
            items = data.get("items", [])
            if items:
                item = items[0]
                elements.append([
                    {"tag": "text", "text": "📰 "},
                    {"tag": "a", "href": item.get("url", ""), "text": item.get("title", "新闻标题")}
                ])
            if ai.get("summary"):
                elements.append([{"tag": "text", "text": f"\n📝 {ai['summary']}"}])
            if ai.get("keywords"):
                elements.append([{"tag": "text", "text": f"\n🏷️ {', '.join(ai['keywords'])}"}])
        else:
            for i, item in enumerate(data.get("items", [])[:10], 1):
                line = [{"tag": "text", "text": f"{i}. "}]
                if item.get("url"):
                    line.append({"tag": "a", "href": item["url"], "text": item.get("title", "")})
                else:
                    line.append({"tag": "text", "text": item.get("title", "")})
                keywords = item.get("matched_keywords", [])
                if keywords:
                    line.append({"tag": "text", "text": f" 【{', '.join(keywords)}】"})
                elements.append(line)

        return title, elements

    def _build_card_content(self, data: Dict[str, Any]) -> dict:
        """构建卡片消息内容"""
        push_type = data.get("type", "raw")
        title = data.get("subject", "TrendRadar 推送")

        # 构建 Markdown 内容
        md_lines = []
        if push_type == "ai_analysis":
            ai = data.get("ai_result", {})
            items = data.get("items", [])

            # 新闻标题和时间
            if items:
                item = items[0]
                md_lines.append(f"**📰 [{item.get('title', '')}]({item.get('url', '')})**")
                if item.get("published_at"):
                    md_lines.append(f"🕐 {item['published_at']}")
                md_lines.append("")  # 空行

            # 完整显示 AI 分析内容
            # 优先级: core_trends > summary
            main_analysis = (
                ai.get("core_trends") or
                ai.get("summary") or ""
            )
            if main_analysis:
                md_lines.append(f"**📝 分析报告**\n{main_analysis}")

            # 舆论风向
            if ai.get("sentiment_controversy"):
                md_lines.append(f"\n**💬 舆论风向**\n{ai['sentiment_controversy']}")

            # 异动信号
            if ai.get("signals"):
                md_lines.append(f"\n**⚡ 异动信号**\n{ai['signals']}")

            # RSS 洞察
            if ai.get("rss_insights"):
                md_lines.append(f"\n**🔍 深度洞察**\n{ai['rss_insights']}")

            # 策略建议
            if ai.get("outlook_strategy"):
                md_lines.append(f"\n**💡 策略建议**\n{ai['outlook_strategy']}")

            # 关键词和实体
            if ai.get("keywords"):
                md_lines.append(f"\n🏷️ 关键词: `{', '.join(ai['keywords'])}`")
            if ai.get("entities"):
                md_lines.append(f"🏢 相关实体: `{', '.join(ai['entities'])}`")

            # 情感和重要性
            sentiment_map = {"positive": "📈 积极", "negative": "📉 消极", "neutral": "➖ 中性"}
            if ai.get("sentiment"):
                md_lines.append(f"情感倾向: {sentiment_map.get(ai['sentiment'], ai['sentiment'])}")
            if ai.get("importance"):
                md_lines.append(f"重要性: {'⭐' * ai['importance']}")

        else:
            # 普通新闻列表
            for i, item in enumerate(data.get("items", [])[:10], 1):
                line_parts = []
                if item.get("url"):
                    line_parts.append(f"{i}. [{item.get('title', '')}]({item['url']})")
                else:
                    line_parts.append(f"{i}. {item.get('title', '')}")

                # 添加时间戳
                if item.get("published_at"):
                    line_parts.append(f"  🕐 {item['published_at']}")

                # 添加关键词标签
                keywords = item.get("matched_keywords", [])
                if keywords:
                    line_parts.append(f"  🏷️ {', '.join(keywords)}")

                md_lines.append("\n".join(line_parts))

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue"
            },
            "elements": [
                {"tag": "markdown", "content": "\n\n".join(md_lines)},
                {"tag": "hr"},
                {"tag": "note", "elements": [
                    {"tag": "plain_text", "content": "📡 TrendRadar 财经监控"}
                ]}
            ]
        }

    def _build_raw_text(self, data: Dict[str, Any]) -> str:
        """原始消息格式"""
        lines = [f"📰 {data.get('subject', '新消息')}", "━" * 20]
        for i, item in enumerate(data.get("items", [])[:10], 1):
            keywords = item.get("matched_keywords", [])
            tag = f" 【{', '.join(keywords)}】" if keywords else ""
            lines.append(f"\n{i}. {item.get('title', '')}{tag}")
            if item.get("published_at"):
                lines.append(f"   🕐 {item['published_at']}")
            if item.get("url"):
                lines.append(f"   🔗 {item['url']}")
        if len(data.get("items", [])) > 10:
            lines.append(f"\n... 还有 {len(data['items']) - 10} 条")
        return "\n".join(lines)

    def _build_ai_text(self, data: Dict[str, Any]) -> str:
        """AI 分析消息格式"""
        lines = ["🤖 AI 分析报告", "━" * 20]
        ai = data.get("ai_result", {})
        items = data.get("items", [])
        if items:
            lines.append(f"📰 {items[0].get('title', '')}")
            if items[0].get("url"):
                lines.append(f"🔗 {items[0]['url']}")
        if ai.get("summary"):
            lines.append(f"\n📝 {ai['summary']}")
        if ai.get("keywords"):
            lines.append(f"🏷️ {', '.join(ai['keywords'])}")
        return "\n".join(lines)

    def _build_daily_text(self, data: Dict[str, Any]) -> str:
        """日报消息格式"""
        if data.get("message"):
            return data["message"]
        lines = [f"📰 {data.get('subject', 'TrendRadar 日报')}", "━" * 20]
        for i, item in enumerate(data.get("items", [])[:10], 1):
            lines.append(f"{i}. {item.get('title', '')}")
            if item.get("source"):
                lines.append(f"   📍 {item['source']}")
        return "\n".join(lines)

    async def terminate(self):
        """停止插件"""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info(f"PushQueue: 停止 (processed={self.stats['processed']}, sent={self.stats['sent']}, failed={self.stats['failed']})")
        await super().terminate()
