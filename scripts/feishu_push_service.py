#!/usr/bin/env python3
# coding=utf-8
"""
飞书推送服务

独立运行的服务，监听推送队列目录，将消息发送到飞书群聊。
支持多目标推送（多个 chat_id 和 open_id）。

用法:
    python scripts/feishu_push_service.py [options]

选项:
    --once          只处理一次队列
    --verbose       详细输出
"""

import argparse
import json
import os
import sys
import time
import sqlite3
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class FeishuClient:
    """飞书 API 客户端"""

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._tenant_token = None
        self._token_expires_at = 0

    def _get_tenant_token(self) -> str:
        """获取租户访问令牌"""
        # 检查缓存的 token 是否有效
        if self._tenant_token and time.time() < self._token_expires_at - 60:
            return self._tenant_token

        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise Exception(f"获取 tenant_token 失败: {data.get('msg')}")

        self._tenant_token = data["tenant_access_token"]
        self._token_expires_at = time.time() + data.get("expire", 7200)
        return self._tenant_token

    def send_message(self, receive_id: str, receive_id_type: str, msg_type: str, content: dict) -> dict:
        """发送消息

        Args:
            receive_id: 接收者 ID (chat_id 或 open_id)
            receive_id_type: ID 类型 (chat_id, open_id, user_id, email)
            msg_type: 消息类型 (text, post, interactive, etc.)
            content: 消息内容

        Returns:
            API 响应
        """
        token = self._get_tenant_token()
        url = f"{self.BASE_URL}/im/v1/messages"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }

        params = {"receive_id_type": receive_id_type}
        body = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps(content, ensure_ascii=False)
        }

        resp = requests.post(url, headers=headers, params=params, json=body, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def send_text(self, receive_id: str, text: str, receive_id_type: str = "chat_id") -> dict:
        """发送文本消息"""
        return self.send_message(receive_id, receive_id_type, "text", {"text": text})

    def send_post(self, receive_id: str, title: str, content_lines: list, receive_id_type: str = "chat_id") -> dict:
        """发送富文本消息"""
        post_content = {
            "zh_cn": {
                "title": title,
                "content": content_lines
            }
        }
        return self.send_message(receive_id, receive_id_type, "post", post_content)


class FeishuPushService:
    """飞书推送服务"""

    def __init__(
        self,
        queue_dir: Path,
        chat_ids: List[str] = None,
        open_ids: List[str] = None,
        app_id: str = None,
        app_secret: str = None,
        langbot_db_path: Path = None,
        poll_interval: int = 2,
        verbose: bool = False
    ):
        self.queue_dir = Path(queue_dir)
        self.processed_dir = self.queue_dir / ".processed"
        self.chat_ids = chat_ids or []
        self.open_ids = open_ids or []
        self.poll_interval = poll_interval
        self.verbose = verbose

        # 获取飞书凭证
        if app_id and app_secret:
            self.app_id = app_id
            self.app_secret = app_secret
        elif langbot_db_path and langbot_db_path.exists():
            self.app_id, self.app_secret = self._load_credentials_from_langbot(langbot_db_path)
        else:
            raise ValueError("必须提供 app_id/app_secret 或 langbot_db_path")

        self.client = FeishuClient(self.app_id, self.app_secret)

        # 确保目录存在
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        # 统计
        self.stats = {
            "processed": 0,
            "sent": 0,
            "failed": 0,
            "start_time": None
        }

    def _load_credentials_from_langbot(self, db_path: Path) -> tuple:
        """从 LangBot 数据库加载飞书凭证"""
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT adapter_config FROM bots WHERE adapter = 'lark' LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise ValueError("LangBot 数据库中未找到飞书配置")

        config = json.loads(row[0])
        return config["app_id"], config["app_secret"]

    def _format_raw_message(self, data: dict) -> list:
        """格式化原始消息为富文本"""
        lines = []

        # 标题行
        lines.append([{"tag": "text", "text": f"📰 {data.get('subject', '新消息')}\n"}])
        lines.append([{"tag": "text", "text": "━" * 20 + "\n"}])

        # 消息内容
        items = data.get("items", [])
        for i, item in enumerate(items[:10], 1):  # 限制最多10条
            title = item.get("title", "")
            url = item.get("url", "")
            published_at = item.get("published_at", "")
            keywords = item.get("matched_keywords", [])
            keyword_tag = f" 【{', '.join(keywords)}】" if keywords else ""

            # 新闻标题
            lines.append([
                {"tag": "text", "text": f"{i}. {title}{keyword_tag}\n"}
            ])
            # 发布时间
            if published_at:
                lines.append([
                    {"tag": "text", "text": f"   🕐 {published_at}\n"}
                ])
            # 链接
            if url:
                lines.append([
                    {"tag": "text", "text": "   🔗 "},
                    {"tag": "a", "text": "查看原文", "href": url},
                    {"tag": "text", "text": "\n"}
                ])

        if len(items) > 10:
            lines.append([{"tag": "text", "text": f"\n... 还有 {len(items) - 10} 条消息"}])

        return lines

    def _format_ai_message(self, data: dict) -> list:
        """格式化 AI 分析消息为富文本"""
        lines = []
        ai_result = data.get("ai_result", {})
        items = data.get("items", [])

        # 标题
        item_title = items[0].get("title", "AI分析") if items else "AI分析"
        lines.append([{"tag": "text", "text": f"🤖 AI 分析报告\n"}])
        lines.append([{"tag": "text", "text": "━" * 20 + "\n"}])

        # 新闻标题和发布时间
        if items:
            item = items[0]
            url = item.get("url", "")
            published_at = item.get("published_at", "")

            lines.append([{"tag": "text", "text": f"📰 {item_title}\n"}])
            # 发布时间
            if published_at:
                lines.append([{"tag": "text", "text": f"🕐 发布时间: {published_at}\n"}])
            if url:
                lines.append([
                    {"tag": "text", "text": "🔗 "},
                    {"tag": "a", "text": "查看原文", "href": url},
                    {"tag": "text", "text": "\n"}
                ])

        lines.append([{"tag": "text", "text": "\n"}])

        # AI 分析结果
        if ai_result.get("summary"):
            lines.append([{"tag": "text", "text": f"📝 摘要: {ai_result['summary']}\n"}])

        if ai_result.get("keywords"):
            keywords_str = ", ".join(ai_result["keywords"])
            lines.append([{"tag": "text", "text": f"🏷️ 关键词: {keywords_str}\n"}])

        if ai_result.get("sentiment"):
            sentiment_emoji = {"positive": "📈", "negative": "📉", "neutral": "➡️"}.get(ai_result["sentiment"], "➡️")
            lines.append([{"tag": "text", "text": f"{sentiment_emoji} 情感: {ai_result['sentiment']}\n"}])

        if ai_result.get("importance"):
            stars = "⭐" * ai_result["importance"]
            lines.append([{"tag": "text", "text": f"重要性: {stars}\n"}])

        return lines

    def _format_daily_report(self, data: dict) -> list:
        """格式化日报消息为富文本"""
        lines = []
        message = data.get("message", "")

        # 直接使用预格式化的消息文本
        if message:
            for line in message.split("\n"):
                lines.append([{"tag": "text", "text": line + "\n"}])
        else:
            # 如果没有预格式化消息，使用 items 构建
            items = data.get("items", [])
            lines.append([{"tag": "text", "text": "📰 TrendRadar 财经日报\n"}])
            lines.append([{"tag": "text", "text": "━" * 20 + "\n"}])

            for i, item in enumerate(items[:10], 1):
                title = item.get("title", "")
                source = item.get("source", "未知")
                lines.append([{"tag": "text", "text": f"{i}. {title}\n"}])
                lines.append([{"tag": "text", "text": f"   📍 {source}\n"}])

        return lines

    def _process_file(self, file_path: Path) -> bool:
        """处理单个推送文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 根据类型格式化消息
            push_type = data.get("type", "raw")
            if push_type == "ai_analysis":
                title = "AI 分析报告"
                content_lines = self._format_ai_message(data)
            elif push_type == "daily_report":
                title = data.get("subject", "TrendRadar 日报")
                content_lines = self._format_daily_report(data)
            else:
                title = data.get("subject", "同花顺快讯")
                content_lines = self._format_raw_message(data)

            # 发送到所有目标
            success_count = 0

            for chat_id in self.chat_ids:
                try:
                    result = self.client.send_post(chat_id, title, content_lines, "chat_id")
                    if result.get("code") == 0:
                        success_count += 1
                        if self.verbose:
                            print(f"[Feishu] 发送到群聊 {chat_id[:20]}... 成功")
                    else:
                        print(f"[Feishu] 发送到群聊失败: {result.get('msg')}")
                except Exception as e:
                    print(f"[Feishu] 发送到群聊异常: {e}")

            for open_id in self.open_ids:
                try:
                    result = self.client.send_post(open_id, title, content_lines, "open_id")
                    if result.get("code") == 0:
                        success_count += 1
                        if self.verbose:
                            print(f"[Feishu] 发送到用户 {open_id[:20]}... 成功")
                    else:
                        print(f"[Feishu] 发送到用户失败: {result.get('msg')}")
                except Exception as e:
                    print(f"[Feishu] 发送到用户异常: {e}")

            # 移动到已处理目录
            processed_path = self.processed_dir / file_path.name
            file_path.rename(processed_path)

            self.stats["processed"] += 1
            if success_count > 0:
                self.stats["sent"] += 1
            else:
                self.stats["failed"] += 1

            return success_count > 0

        except Exception as e:
            print(f"[Feishu] 处理文件失败 {file_path}: {e}")
            self.stats["failed"] += 1
            # 移动到已处理目录（避免重复处理失败文件）
            try:
                error_path = self.processed_dir / f"error_{file_path.name}"
                file_path.rename(error_path)
            except:
                pass
            return False

    def process_queue(self) -> int:
        """处理队列中的所有文件"""
        # 获取所有待处理文件（排除临时文件和隐藏文件）
        files = sorted([
            f for f in self.queue_dir.glob("*.json")
            if not f.name.startswith(".") and not f.name.startswith("error_")
        ])

        processed = 0
        for file_path in files:
            if self._process_file(file_path):
                processed += 1

        return processed

    def run(self, once: bool = False):
        """运行服务"""
        print(f"[Feishu] 飞书推送服务启动")
        print(f"[Feishu] 队列目录: {self.queue_dir}")
        print(f"[Feishu] 目标群聊: {self.chat_ids}")
        print(f"[Feishu] 目标用户: {self.open_ids}")
        print(f"[Feishu] 轮询间隔: {self.poll_interval}s")

        self.stats["start_time"] = datetime.now().isoformat()

        if once:
            processed = self.process_queue()
            print(f"[Feishu] 单次处理完成，处理 {processed} 条消息")
            return

        # 持续运行
        try:
            while True:
                processed = self.process_queue()
                if processed > 0 and self.verbose:
                    print(f"[Feishu] 处理 {processed} 条消息")
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            print("\n[Feishu] 收到停止信号，正在退出...")
        finally:
            self._print_stats()

    def _print_stats(self):
        """打印统计"""
        print("\n" + "=" * 40)
        print("[Feishu] 运行统计")
        print("=" * 40)
        print(f"处理消息: {self.stats['processed']}")
        print(f"发送成功: {self.stats['sent']}")
        print(f"发送失败: {self.stats['failed']}")
        print("=" * 40)


def main():
    parser = argparse.ArgumentParser(description="飞书推送服务")
    parser.add_argument("--queue-dir", default="/app/config/.push_queue",
                        help="推送队列目录")
    parser.add_argument("--langbot-db", default="/app/data/langbot.db",
                        help="LangBot 数据库路径")
    parser.add_argument("--chat-ids", default="",
                        help="目标群聊 ID，逗号分隔")
    parser.add_argument("--open-ids", default="",
                        help="目标用户 open_id，逗号分隔")
    parser.add_argument("--app-id", default="",
                        help="飞书 App ID")
    parser.add_argument("--app-secret", default="",
                        help="飞书 App Secret")
    parser.add_argument("--interval", type=int, default=2,
                        help="轮询间隔（秒）")
    parser.add_argument("--once", action="store_true",
                        help="只处理一次")
    parser.add_argument("--verbose", action="store_true",
                        help="详细输出")
    args = parser.parse_args()

    # 解析目标 ID
    chat_ids = [x.strip() for x in args.chat_ids.split(",") if x.strip()]
    open_ids = [x.strip() for x in args.open_ids.split(",") if x.strip()]

    # 从环境变量读取（如果命令行未提供）
    if not chat_ids:
        env_chat_ids = os.environ.get("FEISHU_CHAT_IDS", "")
        chat_ids = [x.strip() for x in env_chat_ids.split(",") if x.strip()]
    if not open_ids:
        env_open_ids = os.environ.get("FEISHU_OPEN_IDS", "")
        open_ids = [x.strip() for x in env_open_ids.split(",") if x.strip()]

    if not chat_ids and not open_ids:
        print("[Feishu] 错误: 必须指定至少一个目标 (--chat-ids 或 --open-ids)")
        sys.exit(1)

    # 处理路径
    queue_dir = Path(args.queue_dir)
    langbot_db = Path(args.langbot_db) if args.langbot_db else None

    # 凭证
    app_id = args.app_id or os.environ.get("FEISHU_APP_ID", "")
    app_secret = args.app_secret or os.environ.get("FEISHU_APP_SECRET", "")

    # 创建服务
    service = FeishuPushService(
        queue_dir=queue_dir,
        chat_ids=chat_ids,
        open_ids=open_ids,
        app_id=app_id if app_id else None,
        app_secret=app_secret if app_secret else None,
        langbot_db_path=langbot_db if not app_id else None,
        poll_interval=args.interval,
        verbose=args.verbose
    )

    service.run(once=args.once)


if __name__ == "__main__":
    main()
