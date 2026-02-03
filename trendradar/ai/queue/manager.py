# coding=utf-8
"""
AI 队列管理器

提供异步队列处理能力，支持：
- 入队/出队操作
- 并发工作线程
- 任务状态追踪
- 失败重试
"""

import asyncio
import uuid
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from collections import deque
import queue

from trendradar.logging import get_logger
from trendradar.models import TaskStatus, QueueTask

logger = get_logger(__name__)


class AIQueueManager:
    """AI 队列管理器

    提供基于线程的异步队列处理。
    """

    def __init__(
        self,
        max_size: int = 100,
        max_workers: int = 2,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ):
        """
        初始化队列管理器

        Args:
            max_size: 队列最大容量
            max_workers: 最大工作线程数
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
        """
        self.max_size = max_size
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self._queue: queue.Queue = queue.Queue(maxsize=max_size)
        self._tasks: Dict[str, QueueTask] = {}
        self._workers: List[threading.Thread] = []
        self._running = False
        self._processor: Optional[Callable] = None
        self._result_callback: Optional[Callable] = None
        self._lock = threading.Lock()

        # 统计
        self.stats = {
            "total_enqueued": 0,
            "total_processed": 0,
            "total_succeeded": 0,
            "total_failed": 0,
        }

    def set_processor(self, processor: Callable):
        """设置处理函数

        Args:
            processor: 处理函数，签名为 (data) -> result
        """
        self._processor = processor

    def set_result_callback(self, callback: Callable):
        """设置结果回调

        Args:
            callback: 回调函数，签名为 (task_id, result, success) -> None
        """
        self._result_callback = callback

    def enqueue(self, data: Any) -> str:
        """入队

        Args:
            data: 任务数据

        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())[:8]
        task = QueueTask(id=task_id, data=data)

        with self._lock:
            self._tasks[task_id] = task

        try:
            self._queue.put_nowait(task)
            self.stats["total_enqueued"] += 1
            return task_id
        except queue.Full:
            with self._lock:
                del self._tasks[task_id]
            raise RuntimeError("队列已满")

    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        with self._lock:
            task = self._tasks.get(task_id)
            return task.status if task else None

    def get_result(self, task_id: str) -> Optional[Any]:
        """获取任务结果"""
        with self._lock:
            task = self._tasks.get(task_id)
            return task.result if task else None

    def get_task(self, task_id: str) -> Optional[QueueTask]:
        """获取任务详情"""
        with self._lock:
            return self._tasks.get(task_id)

    def start(self):
        """启动工作线程"""
        if self._running:
            return

        self._running = True
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                args=(i,),
                daemon=True,
                name=f"ai-worker-{i}"
            )
            worker.start()
            self._workers.append(worker)
        logger.info("启动 %d 个工作线程", self.max_workers)

    def stop(self, wait: bool = True, timeout: float = 5.0):
        """停止工作线程"""
        self._running = False

        if wait:
            for worker in self._workers:
                worker.join(timeout=timeout)

        self._workers.clear()
        logger.info("工作线程已停止")

    def _worker_loop(self, worker_id: int):
        """工作循环"""
        while self._running:
            try:
                # 非阻塞获取任务
                try:
                    task = self._queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if not self._processor:
                    logger.warning("Worker %d: 未设置处理器", worker_id)
                    continue

                # 更新状态
                task.status = TaskStatus.PROCESSING
                task.started_at = datetime.now().isoformat()

                try:
                    # 执行处理
                    result = self._processor(task.data)

                    task.result = result
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.now().isoformat()
                    self.stats["total_succeeded"] += 1

                    if self._result_callback:
                        try:
                            self._result_callback(task.id, result, True)
                        except Exception as e:
                            logger.error("Worker %d: 回调错误: %s", worker_id, e)

                except Exception as e:
                    task.retry_count += 1
                    task.error = str(e)

                    if task.retry_count < self.max_retries:
                        # 重试
                        task.status = TaskStatus.PENDING
                        import time
                        time.sleep(self.retry_delay)
                        self._queue.put(task)
                    else:
                        # 放弃
                        task.status = TaskStatus.FAILED
                        task.completed_at = datetime.now().isoformat()
                        self.stats["total_failed"] += 1

                        if self._result_callback:
                            try:
                                self._result_callback(task.id, None, False)
                            except Exception as cb_e:
                                logger.error("Worker %d: 回调错误: %s", worker_id, cb_e)

                self.stats["total_processed"] += 1
                self._queue.task_done()

            except Exception as e:
                logger.exception("Worker %d: 未预期异常", worker_id)

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "queue_size": self._queue.qsize(),
            "pending_tasks": len([t for t in self._tasks.values() if t.status == TaskStatus.PENDING]),
            "processing_tasks": len([t for t in self._tasks.values() if t.status == TaskStatus.PROCESSING]),
        }

    def clear(self):
        """清空队列"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        with self._lock:
            self._tasks.clear()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()
