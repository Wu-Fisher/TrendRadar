# coding=utf-8
"""
自定义爬虫模块

提供可扩展的新闻爬虫框架，支持：
- 注册式爬虫管理
- 异步完整内容获取
- 严格异常处理和错误日志
- 三层关键词过滤
"""

from .base import (
    BaseCrawler,
    CrawlerNewsItem,
    CrawlResult,
    FetchStatus,
    CrawlerError,
    NetworkError,
    ParseError,
    ContentFetchError,
)
from .manager import CrawlerManager
from .ths import THSCrawler
from .filter import (
    filter_news_item,
    filter_news_items,
    load_frequency_words_for_crawler,
    format_filter_result,
)

__all__ = [
    # 基类和数据结构
    "BaseCrawler",
    "CrawlerNewsItem",
    "CrawlResult",
    "FetchStatus",
    "CrawlerError",
    "NetworkError",
    "ParseError",
    "ContentFetchError",
    # 管理器
    "CrawlerManager",
    # 爬虫实现
    "THSCrawler",
    # 过滤
    "filter_news_item",
    "filter_news_items",
    "load_frequency_words_for_crawler",
    "format_filter_result",
]
