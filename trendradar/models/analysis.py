# coding=utf-8
"""
AI 分析结果数据模型

统一的分析结果数据结构，供所有分析器使用。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

from .base import BaseAnalysisResult, ToDictMixin


@dataclass
class NewsAnalysisResult(BaseAnalysisResult):
    """单条新闻分析结果

    用于单条新闻的 AI 分析，包含情感、关键词、摘要等。
    合并了原 AnalysisResult 和 ItemAnalysisResult。
    """
    news_id: str = ""                   # 新闻 ID/序号
    summary: str = ""                   # AI 生成的摘要
    keywords: List[str] = field(default_factory=list)  # 关键词列表
    sentiment: str = "neutral"          # 情感: positive/negative/neutral
    importance: int = 3                 # 重要性 1-5
    category: str = ""                  # 分类
    entities: List[str] = field(default_factory=list)  # 关键实体
    tags: List[str] = field(default_factory=list)      # 自动标签

    @classmethod
    def from_error(cls, news_id: str, error_msg: str) -> "NewsAnalysisResult":
        """创建错误结果"""
        result = cls(news_id=news_id)
        result.mark_error(error_msg)
        return result


@dataclass
class BatchAnalysisResult(BaseAnalysisResult):
    """批量新闻分析结果

    用于热榜/RSS 整体分析，包含趋势、热点等宏观分析。
    """
    # 5 核心板块
    core_trends: str = ""               # 核心热点与舆情态势
    sentiment_controversy: str = ""     # 舆论风向与争议
    signals: str = ""                   # 异动与弱信号
    rss_insights: str = ""              # RSS 深度洞察
    outlook_strategy: str = ""          # 研判与策略建议

    # 统计
    news_count: int = 0                 # 分析的新闻数量
    hotlist_count: int = 0              # 热榜新闻数量
    rss_count: int = 0                  # RSS 新闻数量


@dataclass
class TranslationResult(ToDictMixin):
    """翻译结果

    独立的数据类，不继承 BaseAnalysisResult 因为语义不同。
    翻译结果默认为失败状态，需要显式设置成功。
    """
    translated_text: str = ""           # 翻译后的文本
    original_text: str = ""             # 原始文本
    source_language: str = ""           # 源语言
    target_language: str = ""           # 目标语言
    success: bool = False               # 是否成功（默认 False）
    error: str = ""                     # 错误信息


@dataclass
class BatchTranslationResult(ToDictMixin):
    """批量翻译结果"""
    results: List[TranslationResult] = field(default_factory=list)
    success_count: int = 0
    fail_count: int = 0
    total_count: int = 0

    def add_result(self, result: TranslationResult) -> None:
        """添加翻译结果"""
        self.results.append(result)
        self.total_count += 1
        if result.success:
            self.success_count += 1
        else:
            self.fail_count += 1


# 向后兼容的别名
AnalysisResult = NewsAnalysisResult
ItemAnalysisResult = NewsAnalysisResult
AIAnalysisResult = BatchAnalysisResult
