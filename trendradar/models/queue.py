# coding=utf-8
"""
队列任务数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict
from enum import Enum

from .base import ToDictMixin


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"  # 也可用 RUNNING 作为别名
    COMPLETED = "completed"    # 也可用 SUCCESS 作为别名
    FAILED = "failed"
    CANCELLED = "cancelled"

    # 别名 - 向后兼容
    @classmethod
    def running(cls):
        """RUNNING 别名，等同于 PROCESSING"""
        return cls.PROCESSING

    @classmethod
    def success(cls):
        """SUCCESS 别名，等同于 COMPLETED"""
        return cls.COMPLETED


@dataclass
class QueueTask(ToDictMixin):
    """队列任务

    表示队列中的一个任务，包含状态追踪。
    """
    id: str
    data: Any
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: str = ""
    completed_at: str = ""
    retry_count: int = 0
    max_retries: int = 3

    def start(self) -> None:
        """标记任务开始"""
        self.status = TaskStatus.PROCESSING
        self.started_at = datetime.now().isoformat()

    def complete(self, result: Any) -> None:
        """标记任务完成"""
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now().isoformat()

    def fail(self, error: str) -> None:
        """标记任务失败"""
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = datetime.now().isoformat()

    def can_retry(self) -> bool:
        """是否可以重试"""
        return self.retry_count < self.max_retries

    def increment_retry(self) -> None:
        """增加重试次数"""
        self.retry_count += 1
        self.status = TaskStatus.PENDING
        self.error = ""

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
        }
