# coding=utf-8
"""
爬虫管理器

负责管理所有注册的爬虫，提供统一的调度和错误处理。
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
import json
import sqlite3
from pathlib import Path

from .base import (
    BaseCrawler,
    CrawlerNewsItem,
    CrawlResult,
    FetchStatus,
    ErrorLogEntry,
)


@dataclass
class CrawlerStats:
    """爬虫统计信息"""
    source_id: str
    total_fetches: int = 0
    successful_fetches: int = 0
    failed_fetches: int = 0
    total_items: int = 0
    new_items: int = 0
    last_fetch_time: str = ""
    last_success_time: str = ""
    last_error: str = ""


class CrawlerManager:
    """爬虫管理器

    功能：
    - 注册/注销爬虫
    - 统一调度爬取
    - 增量检测
    - 错误日志
    - 异步内容获取
    """

    def __init__(self, config: Optional[Dict] = None, db_path: Optional[str] = None):
        """初始化管理器

        Args:
            config: 配置字典
            db_path: 数据库路径（用于持久化）
        """
        self.config = config or {}
        self.crawlers: Dict[str, BaseCrawler] = {}
        self.stats: Dict[str, CrawlerStats] = {}
        self.error_log: List[ErrorLogEntry] = []
        self.seen_items: Dict[str, Set[str]] = {}  # {source_id: {seq1, seq2, ...}}

        # 配置项
        self.poll_interval = self.config.get("poll_interval", 10)
        self.max_error_log = self.config.get("max_error_log", 1000)
        self.content_fetch_enabled = self.config.get("full_content", {}).get("enabled", True)
        self.content_fetch_async = self.config.get("full_content", {}).get("async_mode", True)
        self.content_fetch_delay = self.config.get("full_content", {}).get("fetch_delay", 0.3)
        self.content_fetch_timeout = self.config.get("full_content", {}).get("timeout", 10)

        # 数据库
        self.db_path = db_path
        self._init_db()

        # 回调
        self._on_new_items_callbacks: List[Callable] = []
        self._on_content_fetched_callbacks: List[Callable] = []
        self._on_error_callbacks: List[Callable] = []

    def _init_db(self) -> None:
        """初始化数据库"""
        if not self.db_path:
            return

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 原始数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawler_raw (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                seq TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                full_content TEXT,
                url TEXT,
                published_at TEXT,
                extra_data TEXT,
                crawl_time TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                content_fetched INTEGER DEFAULT 0,
                content_fetch_error TEXT,
                content_fetch_time TEXT,
                UNIQUE(source_id, seq)
            )
        """)

        # 过滤后数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawler_filtered (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_id INTEGER NOT NULL,
                source_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                seq TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                full_content TEXT,
                url TEXT,
                published_at TEXT,
                matched_keywords TEXT,
                filter_time TEXT NOT NULL,
                pushed INTEGER DEFAULT 0,
                push_time TEXT,
                ai_analysis TEXT,
                ai_analysis_time TEXT,
                FOREIGN KEY (raw_id) REFERENCES crawler_raw(id)
            )
        """)

        # 错误日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawler_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source_id TEXT,
                operation TEXT NOT NULL,
                url TEXT,
                error_type TEXT NOT NULL,
                error_message TEXT,
                stack_trace TEXT,
                resolved INTEGER DEFAULT 0,
                resolve_note TEXT
            )
        """)

        # 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crawler_raw_source ON crawler_raw(source_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crawler_raw_time ON crawler_raw(crawl_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crawler_raw_first_seen ON crawler_raw(first_seen)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crawler_filtered_source ON crawler_filtered(source_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crawler_filtered_pushed ON crawler_filtered(pushed)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crawler_errors_time ON crawler_errors(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_crawler_errors_resolved ON crawler_errors(resolved)")

        conn.commit()
        conn.close()

    def register(self, crawler: BaseCrawler) -> None:
        """注册爬虫

        Args:
            crawler: 爬虫实例
        """
        source_id = crawler.get_source_id()
        self.crawlers[source_id] = crawler
        self.stats[source_id] = CrawlerStats(source_id=source_id)
        self.seen_items[source_id] = set()

        # 从数据库加载已见过的 seq
        if self.db_path:
            self._load_seen_items(source_id)

    def unregister(self, source_id: str) -> None:
        """注销爬虫

        Args:
            source_id: 数据源 ID
        """
        if source_id in self.crawlers:
            self.crawlers[source_id].cleanup()
            del self.crawlers[source_id]
        self.stats.pop(source_id, None)
        self.seen_items.pop(source_id, None)

    def _load_seen_items(self, source_id: str) -> None:
        """从数据库加载已见过的条目"""
        if not self.db_path:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT seq FROM crawler_raw WHERE source_id = ?",
                (source_id,)
            )
            for row in cursor.fetchall():
                self.seen_items[source_id].add(row[0])
            conn.close()
        except Exception as e:
            self.log_error(source_id, "load_seen", "", str(e))

    def crawl_all(self) -> Dict[str, CrawlResult]:
        """执行所有已注册爬虫

        Returns:
            {source_id: CrawlResult} 字典
        """
        results = {}
        for source_id, crawler in self.crawlers.items():
            try:
                result = crawler.fetch_news_list()
                results[source_id] = result

                # 更新统计
                stats = self.stats[source_id]
                stats.total_fetches += 1
                stats.last_fetch_time = datetime.now().isoformat()

                if result.status == FetchStatus.SUCCESS:
                    stats.successful_fetches += 1
                    stats.last_success_time = datetime.now().isoformat()
                    stats.total_items += len(result.items)

                    # 检测新增
                    new_items = self._detect_new_items(source_id, result.items)
                    result.new_count = len(new_items)
                    stats.new_items += len(new_items)

                    # 保存到数据库
                    if self.db_path:
                        self._save_items(source_id, crawler.get_source_name(), result.items)

                    # 触发回调
                    if new_items and self._on_new_items_callbacks:
                        for callback in self._on_new_items_callbacks:
                            try:
                                callback(source_id, new_items)
                            except Exception:
                                pass
                else:
                    stats.failed_fetches += 1
                    stats.last_error = result.error_message
                    self.log_error(source_id, "fetch_list", "", result.error_message)

            except Exception as e:
                error_msg = str(e)
                self.log_error(source_id, "crawl", "", error_msg)
                results[source_id] = CrawlResult(
                    source_id=source_id,
                    source_name=crawler.get_source_name(),
                    items=[],
                    status=FetchStatus.UNKNOWN_ERROR,
                    error_message=error_msg,
                )
                self.stats[source_id].failed_fetches += 1
                self.stats[source_id].last_error = error_msg

        return results

    def crawl_single(self, source_id: str) -> Optional[CrawlResult]:
        """执行单个爬虫

        Args:
            source_id: 数据源 ID

        Returns:
            CrawlResult 或 None
        """
        if source_id not in self.crawlers:
            return None
        return self.crawl_all().get(source_id)

    def _detect_new_items(
        self,
        source_id: str,
        items: List[CrawlerNewsItem]
    ) -> List[CrawlerNewsItem]:
        """检测新增条目

        Args:
            source_id: 数据源 ID
            items: 条目列表

        Returns:
            新增条目列表
        """
        seen = self.seen_items.get(source_id, set())
        new_items = []

        for item in items:
            if item.seq not in seen:
                new_items.append(item)
                seen.add(item.seq)

        self.seen_items[source_id] = seen
        return new_items

    def _save_items(
        self,
        source_id: str,
        source_name: str,
        items: List[CrawlerNewsItem]
    ) -> None:
        """保存条目到数据库"""
        if not self.db_path:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            for item in items:
                # 使用 UPSERT
                cursor.execute("""
                    INSERT INTO crawler_raw (
                        source_id, source_name, seq, title, summary, full_content,
                        url, published_at, extra_data, crawl_time, first_seen,
                        last_seen, content_fetched, content_fetch_error, content_fetch_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id, seq) DO UPDATE SET
                        title = excluded.title,
                        summary = excluded.summary,
                        full_content = CASE
                            WHEN excluded.full_content != '' THEN excluded.full_content
                            ELSE crawler_raw.full_content
                        END,
                        last_seen = excluded.last_seen,
                        content_fetched = CASE
                            WHEN excluded.content_fetched = 1 THEN 1
                            ELSE crawler_raw.content_fetched
                        END,
                        content_fetch_error = CASE
                            WHEN excluded.content_fetch_error != '' THEN excluded.content_fetch_error
                            ELSE crawler_raw.content_fetch_error
                        END,
                        content_fetch_time = CASE
                            WHEN excluded.content_fetch_time != '' THEN excluded.content_fetch_time
                            ELSE crawler_raw.content_fetch_time
                        END
                """, (
                    source_id,
                    source_name,
                    item.seq,
                    item.title,
                    item.summary,
                    item.full_content,
                    item.url,
                    item.published_at,
                    json.dumps(item.extra, ensure_ascii=False) if item.extra else "",
                    now,
                    now,
                    now,
                    1 if item.content_fetched else 0,
                    item.content_fetch_error,
                    item.content_fetch_time,
                ))

            conn.commit()
            conn.close()
        except Exception as e:
            self.log_error(source_id, "save_items", "", str(e))

    def fetch_full_content(
        self,
        source_id: str,
        items: List[CrawlerNewsItem],
        async_mode: bool = None,
        callback: Callable = None
    ) -> None:
        """获取完整内容

        Args:
            source_id: 数据源 ID
            items: 条目列表
            async_mode: 是否异步模式
            callback: 回调函数
        """
        if source_id not in self.crawlers:
            return

        crawler = self.crawlers[source_id]
        if not crawler.supports_full_content():
            return

        async_mode = async_mode if async_mode is not None else self.content_fetch_async

        def fetch_task():
            for item in items:
                if item.content_fetched:
                    continue

                try:
                    content, status = crawler.fetch_full_content(item)
                    item.full_content = content
                    item.content_fetched = status == FetchStatus.SUCCESS
                    item.content_fetch_time = datetime.now().isoformat()
                    if status != FetchStatus.SUCCESS:
                        item.content_fetch_error = status.value

                    # 更新数据库
                    if self.db_path:
                        self._update_item_content(source_id, item)

                    # 回调
                    if callback:
                        callback(item, content, status)

                    for cb in self._on_content_fetched_callbacks:
                        try:
                            cb(source_id, item)
                        except Exception:
                            pass

                    # 延迟
                    time.sleep(self.content_fetch_delay)

                except Exception as e:
                    item.content_fetch_error = str(e)
                    self.log_error(source_id, "fetch_content", item.url, str(e))

        if async_mode:
            thread = threading.Thread(target=fetch_task, daemon=True)
            thread.start()
        else:
            fetch_task()

    def _update_item_content(self, source_id: str, item: CrawlerNewsItem) -> None:
        """更新条目内容到数据库"""
        if not self.db_path:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE crawler_raw SET
                    full_content = ?,
                    content_fetched = ?,
                    content_fetch_error = ?,
                    content_fetch_time = ?
                WHERE source_id = ? AND seq = ?
            """, (
                item.full_content,
                1 if item.content_fetched else 0,
                item.content_fetch_error,
                item.content_fetch_time,
                source_id,
                item.seq,
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            self.log_error(source_id, "update_content", item.url, str(e))

    def log_error(
        self,
        source_id: str,
        operation: str,
        url: str,
        error_message: str,
        error_type: str = "unknown",
        stack_trace: str = ""
    ) -> None:
        """记录错误日志

        Args:
            source_id: 数据源 ID
            operation: 操作类型
            url: 相关 URL
            error_message: 错误信息
            error_type: 错误类型
            stack_trace: 堆栈跟踪
        """
        entry = ErrorLogEntry(
            timestamp=datetime.now().isoformat(),
            source_id=source_id,
            operation=operation,
            url=url,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
        )

        # 内存中保留
        self.error_log.append(entry)
        if len(self.error_log) > self.max_error_log:
            self.error_log = self.error_log[-self.max_error_log:]

        # 保存到数据库
        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO crawler_errors (
                        timestamp, source_id, operation, url,
                        error_type, error_message, stack_trace
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.timestamp,
                    entry.source_id,
                    entry.operation,
                    entry.url,
                    entry.error_type,
                    entry.error_message,
                    entry.stack_trace,
                ))
                conn.commit()
                conn.close()
            except Exception:
                pass  # 避免循环记录错误

        # 触发回调
        for callback in self._on_error_callbacks:
            try:
                callback(entry)
            except Exception:
                pass

    def get_errors(
        self,
        source_id: Optional[str] = None,
        unresolved_only: bool = False,
        limit: int = 100
    ) -> List[ErrorLogEntry]:
        """获取错误日志

        Args:
            source_id: 过滤数据源
            unresolved_only: 只返回未解决的
            limit: 返回数量限制

        Returns:
            错误日志列表
        """
        if self.db_path:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                query = "SELECT * FROM crawler_errors WHERE 1=1"
                params = []

                if source_id:
                    query += " AND source_id = ?"
                    params.append(source_id)
                if unresolved_only:
                    query += " AND resolved = 0"

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()
                conn.close()

                return [
                    ErrorLogEntry(
                        timestamp=row[1],
                        source_id=row[2],
                        operation=row[3],
                        url=row[4],
                        error_type=row[5],
                        error_message=row[6],
                        stack_trace=row[7],
                        resolved=bool(row[8]),
                        resolve_note=row[9] or "",
                    )
                    for row in rows
                ]
            except Exception:
                pass

        # 回退到内存
        result = self.error_log
        if source_id:
            result = [e for e in result if e.source_id == source_id]
        if unresolved_only:
            result = [e for e in result if not e.resolved]
        return result[-limit:]

    def on_new_items(self, callback: Callable) -> None:
        """注册新条目回调

        Args:
            callback: 回调函数，接收 (source_id, items) 参数
        """
        self._on_new_items_callbacks.append(callback)

    def on_content_fetched(self, callback: Callable) -> None:
        """注册内容获取回调

        Args:
            callback: 回调函数，接收 (source_id, item) 参数
        """
        self._on_content_fetched_callbacks.append(callback)

    def on_error(self, callback: Callable) -> None:
        """注册错误回调

        Args:
            callback: 回调函数，接收 ErrorLogEntry 参数
        """
        self._on_error_callbacks.append(callback)

    def get_stats(self, source_id: Optional[str] = None) -> Dict[str, CrawlerStats]:
        """获取统计信息

        Args:
            source_id: 指定数据源

        Returns:
            统计信息字典
        """
        if source_id:
            return {source_id: self.stats.get(source_id)}
        return self.stats.copy()

    def get_items(
        self,
        source_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        filtered_only: bool = False
    ) -> List[CrawlerNewsItem]:
        """获取条目列表

        Args:
            source_id: 过滤数据源
            limit: 返回数量限制
            offset: 偏移量
            filtered_only: 只返回过滤后的

        Returns:
            条目列表
        """
        if not self.db_path:
            return []

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            table = "crawler_filtered" if filtered_only else "crawler_raw"
            query = f"SELECT * FROM {table} WHERE 1=1"
            params = []

            if source_id:
                query += " AND source_id = ?"
                params.append(source_id)

            query += " ORDER BY first_seen DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            items = []
            for row in rows:
                item = CrawlerNewsItem(
                    seq=row[3],
                    title=row[4],
                    summary=row[5] or "",
                    full_content=row[6] or "",
                    url=row[7] or "",
                    published_at=row[8] or "",
                    extra=json.loads(row[9]) if row[9] else {},
                    content_fetched=bool(row[12]) if len(row) > 12 else False,
                    content_fetch_error=row[13] if len(row) > 13 else "",
                    content_fetch_time=row[14] if len(row) > 14 else "",
                )
                items.append(item)

            return items
        except Exception as e:
            self.log_error("", "get_items", "", str(e))
            return []

    def cleanup_old_data(
        self,
        max_items: int = 10000,
        max_days: int = 30
    ) -> int:
        """清理旧数据

        Args:
            max_items: 最大条目数
            max_days: 最大保留天数

        Returns:
            删除的条目数
        """
        if not self.db_path:
            return 0

        deleted = 0
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 按时间清理
            if max_days > 0:
                cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                from datetime import timedelta
                cutoff = cutoff - timedelta(days=max_days)
                cutoff_str = cutoff.isoformat()

                cursor.execute(
                    "DELETE FROM crawler_raw WHERE first_seen < ?",
                    (cutoff_str,)
                )
                deleted += cursor.rowcount

            # 按数量清理
            if max_items > 0:
                cursor.execute("SELECT COUNT(*) FROM crawler_raw")
                count = cursor.fetchone()[0]
                if count > max_items:
                    cursor.execute(f"""
                        DELETE FROM crawler_raw WHERE id IN (
                            SELECT id FROM crawler_raw ORDER BY first_seen ASC LIMIT ?
                        )
                    """, (count - max_items,))
                    deleted += cursor.rowcount

            # 清理错误日志
            cursor.execute(f"""
                DELETE FROM crawler_errors WHERE id IN (
                    SELECT id FROM crawler_errors ORDER BY timestamp ASC LIMIT ?
                )
            """, (max(0, len(self.error_log) - self.max_error_log),))

            conn.commit()
            conn.close()
        except Exception as e:
            self.log_error("", "cleanup", "", str(e))

        return deleted

    def cleanup(self) -> None:
        """清理所有资源"""
        for crawler in self.crawlers.values():
            crawler.cleanup()
        self.crawlers.clear()
        self.stats.clear()
        self.seen_items.clear()
