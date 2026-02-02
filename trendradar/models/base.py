# coding=utf-8
"""
数据模型基类和通用混入类

提供所有数据类的基础功能：
- BaseResult: 结果类基类，包含 success, error 等通用字段
- ToDictMixin: 提供统一的 to_dict() 方法
"""

from dataclasses import dataclass, field, fields, asdict
from datetime import datetime
from typing import Dict, Any, Optional, List


class ToDictMixin:
    """提供统一的 to_dict() 方法

    自动将 dataclass 转换为字典，处理嵌套对象。
    """

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            包含所有字段的字典
        """
        result = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if hasattr(value, 'to_dict'):
                result[f.name] = value.to_dict()
            elif isinstance(value, list):
                result[f.name] = [
                    item.to_dict() if hasattr(item, 'to_dict') else item
                    for item in value
                ]
            elif isinstance(value, dict):
                result[f.name] = {
                    k: v.to_dict() if hasattr(v, 'to_dict') else v
                    for k, v in value.items()
                }
            else:
                result[f.name] = value
        return result


@dataclass
class BaseResult(ToDictMixin):
    """结果类基类

    所有返回结果的基类，包含通用的状态字段。
    """
    success: bool = True
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def mark_error(self, error_msg: str) -> None:
        """标记为错误状态"""
        self.success = False
        self.error = error_msg


@dataclass
class BaseAnalysisResult(BaseResult):
    """AI 分析结果基类

    所有 AI 分析结果的基类，包含分析相关的通用字段。
    """
    raw_response: str = ""              # 原始 AI 响应
    model_used: str = ""                # 使用的模型
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class BaseNewsItem(ToDictMixin):
    """新闻条目基类

    所有新闻条目的基类，包含新闻的通用字段。
    """
    title: str                          # 标题
    url: str = ""                       # 链接
    summary: str = ""                   # 摘要
    published_at: str = ""              # 发布时间
    crawl_time: str = ""                # 抓取时间
    source: str = ""                    # 来源

    def __post_init__(self):
        if not self.crawl_time:
            self.crawl_time = datetime.now().strftime("%H:%M")
