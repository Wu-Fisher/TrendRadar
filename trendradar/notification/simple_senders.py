# coding=utf-8
"""
简化消息发送器 - 供 daemon 即时推送使用

与完整的 senders.py 不同，这里不需要分批逻辑，
只提供单条消息的快速发送，用于 daemon 模式的即时推送。

设计原则：
- 轻量级：不依赖复杂的 split_content_func
- 多账号支持：URL 用分号分隔，最多支持 MAX_ACCOUNTS_PER_CHANNEL 个账号
- 统一接口：所有函数签名一致，便于统一调用
"""

import requests
from typing import Optional

from trendradar.logging import get_logger
from trendradar.constants import Limits, Timeouts

logger = get_logger(__name__)


def send_simple_feishu(
    webhook_url: str,
    subject: str,
    content: str,
    verbose: bool = False
) -> bool:
    """
    发送飞书 webhook 消息（支持多账号）

    Args:
        webhook_url: Webhook URL，多个用分号分隔
        subject: 消息标题
        content: 消息内容
        verbose: 是否输出详细日志

    Returns:
        是否至少有一个账号发送成功
    """
    urls = [url.strip() for url in webhook_url.split(";") if url.strip()]
    success = False

    for i, url in enumerate(urls[:Limits.MAX_ACCOUNTS_PER_CHANNEL]):
        account_label = f"[{i+1}]" if len(urls) > 1 else ""
        try:
            payload = {
                "msg_type": "text",
                "content": {"text": f"{subject}\n\n{content}"}
            }
            response = requests.post(url, json=payload, timeout=Timeouts.HTTP_REQUEST)

            if response.status_code == 200:
                result = response.json()
                if result.get("StatusCode") == 0 or result.get("code") == 0:
                    if verbose:
                        logger.debug("飞书%s推送成功", account_label)
                    success = True
                else:
                    logger.warning("飞书%s推送失败: %s", account_label,
                                   result.get("msg", "未知错误"))
            else:
                logger.warning("飞书%s推送失败: HTTP %d", account_label, response.status_code)

        except requests.RequestException as e:
            logger.error("飞书%s推送网络异常: %s", account_label, e)
        except Exception as e:
            logger.exception("飞书%s推送未预期异常", account_label)

    return success


def send_simple_dingtalk(
    webhook_url: str,
    subject: str,
    content: str,
    verbose: bool = False
) -> bool:
    """
    发送钉钉 webhook 消息（支持多账号）

    Args:
        webhook_url: Webhook URL，多个用分号分隔
        subject: 消息标题
        content: 消息内容
        verbose: 是否输出详细日志

    Returns:
        是否至少有一个账号发送成功
    """
    urls = [url.strip() for url in webhook_url.split(";") if url.strip()]
    success = False

    for i, url in enumerate(urls[:Limits.MAX_ACCOUNTS_PER_CHANNEL]):
        account_label = f"[{i+1}]" if len(urls) > 1 else ""
        try:
            payload = {
                "msgtype": "markdown",
                "markdown": {"title": subject, "text": f"## {subject}\n\n{content}"}
            }
            response = requests.post(url, json=payload, timeout=Timeouts.HTTP_REQUEST)

            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    if verbose:
                        logger.debug("钉钉%s推送成功", account_label)
                    success = True
                else:
                    logger.warning("钉钉%s推送失败: %s", account_label,
                                   result.get("errmsg", "未知错误"))
            else:
                logger.warning("钉钉%s推送失败: HTTP %d", account_label, response.status_code)

        except requests.RequestException as e:
            logger.error("钉钉%s推送网络异常: %s", account_label, e)
        except Exception as e:
            logger.exception("钉钉%s推送未预期异常", account_label)

    return success


def send_simple_wework(
    webhook_url: str,
    subject: str,
    content: str,
    msg_type: str = "markdown",
    verbose: bool = False
) -> bool:
    """
    发送企业微信 webhook 消息（支持多账号）

    Args:
        webhook_url: Webhook URL，多个用分号分隔
        subject: 消息标题
        content: 消息内容
        msg_type: 消息类型 (markdown/text)
        verbose: 是否输出详细日志

    Returns:
        是否至少有一个账号发送成功
    """
    urls = [url.strip() for url in webhook_url.split(";") if url.strip()]
    success = False

    for i, url in enumerate(urls[:Limits.MAX_ACCOUNTS_PER_CHANNEL]):
        account_label = f"[{i+1}]" if len(urls) > 1 else ""
        try:
            if msg_type.lower() == "text":
                payload = {"msgtype": "text", "text": {"content": f"{subject}\n\n{content}"}}
            else:
                payload = {"msgtype": "markdown", "markdown": {"content": f"## {subject}\n\n{content}"}}

            response = requests.post(url, json=payload, timeout=Timeouts.HTTP_REQUEST)

            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    if verbose:
                        logger.debug("企业微信%s推送成功", account_label)
                    success = True
                else:
                    logger.warning("企业微信%s推送失败: %s", account_label,
                                   result.get("errmsg", "未知错误"))
            else:
                logger.warning("企业微信%s推送失败: HTTP %d", account_label, response.status_code)

        except requests.RequestException as e:
            logger.error("企业微信%s推送网络异常: %s", account_label, e)
        except Exception as e:
            logger.exception("企业微信%s推送未预期异常", account_label)

    return success


def send_simple_telegram(
    bot_token: str,
    chat_id: str,
    subject: str,
    content: str,
    verbose: bool = False
) -> bool:
    """
    发送 Telegram 消息（支持多账号）

    Args:
        bot_token: Bot Token，多个用分号分隔
        chat_id: Chat ID，多个用分号分隔（需与 bot_token 数量一致）
        subject: 消息标题
        content: 消息内容
        verbose: 是否输出详细日志

    Returns:
        是否至少有一个账号发送成功
    """
    tokens = [t.strip() for t in bot_token.split(";") if t.strip()]
    chat_ids = [c.strip() for c in chat_id.split(";") if c.strip()]

    if len(tokens) != len(chat_ids):
        logger.error("Telegram 配置错误: bot_token 和 chat_id 数量不匹配 (%d vs %d)",
                     len(tokens), len(chat_ids))
        return False

    success = False
    for i, (token, cid) in enumerate(zip(tokens[:Limits.MAX_ACCOUNTS_PER_CHANNEL],
                                          chat_ids[:Limits.MAX_ACCOUNTS_PER_CHANNEL])):
        account_label = f"[{i+1}]" if len(tokens) > 1 else ""
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": cid,
                "text": f"<b>{subject}</b>\n\n{content}",
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            response = requests.post(url, json=payload, timeout=Timeouts.HTTP_REQUEST)

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    if verbose:
                        logger.debug("Telegram%s推送成功", account_label)
                    success = True
                else:
                    logger.warning("Telegram%s推送失败: %s", account_label,
                                   result.get("description", "未知错误"))
            else:
                logger.warning("Telegram%s推送失败: HTTP %d", account_label, response.status_code)

        except requests.RequestException as e:
            logger.error("Telegram%s推送网络异常: %s", account_label, e)
        except Exception as e:
            logger.exception("Telegram%s推送未预期异常", account_label)

    return success
