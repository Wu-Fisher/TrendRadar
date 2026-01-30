# coding=utf-8
"""
爬虫基类和数据结构定义

提供所有爬虫的抽象基类和统一的数据结构。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
from datetime import datetime
import traceback


class FetchStatus(Enum):
    """获取状态枚举"""
    SUCCESS = "success"
    NETWORK_ERROR = "network_error"
    PARSE_ERROR = "parse_error"
    TIMEOUT = "timeout"
    EMPTY_RESULT = "empty_result"
    UNKNOWN_ERROR = "unknown_error"


class CrawlerError(Exception):
    """爬虫基础异常"""

    def __init__(self, message: str, source_id: str = "", url: str = ""):
        super().__init__(message)
        self.message = message
        self.source_id = source_id
        self.url = url
        self.timestamp = datetime.now().isoformat()


class NetworkError(CrawlerError):
    """网络错误"""
    pass


class ParseError(CrawlerError):
    """解析错误"""
    pass


class ContentFetchError(CrawlerError):
    """内容获取错误"""
    pass


@dataclass
class CrawlerNewsItem:
    """爬虫新闻条目

    统一的新闻数据结构，所有爬虫返回此格式。
    """
    seq: str                          # 唯一序号（用于增量检测）
    title: str                        # 标题
    summary: str = ""                 # 摘要/简介
    full_content: str = ""            # 完整内容（可异步填充）
    url: str = ""                     # 链接
    published_at: str = ""            # 发布时间（ISO格式）
    source: str = ""                  # 来源（如：同花顺）
    author: str = ""                  # 作者

    # 扩展字段
    extra: Dict[str, Any] = field(default_factory=dict)  # 扩展数据（股票代码等）

    # 状态字段
    content_fetched: bool = False     # 完整内容是否已获取
    content_fetch_error: str = ""     # 内容获取错误信息
    content_fetch_time: str = ""      # 内容获取时间

    # 过滤相关
    matched_keywords: List[str] = field(default_factory=list)  # 匹配的关键词
    filtered_out: bool = False        # 是否被过滤掉
    filter_reason: str = ""           # 过滤原因

    # AI 分析预留
    ai_analysis: str = ""             # AI 分析结果
    ai_analysis_time: str = ""        # AI 分析时间

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "seq": self.seq,
            "title": self.title,
            "summary": self.summary,
            "full_content": self.full_content,
            "url": self.url,
            "published_at": self.published_at,
            "source": self.source,
            "author": self.author,
            "extra": self.extra,
            "content_fetched": self.content_fetched,
            "content_fetch_error": self.content_fetch_error,
            "content_fetch_time": self.content_fetch_time,
            "matched_keywords": self.matched_keywords,
            "filtered_out": self.filtered_out,
            "filter_reason": self.filter_reason,
            "ai_analysis": self.ai_analysis,
            "ai_analysis_time": self.ai_analysis_time,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrawlerNewsItem":
        """从字典创建"""
        return cls(
            seq=data.get("seq", ""),
            title=data.get("title", ""),
            summary=data.get("summary", ""),
            full_content=data.get("full_content", ""),
            url=data.get("url", ""),
            published_at=data.get("published_at", ""),
            source=data.get("source", ""),
            author=data.get("author", ""),
            extra=data.get("extra", {}),
            content_fetched=data.get("content_fetched", False),
            content_fetch_error=data.get("content_fetch_error", ""),
            content_fetch_time=data.get("content_fetch_time", ""),
            matched_keywords=data.get("matched_keywords", []),
            filtered_out=data.get("filtered_out", False),
            filter_reason=data.get("filter_reason", ""),
            ai_analysis=data.get("ai_analysis", ""),
            ai_analysis_time=data.get("ai_analysis_time", ""),
        )


@dataclass
class CrawlResult:
    """爬取结果

    封装单次爬取的完整结果。
    """
    source_id: str                    # 数据源 ID
    source_name: str                  # 数据源名称
    items: List[CrawlerNewsItem]      # 新闻条目列表
    status: FetchStatus               # 获取状态
    error_message: str = ""           # 错误信息
    fetch_time: str = ""              # 获取时间
    data_time: str = ""               # 数据时间（服务端返回的时间）
    total_count: int = 0              # 总条目数
    new_count: int = 0                # 新增条目数

    def __post_init__(self):
        if not self.fetch_time:
            self.fetch_time = datetime.now().isoformat()
        if self.total_count == 0:
            self.total_count = len(self.items)


@dataclass
class ErrorLogEntry:
    """错误日志条目"""
    timestamp: str
    source_id: str
    operation: str                    # fetch_list, fetch_content, parse
    url: str
    error_type: str
    error_message: str
    stack_trace: str = ""
    resolved: bool = False
    resolve_note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "source_id": self.source_id,
            "operation": self.operation,
            "url": self.url,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "resolved": self.resolved,
            "resolve_note": self.resolve_note,
        }


class BaseCrawler(ABC):
    """爬虫抽象基类

    所有自定义爬虫必须继承此类并实现抽象方法。

    使用示例:
        class MyCrawler(BaseCrawler):
            def get_source_id(self) -> str:
                return "my-source"

            def get_source_name(self) -> str:
                return "我的数据源"

            def fetch_news_list(self) -> CrawlResult:
                # 实现获取新闻列表逻辑
                pass

            def fetch_full_content(self, item: CrawlerNewsItem) -> Tuple[str, FetchStatus]:
                # 实现获取完整内容逻辑
                pass
    """

    def __init__(self, config: Optional[Dict] = None):
        """初始化爬虫

        Args:
            config: 爬虫配置字典
        """
        self.config = config or {}
        self._session = None

    @abstractmethod
    def get_source_id(self) -> str:
        """返回数据源唯一ID

        Returns:
            数据源的唯一标识符，如 "ths-realtime"
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """返回数据源显示名称

        Returns:
            用于展示的数据源名称，如 "同花顺7x24"
        """
        pass

    @abstractmethod
    def fetch_news_list(self) -> CrawlResult:
        """获取新闻列表

        Returns:
            CrawlResult 对象，包含新闻列表和状态信息
        """
        pass

    @abstractmethod
    def fetch_full_content(self, item: CrawlerNewsItem) -> Tuple[str, FetchStatus]:
        """获取单条新闻的完整内容

        Args:
            item: 新闻条目

        Returns:
            (完整内容, 状态) 元组
        """
        pass

    def supports_full_content(self) -> bool:
        """是否支持获取完整内容

        子类可重写此方法以禁用完整内容获取。

        Returns:
            True 表示支持，False 表示不支持
        """
        return True

    def get_request_headers(self) -> Dict[str, str]:
        """获取请求头

        子类可重写此方法以自定义请求头。

        Returns:
            HTTP 请求头字典
        """
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
        }

    def cleanup(self) -> None:
        """清理资源

        子类可重写此方法以清理资源（如关闭连接）。
        """
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
