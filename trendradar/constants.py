# coding=utf-8
"""
TrendRadar 常量定义

集中管理所有魔法数字和字符串常量，便于维护和修改。
"""

from typing import Dict


# === 消息批次大小（字节）===
# 各推送渠道的消息大小限制
class BatchSizes:
    """消息批次大小限制（字节）"""
    FEISHU = 29000       # 飞书 webhook 限制约 30KB，预留 buffer
    DINGTALK = 20000     # 钉钉 markdown 限制约 20KB
    WEWORK = 4000        # 企业微信限制较小
    TELEGRAM = 4000      # Telegram 单条消息限制 4096 字节
    BARK = 3600          # Bark 使用 APNs，限制 4KB
    NTFY = 3800          # ntfy 限制 4KB
    SLACK = 4000         # Slack 消息限制
    DEFAULT = 4000       # 默认安全值

    @classmethod
    def get(cls, channel: str) -> int:
        """获取指定渠道的批次大小"""
        return getattr(cls, channel.upper(), cls.DEFAULT)


# === 分隔符 ===
class Separators:
    """消息分隔符"""
    FEISHU = "━" * 20
    DEFAULT = "━" * 30
    LINE = "─" * 40
    SECTION = "═" * 40


# === 超时设置（秒）===
class Timeouts:
    """各类操作超时设置"""
    AI_ANALYSIS = 120        # AI 分析超时
    HTTP_REQUEST = 30        # 一般 HTTP 请求
    CONTENT_FETCH = 10       # 内容获取
    SMTP_CONNECT = 30        # SMTP 连接


# === 数量限制 ===
class Limits:
    """各类数量限制"""
    MAX_NEWS_FOR_ANALYSIS = 50      # AI 分析最大新闻数
    MAX_ACCOUNTS_PER_CHANNEL = 3    # 每渠道最大账号数
    MAX_ITEMS_DISPLAY = 100         # 最大显示条目数
    MAX_QUEUE_SIZE = 100            # AI 队列最大容量
    MAX_QUEUE_WORKERS = 2           # AI 队列工作线程数
    MAX_RETRIES = 3                 # 最大重试次数


# === 轮询间隔（秒）===
class Intervals:
    """轮询和等待间隔"""
    DAEMON_POLL = 10         # daemon 轮询间隔
    BATCH_SEND = 3           # 批次发送间隔
    RETRY_DELAY = 5.0        # 重试延迟


# === AI 模型配置默认值 ===
class AIDefaults:
    """AI 配置默认值"""
    TIMEOUT = 120
    MAX_TOKENS = 5000
    TEMPERATURE = 1.0
    NUM_RETRIES = 2


# === 配置键名映射 ===
# 统一使用大写键名，此映射用于兼容小写键名
CONFIG_KEY_ALIASES: Dict[str, str] = {
    "timeout": "TIMEOUT",
    "max_tokens": "MAX_TOKENS",
    "queue": "QUEUE",
    "workers": "WORKERS",
    "max_size": "MAX_SIZE",
    "retry_count": "RETRY_COUNT",
}


def normalize_config_key(key: str) -> str:
    """标准化配置键名为大写"""
    return CONFIG_KEY_ALIASES.get(key, key.upper())


# === 日志前缀 ===
class LogPrefixes:
    """日志输出前缀"""
    DAEMON = "[Daemon]"
    AI = "[AI]"
    AI_QUEUE = "[AI Queue]"
    AI_WORKER = "[AI Worker]"
    CRAWLER = "[Crawler]"
    NOTIFICATION = "[Notification]"


# === 推送类型 ===
class PushTypes:
    """推送队列消息类型"""
    RAW = "raw"                 # 原始消息
    AI_ANALYSIS = "ai_analysis"  # AI 分析消息


# === 情感分析标签 ===
class Sentiments:
    """情感分析标签"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

    EMOJIS = {
        "positive": "📈",
        "negative": "📉",
        "neutral": "➡️",
    }

    @classmethod
    def get_emoji(cls, sentiment: str) -> str:
        return cls.EMOJIS.get(sentiment, cls.EMOJIS["neutral"])
