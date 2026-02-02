# coding=utf-8
"""
配置管理器模块

提供类型安全的配置访问接口，封装原始配置字典为 dataclass 对象。

使用方式：
    from trendradar.core.config_manager import ConfigManager

    # 从现有配置字典创建
    config = load_config()
    manager = ConfigManager(config)

    # 类型安全的访问
    timeout = manager.ai.timeout  # int
    webhook = manager.notification.feishu_webhook_url  # str

    # 访问原始配置（向后兼容）
    raw_value = manager.get("SOME_KEY", default_value)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from trendradar.logging import get_logger

logger = get_logger(__name__)


# ============================================================
# AI 配置
# ============================================================

@dataclass(frozen=True)
class AIQueueConfig:
    """AI 队列配置"""
    max_size: int = 100
    workers: int = 2
    retry_count: int = 3


@dataclass(frozen=True)
class AIConfig:
    """AI 模型配置（LiteLLM 格式）"""
    model: str = "deepseek/deepseek-chat"
    api_key: str = ""
    api_base: str = ""
    timeout: int = 120
    temperature: float = 1.0
    max_tokens: int = 5000
    num_retries: int = 2
    fallback_models: List[str] = field(default_factory=list)
    extra_params: Dict[str, Any] = field(default_factory=dict)
    queue: AIQueueConfig = field(default_factory=AIQueueConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIConfig":
        """从字典创建 AIConfig"""
        queue_data = data.get("QUEUE", {})
        queue = AIQueueConfig(
            max_size=queue_data.get("MAX_SIZE", 100),
            workers=queue_data.get("WORKERS", 2),
            retry_count=queue_data.get("RETRY_COUNT", 3),
        )
        return cls(
            model=data.get("MODEL", "deepseek/deepseek-chat"),
            api_key=data.get("API_KEY", ""),
            api_base=data.get("API_BASE", ""),
            timeout=data.get("TIMEOUT", 120),
            temperature=data.get("TEMPERATURE", 1.0),
            max_tokens=data.get("MAX_TOKENS", 5000),
            num_retries=data.get("NUM_RETRIES", 2),
            fallback_models=data.get("FALLBACK_MODELS", []),
            extra_params=data.get("EXTRA_PARAMS", {}),
            queue=queue,
        )


@dataclass(frozen=True)
class AIAnalysisWindowConfig:
    """AI 分析窗口配置"""
    enabled: bool = False
    start: str = "09:00"
    end: str = "22:00"
    once_per_day: bool = False


@dataclass(frozen=True)
class AIAnalysisConfig:
    """AI 分析功能配置"""
    enabled: bool = False
    language: str = "Chinese"
    prompt_file: str = "ai_analysis_prompt.txt"
    mode: str = "follow_report"
    max_news_for_analysis: int = 50
    include_rss: bool = True
    include_rank_timeline: bool = False
    analysis_window: AIAnalysisWindowConfig = field(default_factory=AIAnalysisWindowConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIAnalysisConfig":
        """从字典创建 AIAnalysisConfig"""
        window_data = data.get("ANALYSIS_WINDOW", {})
        time_range = window_data.get("TIME_RANGE", {})
        window = AIAnalysisWindowConfig(
            enabled=window_data.get("ENABLED", False),
            start=time_range.get("START", "09:00"),
            end=time_range.get("END", "22:00"),
            once_per_day=window_data.get("ONCE_PER_DAY", False),
        )
        return cls(
            enabled=data.get("ENABLED", False),
            language=data.get("LANGUAGE", "Chinese"),
            prompt_file=data.get("PROMPT_FILE", "ai_analysis_prompt.txt"),
            mode=data.get("MODE", "follow_report"),
            max_news_for_analysis=data.get("MAX_NEWS_FOR_ANALYSIS", 50),
            include_rss=data.get("INCLUDE_RSS", True),
            include_rank_timeline=data.get("INCLUDE_RANK_TIMELINE", False),
            analysis_window=window,
        )


@dataclass(frozen=True)
class AITranslationConfig:
    """AI 翻译功能配置"""
    enabled: bool = False
    language: str = "English"
    prompt_file: str = "ai_translation_prompt.txt"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AITranslationConfig":
        """从字典创建 AITranslationConfig"""
        return cls(
            enabled=data.get("ENABLED", False),
            language=data.get("LANGUAGE", "English"),
            prompt_file=data.get("PROMPT_FILE", "ai_translation_prompt.txt"),
        )


# ============================================================
# 通知配置
# ============================================================

@dataclass(frozen=True)
class PushWindowConfig:
    """推送窗口配置"""
    enabled: bool = False
    start: str = "08:00"
    end: str = "22:00"
    once_per_day: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PushWindowConfig":
        """从字典创建 PushWindowConfig"""
        time_range = data.get("TIME_RANGE", {})
        return cls(
            enabled=data.get("ENABLED", False),
            start=time_range.get("START", "08:00"),
            end=time_range.get("END", "22:00"),
            once_per_day=data.get("ONCE_PER_DAY", True),
        )


@dataclass(frozen=True)
class NotificationConfig:
    """通知配置"""
    enabled: bool = True

    # 批次大小
    message_batch_size: int = 4000
    dingtalk_batch_size: int = 20000
    feishu_batch_size: int = 29000
    bark_batch_size: int = 3600
    slack_batch_size: int = 4000

    # 其他设置
    batch_send_interval: float = 1.0
    feishu_message_separator: str = "---"
    max_accounts_per_channel: int = 3

    # Webhook URLs
    feishu_webhook_url: str = ""
    dingtalk_webhook_url: str = ""
    wework_webhook_url: str = ""
    wework_msg_type: str = "markdown"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # 邮件
    email_enabled: bool = True
    email_from: str = ""
    email_password: str = ""
    email_to: str = ""
    email_smtp_server: str = ""
    email_smtp_port: str = ""

    # ntfy
    ntfy_server_url: str = "https://ntfy.sh"
    ntfy_topic: str = ""
    ntfy_token: str = ""

    # Bark
    bark_url: str = ""

    # Slack
    slack_webhook_url: str = ""

    # 通用 Webhook
    generic_webhook_url: str = ""
    generic_webhook_template: str = ""

    # 推送窗口
    push_window: PushWindowConfig = field(default_factory=PushWindowConfig)

    @classmethod
    def from_raw_config(cls, config: Dict[str, Any]) -> "NotificationConfig":
        """从原始配置字典创建 NotificationConfig"""
        push_window_data = config.get("PUSH_WINDOW", {})
        push_window = PushWindowConfig.from_dict(push_window_data)

        return cls(
            enabled=config.get("ENABLE_NOTIFICATION", True),
            message_batch_size=config.get("MESSAGE_BATCH_SIZE", 4000),
            dingtalk_batch_size=config.get("DINGTALK_BATCH_SIZE", 20000),
            feishu_batch_size=config.get("FEISHU_BATCH_SIZE", 29000),
            bark_batch_size=config.get("BARK_BATCH_SIZE", 3600),
            slack_batch_size=config.get("SLACK_BATCH_SIZE", 4000),
            batch_send_interval=config.get("BATCH_SEND_INTERVAL", 1.0),
            feishu_message_separator=config.get("FEISHU_MESSAGE_SEPARATOR", "---"),
            max_accounts_per_channel=config.get("MAX_ACCOUNTS_PER_CHANNEL", 3),
            feishu_webhook_url=config.get("FEISHU_WEBHOOK_URL", ""),
            dingtalk_webhook_url=config.get("DINGTALK_WEBHOOK_URL", ""),
            wework_webhook_url=config.get("WEWORK_WEBHOOK_URL", ""),
            wework_msg_type=config.get("WEWORK_MSG_TYPE", "markdown"),
            telegram_bot_token=config.get("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=config.get("TELEGRAM_CHAT_ID", ""),
            email_enabled=config.get("EMAIL_ENABLED", True),
            email_from=config.get("EMAIL_FROM", ""),
            email_password=config.get("EMAIL_PASSWORD", ""),
            email_to=config.get("EMAIL_TO", ""),
            email_smtp_server=config.get("EMAIL_SMTP_SERVER", ""),
            email_smtp_port=config.get("EMAIL_SMTP_PORT", ""),
            ntfy_server_url=config.get("NTFY_SERVER_URL", "https://ntfy.sh"),
            ntfy_topic=config.get("NTFY_TOPIC", ""),
            ntfy_token=config.get("NTFY_TOKEN", ""),
            bark_url=config.get("BARK_URL", ""),
            slack_webhook_url=config.get("SLACK_WEBHOOK_URL", ""),
            generic_webhook_url=config.get("GENERIC_WEBHOOK_URL", ""),
            generic_webhook_template=config.get("GENERIC_WEBHOOK_TEMPLATE", ""),
            push_window=push_window,
        )


# ============================================================
# 报告配置
# ============================================================

@dataclass(frozen=True)
class ReportConfig:
    """报告配置"""
    mode: str = "daily"
    display_mode: str = "keyword"
    rank_threshold: int = 10
    sort_by_position_first: bool = False
    max_news_per_keyword: int = 0

    @classmethod
    def from_raw_config(cls, config: Dict[str, Any]) -> "ReportConfig":
        """从原始配置字典创建 ReportConfig"""
        return cls(
            mode=config.get("REPORT_MODE", "daily"),
            display_mode=config.get("DISPLAY_MODE", "keyword"),
            rank_threshold=config.get("RANK_THRESHOLD", 10),
            sort_by_position_first=config.get("SORT_BY_POSITION_FIRST", False),
            max_news_per_keyword=config.get("MAX_NEWS_PER_KEYWORD", 0),
        )


# ============================================================
# 存储配置
# ============================================================

@dataclass(frozen=True)
class StorageFormatsConfig:
    """存储格式配置"""
    sqlite: bool = True
    txt: bool = True
    html: bool = True


@dataclass(frozen=True)
class StorageLocalConfig:
    """本地存储配置"""
    data_dir: str = "output"
    retention_days: int = 0


@dataclass(frozen=True)
class StorageRemoteConfig:
    """远程存储配置"""
    endpoint_url: str = ""
    bucket_name: str = ""
    access_key_id: str = ""
    secret_access_key: str = ""
    region: str = ""
    retention_days: int = 0


@dataclass(frozen=True)
class StoragePullConfig:
    """存储拉取配置"""
    enabled: bool = False
    days: int = 7


@dataclass(frozen=True)
class StorageConfig:
    """存储配置"""
    backend: str = "auto"
    formats: StorageFormatsConfig = field(default_factory=StorageFormatsConfig)
    local: StorageLocalConfig = field(default_factory=StorageLocalConfig)
    remote: StorageRemoteConfig = field(default_factory=StorageRemoteConfig)
    pull: StoragePullConfig = field(default_factory=StoragePullConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StorageConfig":
        """从字典创建 StorageConfig"""
        formats_data = data.get("FORMATS", {})
        local_data = data.get("LOCAL", {})
        remote_data = data.get("REMOTE", {})
        pull_data = data.get("PULL", {})

        return cls(
            backend=data.get("BACKEND", "auto"),
            formats=StorageFormatsConfig(
                sqlite=formats_data.get("SQLITE", True),
                txt=formats_data.get("TXT", True),
                html=formats_data.get("HTML", True),
            ),
            local=StorageLocalConfig(
                data_dir=local_data.get("DATA_DIR", "output"),
                retention_days=local_data.get("RETENTION_DAYS", 0),
            ),
            remote=StorageRemoteConfig(
                endpoint_url=remote_data.get("ENDPOINT_URL", ""),
                bucket_name=remote_data.get("BUCKET_NAME", ""),
                access_key_id=remote_data.get("ACCESS_KEY_ID", ""),
                secret_access_key=remote_data.get("SECRET_ACCESS_KEY", ""),
                region=remote_data.get("REGION", ""),
                retention_days=remote_data.get("RETENTION_DAYS", 0),
            ),
            pull=StoragePullConfig(
                enabled=pull_data.get("ENABLED", False),
                days=pull_data.get("DAYS", 7),
            ),
        )


# ============================================================
# RSS 配置
# ============================================================

@dataclass(frozen=True)
class RSSFreshnessConfig:
    """RSS 新鲜度过滤配置"""
    enabled: bool = True
    max_age_days: int = 3


@dataclass(frozen=True)
class RSSConfig:
    """RSS 配置"""
    enabled: bool = False
    request_interval: int = 2000
    timeout: int = 15
    use_proxy: bool = False
    proxy_url: str = ""
    feeds: List[Dict[str, Any]] = field(default_factory=list)
    freshness_filter: RSSFreshnessConfig = field(default_factory=RSSFreshnessConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RSSConfig":
        """从字典创建 RSSConfig"""
        freshness_data = data.get("FRESHNESS_FILTER", {})
        return cls(
            enabled=data.get("ENABLED", False),
            request_interval=data.get("REQUEST_INTERVAL", 2000),
            timeout=data.get("TIMEOUT", 15),
            use_proxy=data.get("USE_PROXY", False),
            proxy_url=data.get("PROXY_URL", ""),
            feeds=data.get("FEEDS", []),
            freshness_filter=RSSFreshnessConfig(
                enabled=freshness_data.get("ENABLED", True),
                max_age_days=freshness_data.get("MAX_AGE_DAYS", 3),
            ),
        )


# ============================================================
# 自定义爬虫配置
# ============================================================

@dataclass(frozen=True)
class CrawlerCustomFullContentConfig:
    """自定义爬虫全文抓取配置"""
    enabled: bool = True
    async_mode: bool = True
    fetch_delay: float = 0.3
    timeout: int = 10


@dataclass(frozen=True)
class CrawlerCustomStorageConfig:
    """自定义爬虫存储配置"""
    max_items: int = 10000
    max_days: int = 30
    max_display_items: int = 100


@dataclass(frozen=True)
class CrawlerCustomFilterConfig:
    """自定义爬虫过滤配置"""
    enabled: bool = True
    show_tag: bool = True


@dataclass(frozen=True)
class CrawlerCustomConfig:
    """自定义爬虫配置"""
    enabled: bool = False
    poll_interval: int = 10
    api_type: str = "tapp"
    full_content: CrawlerCustomFullContentConfig = field(default_factory=CrawlerCustomFullContentConfig)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    storage: CrawlerCustomStorageConfig = field(default_factory=CrawlerCustomStorageConfig)
    filter: CrawlerCustomFilterConfig = field(default_factory=CrawlerCustomFilterConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrawlerCustomConfig":
        """从字典创建 CrawlerCustomConfig"""
        full_content_data = data.get("FULL_CONTENT", {})
        storage_data = data.get("STORAGE", {})
        filter_data = data.get("FILTER", {})

        return cls(
            enabled=data.get("ENABLED", False),
            poll_interval=data.get("POLL_INTERVAL", 10),
            api_type=data.get("API_TYPE", "tapp"),
            full_content=CrawlerCustomFullContentConfig(
                enabled=full_content_data.get("ENABLED", True),
                async_mode=full_content_data.get("ASYNC_MODE", True),
                fetch_delay=full_content_data.get("FETCH_DELAY", 0.3),
                timeout=full_content_data.get("TIMEOUT", 10),
            ),
            sources=data.get("SOURCES", []),
            storage=CrawlerCustomStorageConfig(
                max_items=storage_data.get("MAX_ITEMS", 10000),
                max_days=storage_data.get("MAX_DAYS", 30),
                max_display_items=storage_data.get("MAX_DISPLAY_ITEMS", 100),
            ),
            filter=CrawlerCustomFilterConfig(
                enabled=filter_data.get("ENABLED", True),
                show_tag=filter_data.get("SHOW_TAG", True),
            ),
        )


# ============================================================
# 显示配置
# ============================================================

@dataclass(frozen=True)
class DisplayRegionsConfig:
    """显示区域开关配置"""
    hotlist: bool = True
    new_items: bool = True
    rss: bool = True
    standalone: bool = False
    ai_analysis: bool = True


@dataclass(frozen=True)
class DisplayStandaloneConfig:
    """独立展示区配置"""
    platforms: List[str] = field(default_factory=list)
    rss_feeds: List[str] = field(default_factory=list)
    max_items: int = 20


@dataclass(frozen=True)
class DisplayConfig:
    """显示配置"""
    region_order: List[str] = field(default_factory=lambda: ["hotlist", "rss", "new_items", "standalone", "ai_analysis"])
    regions: DisplayRegionsConfig = field(default_factory=DisplayRegionsConfig)
    standalone: DisplayStandaloneConfig = field(default_factory=DisplayStandaloneConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DisplayConfig":
        """从字典创建 DisplayConfig"""
        regions_data = data.get("REGIONS", {})
        standalone_data = data.get("STANDALONE", {})

        return cls(
            region_order=data.get("REGION_ORDER", ["hotlist", "rss", "new_items", "standalone", "ai_analysis"]),
            regions=DisplayRegionsConfig(
                hotlist=regions_data.get("HOTLIST", True),
                new_items=regions_data.get("NEW_ITEMS", True),
                rss=regions_data.get("RSS", True),
                standalone=regions_data.get("STANDALONE", False),
                ai_analysis=regions_data.get("AI_ANALYSIS", True),
            ),
            standalone=DisplayStandaloneConfig(
                platforms=standalone_data.get("PLATFORMS", []),
                rss_feeds=standalone_data.get("RSS_FEEDS", []),
                max_items=standalone_data.get("MAX_ITEMS", 20),
            ),
        )


# ============================================================
# 应用配置
# ============================================================

@dataclass(frozen=True)
class AppConfig:
    """应用基础配置"""
    timezone: str = "Asia/Shanghai"
    debug: bool = False
    show_version_update: bool = True
    version_check_url: str = ""
    configs_version_check_url: str = ""

    @classmethod
    def from_raw_config(cls, config: Dict[str, Any]) -> "AppConfig":
        """从原始配置字典创建 AppConfig"""
        return cls(
            timezone=config.get("TIMEZONE", "Asia/Shanghai"),
            debug=config.get("DEBUG", False),
            show_version_update=config.get("SHOW_VERSION_UPDATE", True),
            version_check_url=config.get("VERSION_CHECK_URL", ""),
            configs_version_check_url=config.get("CONFIGS_VERSION_CHECK_URL", ""),
        )


# ============================================================
# 爬虫配置
# ============================================================

@dataclass(frozen=True)
class CrawlerConfig:
    """爬虫基础配置"""
    request_interval: int = 100
    use_proxy: bool = False
    default_proxy: str = ""
    enable_platforms: bool = True

    @classmethod
    def from_raw_config(cls, config: Dict[str, Any]) -> "CrawlerConfig":
        """从原始配置字典创建 CrawlerConfig"""
        return cls(
            request_interval=config.get("REQUEST_INTERVAL", 100),
            use_proxy=config.get("USE_PROXY", False),
            default_proxy=config.get("DEFAULT_PROXY", ""),
            enable_platforms=config.get("ENABLE_PLATFORMS", True),
        )


# ============================================================
# 配置管理器
# ============================================================

class ConfigManager:
    """
    统一的配置管理器

    提供类型安全的配置访问接口，同时保持对原始配置字典的向后兼容。

    Example:
        >>> config = load_config()
        >>> manager = ConfigManager(config)
        >>> manager.ai.timeout  # 类型安全访问
        120
        >>> manager.get("AI")  # 原始字典访问
        {'MODEL': 'deepseek/deepseek-chat', ...}
    """

    def __init__(self, raw_config: Dict[str, Any]):
        """
        初始化配置管理器

        Args:
            raw_config: 由 load_config() 返回的原始配置字典
        """
        self._raw_config = raw_config
        self._validate()

        # 懒加载缓存
        self._ai: Optional[AIConfig] = None
        self._ai_analysis: Optional[AIAnalysisConfig] = None
        self._ai_translation: Optional[AITranslationConfig] = None
        self._notification: Optional[NotificationConfig] = None
        self._report: Optional[ReportConfig] = None
        self._storage: Optional[StorageConfig] = None
        self._rss: Optional[RSSConfig] = None
        self._crawler_custom: Optional[CrawlerCustomConfig] = None
        self._display: Optional[DisplayConfig] = None
        self._app: Optional[AppConfig] = None
        self._crawler: Optional[CrawlerConfig] = None

    def _validate(self) -> None:
        """验证配置，记录警告信息"""
        warnings = []

        # 检查 AI 配置
        ai_config = self._raw_config.get("AI", {})
        if ai_config.get("API_KEY") and not ai_config.get("MODEL"):
            warnings.append("配置了 AI_API_KEY 但未设置 AI_MODEL")

        # 检查通知配置
        if self._raw_config.get("ENABLE_NOTIFICATION", True):
            has_channel = any([
                self._raw_config.get("FEISHU_WEBHOOK_URL"),
                self._raw_config.get("DINGTALK_WEBHOOK_URL"),
                self._raw_config.get("WEWORK_WEBHOOK_URL"),
                self._raw_config.get("TELEGRAM_BOT_TOKEN"),
                self._raw_config.get("EMAIL_FROM"),
                self._raw_config.get("NTFY_TOPIC"),
                self._raw_config.get("BARK_URL"),
                self._raw_config.get("SLACK_WEBHOOK_URL"),
            ])
            if not has_channel:
                warnings.append("通知已启用但未配置任何推送渠道")

        if warnings:
            for w in warnings:
                logger.warning("配置警告: %s", w)

    # ============================================================
    # 类型安全的配置属性
    # ============================================================

    @property
    def ai(self) -> AIConfig:
        """获取 AI 模型配置"""
        if self._ai is None:
            self._ai = AIConfig.from_dict(self._raw_config.get("AI", {}))
        return self._ai

    @property
    def ai_analysis(self) -> AIAnalysisConfig:
        """获取 AI 分析功能配置"""
        if self._ai_analysis is None:
            self._ai_analysis = AIAnalysisConfig.from_dict(self._raw_config.get("AI_ANALYSIS", {}))
        return self._ai_analysis

    @property
    def ai_translation(self) -> AITranslationConfig:
        """获取 AI 翻译功能配置"""
        if self._ai_translation is None:
            self._ai_translation = AITranslationConfig.from_dict(self._raw_config.get("AI_TRANSLATION", {}))
        return self._ai_translation

    @property
    def notification(self) -> NotificationConfig:
        """获取通知配置"""
        if self._notification is None:
            self._notification = NotificationConfig.from_raw_config(self._raw_config)
        return self._notification

    @property
    def report(self) -> ReportConfig:
        """获取报告配置"""
        if self._report is None:
            self._report = ReportConfig.from_raw_config(self._raw_config)
        return self._report

    @property
    def storage(self) -> StorageConfig:
        """获取存储配置"""
        if self._storage is None:
            self._storage = StorageConfig.from_dict(self._raw_config.get("STORAGE", {}))
        return self._storage

    @property
    def rss(self) -> RSSConfig:
        """获取 RSS 配置"""
        if self._rss is None:
            self._rss = RSSConfig.from_dict(self._raw_config.get("RSS", {}))
        return self._rss

    @property
    def crawler_custom(self) -> CrawlerCustomConfig:
        """获取自定义爬虫配置"""
        if self._crawler_custom is None:
            self._crawler_custom = CrawlerCustomConfig.from_dict(self._raw_config.get("CRAWLER_CUSTOM", {}))
        return self._crawler_custom

    @property
    def display(self) -> DisplayConfig:
        """获取显示配置"""
        if self._display is None:
            self._display = DisplayConfig.from_dict(self._raw_config.get("DISPLAY", {}))
        return self._display

    @property
    def app(self) -> AppConfig:
        """获取应用基础配置"""
        if self._app is None:
            self._app = AppConfig.from_raw_config(self._raw_config)
        return self._app

    @property
    def crawler(self) -> CrawlerConfig:
        """获取爬虫基础配置"""
        if self._crawler is None:
            self._crawler = CrawlerConfig.from_raw_config(self._raw_config)
        return self._crawler

    # ============================================================
    # 向后兼容的字典访问
    # ============================================================

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取原始配置值（向后兼容）

        Args:
            key: 配置键名
            default: 默认值

        Returns:
            配置值或默认值
        """
        return self._raw_config.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """支持 config_manager["KEY"] 语法"""
        return self._raw_config[key]

    def __contains__(self, key: str) -> bool:
        """支持 "KEY" in config_manager 语法"""
        return key in self._raw_config

    @property
    def raw(self) -> Dict[str, Any]:
        """获取原始配置字典（只读）"""
        return self._raw_config.copy()

    def to_dict(self) -> Dict[str, Any]:
        """导出完整配置为字典（只读副本）"""
        return self._raw_config.copy()
