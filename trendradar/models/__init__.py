# coding=utf-8
"""
TrendRadar 数据模型

统一的数据结构定义，提供类型安全和代码复用。

使用示例:
    from trendradar.models import NewsAnalysisResult, QueueTask, TaskStatus

    # 创建分析结果
    result = NewsAnalysisResult(
        news_id="12345",
        summary="这是一条新闻摘要",
        sentiment="positive",
        importance=4,
    )

    # 创建队列任务
    task = QueueTask(id="task-001", data={"title": "新闻标题"})
    task.start()
    task.complete(result)
"""

# 基类
from .base import (
    ToDictMixin,
    BaseResult,
    BaseAnalysisResult,
    BaseNewsItem,
)

# 分析结果
from .analysis import (
    NewsAnalysisResult,
    BatchAnalysisResult,
    TranslationResult,
    BatchTranslationResult,
    # 向后兼容别名
    AnalysisResult,
    ItemAnalysisResult,
    AIAnalysisResult,
)

# 队列任务
from .queue import (
    TaskStatus,
    QueueTask,
)

__all__ = [
    # 基类
    "ToDictMixin",
    "BaseResult",
    "BaseAnalysisResult",
    "BaseNewsItem",
    # 分析结果
    "NewsAnalysisResult",
    "BatchAnalysisResult",
    "TranslationResult",
    "BatchTranslationResult",
    # 向后兼容
    "AnalysisResult",
    "ItemAnalysisResult",
    "AIAnalysisResult",
    # 队列
    "TaskStatus",
    "QueueTask",
]
