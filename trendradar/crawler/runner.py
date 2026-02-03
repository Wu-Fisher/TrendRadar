# coding=utf-8
"""
爬虫运行器

将自定义爬虫集成到 TrendRadar 主流程。
支持：
- 10秒轮询
- 增量检测
- 过滤标记
- 网页展示
- 推送通知
"""

import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
import json

from trendradar.logging import get_logger
from .custom import (
    CrawlerManager,
    THSCrawler,
    THSTappCrawler,
    CrawlerNewsItem,
    CrawlResult,
    FetchStatus,
    filter_news_items,
    load_frequency_words_for_crawler,
    format_filter_result,
)

logger = get_logger(__name__)


class CrawlerRunner:
    """爬虫运行器

    提供与 TrendRadar 主流程的集成接口。
    """

    def __init__(self, config: Dict, ctx=None):
        """初始化运行器

        Args:
            config: 配置字典
            ctx: AppContext 实例（可选）
        """
        self.config = config
        self.ctx = ctx

        # 爬虫配置
        crawler_config = config.get("CRAWLER_CUSTOM", {})
        self.enabled = crawler_config.get("ENABLED", True)
        self.poll_interval = crawler_config.get("POLL_INTERVAL", 10)

        # 内容获取配置
        full_content_config = crawler_config.get("FULL_CONTENT", {})
        self.content_enabled = full_content_config.get("ENABLED", True)
        self.content_async = full_content_config.get("ASYNC_MODE", True)
        self.content_fetch_delay = full_content_config.get("FETCH_DELAY", 0.3)

        # 存储配置
        storage_config = crawler_config.get("STORAGE", {})
        self.max_items = storage_config.get("MAX_ITEMS", 10000)
        self.max_days = storage_config.get("MAX_DAYS", 30)
        self.max_display_items = storage_config.get("MAX_DISPLAY_ITEMS", 100)

        # 数据库路径
        data_dir = config.get("STORAGE", {}).get("LOCAL", {}).get("DATA_DIR", "output")
        db_dir = Path(data_dir) / "crawler"
        db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_dir / "crawler.db")

        # 创建管理器
        self.manager = CrawlerManager(
            config={
                "poll_interval": self.poll_interval,
                "full_content": {
                    "enabled": self.content_enabled,
                    "async_mode": self.content_async,
                    "fetch_delay": self.content_fetch_delay,
                },
            },
            db_path=self.db_path,
        )

        # 注册爬虫
        self._register_crawlers(crawler_config.get("SOURCES", []))

        # 过滤配置
        self.filter_enabled = crawler_config.get("FILTER", {}).get("ENABLED", True)
        self.show_filter_tag = crawler_config.get("FILTER", {}).get("SHOW_TAG", True)

        # 回调
        self._on_new_items: List[Callable] = []
        self._on_filtered: List[Callable] = []

        # 状态
        self._running = False
        self._poll_thread = None
        self._last_results: Dict[str, CrawlResult] = {}
        self._last_items: Dict[str, List[CrawlerNewsItem]] = {}  # 保存过滤后的条目（含过滤标记）

    def _register_crawlers(self, sources: List[Dict]) -> None:
        """注册配置的爬虫"""
        # 获取全局 API 类型配置
        crawler_config = self.config.get("CRAWLER_CUSTOM", {})
        default_api_type = crawler_config.get("API_TYPE", "tapp")  # 默认使用 TAPP API

        if not sources:
            # 默认注册同花顺爬虫
            sources = [{"id": "ths-realtime", "name": "同花顺7x24", "type": "ths", "enabled": True}]

        for source in sources:
            if not source.get("enabled", True):
                continue

            source_type = source.get("type", "ths")
            # 支持在 source 级别覆盖 api_type
            api_type = source.get("api_type", default_api_type)

            if source_type in ("ths", "ths_tapp"):
                crawler_cls = THSTappCrawler if api_type == "tapp" else THSCrawler
                crawler = crawler_cls(config={
                    "timezone": self.config.get("TIMEZONE", "Asia/Shanghai"),
                    "timeout": source.get("timeout", 10),
                    "content_fetch_delay": self.content_fetch_delay,
                    "page_size": source.get("page_size", 100),
                })
                self.manager.register(crawler)
                logger.info("注册 %s (API: %s)", source.get('name', source_type), api_type)

    def crawl_once(self) -> Dict[str, CrawlResult]:
        """执行一次爬取

        Returns:
            {source_id: CrawlResult} 字典
        """
        if not self.enabled:
            return {}

        results = self.manager.crawl_all()
        self._last_results = results

        # 处理每个结果
        for source_id, result in results.items():
            if result.status != FetchStatus.SUCCESS:
                logger.warning("%s 获取失败: %s", source_id, result.error_message)
                continue

            logger.info("%s 获取成功: %d 条, 新增 %d 条", source_id, result.total_count, result.new_count)

            # 获取完整内容（新增条目）
            if self.content_enabled and result.new_count > 0:
                new_items = [item for item in result.items if item.seq in
                           (self.manager.seen_items.get(source_id, set()) -
                            set(item.seq for item in self._get_old_items(source_id, result.items)))]

                # 实际上获取所有未获取内容的条目
                items_to_fetch = [item for item in result.items if not item.content_fetched]
                if items_to_fetch:
                    logger.info("开始获取 %d 条新闻的完整内容...", len(items_to_fetch))
                    self.manager.fetch_full_content(
                        source_id,
                        items_to_fetch,
                        async_mode=self.content_async,
                    )

            # 过滤处理
            if self.filter_enabled:
                self._apply_filter(source_id, result.items)
            else:
                # 不过滤时，所有条目标记为通过
                for item in result.items:
                    item.filtered_out = False
                    item.matched_keywords = []

            # 过滤后重新保存到数据库（更新过滤状态）
            self.manager._save_items(source_id, result.source_name, result.items)

            # 保存条目到内存（含过滤标记）
            self._last_items[source_id] = result.items

        return results

    def _get_old_items(self, source_id: str, current_items: List[CrawlerNewsItem]) -> List[CrawlerNewsItem]:
        """获取旧条目（用于计算新增）"""
        # 简化实现：返回空列表，实际新增检测在 manager 中完成
        return []

    def _apply_filter(self, source_id: str, items: List[CrawlerNewsItem]) -> None:
        """应用过滤"""
        try:
            # 加载关键词配置
            word_groups, filter_words, global_filters = load_frequency_words_for_crawler()

            if not word_groups and not filter_words and not global_filters:
                # 无过滤配置，全部通过
                for item in items:
                    item.filtered_out = False
                    item.matched_keywords = []
                return

            # 执行过滤
            passed, filtered = filter_news_items(
                items, word_groups, filter_words, global_filters
            )

            logger.info("过滤结果: 通过 %d 条, 过滤 %d 条", len(passed), len(filtered))

            # 触发回调
            for callback in self._on_filtered:
                try:
                    callback(source_id, passed, filtered)
                except Exception as e:
                    logger.error("过滤回调错误: %s", e)

        except Exception as e:
            logger.error("过滤处理错误: %s", e)

    def start_polling(self, callback: Optional[Callable] = None) -> None:
        """开始轮询

        Args:
            callback: 每次爬取后的回调函数
        """
        if self._running:
            return

        self._running = True

        def poll_task():
            while self._running:
                try:
                    results = self.crawl_once()
                    if callback:
                        callback(results)
                except Exception as e:
                    logger.error("轮询错误: %s", e)

                # 等待下一次
                for _ in range(self.poll_interval):
                    if not self._running:
                        break
                    time.sleep(1)

        self._poll_thread = threading.Thread(target=poll_task, daemon=True)
        self._poll_thread.start()
        logger.info("开始轮询，间隔 %d 秒", self.poll_interval)

    def stop_polling(self) -> None:
        """停止轮询"""
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=5)
        logger.info("停止轮询")

    def get_items_for_display(
        self,
        source_id: Optional[str] = None,
        include_filtered: bool = True,
        max_items: int = None
    ) -> List[Dict[str, Any]]:
        """获取用于展示的条目列表

        Args:
            source_id: 数据源 ID（可选）
            include_filtered: 是否包含被过滤的条目
            max_items: 最大条目数

        Returns:
            条目列表（字典格式）
        """
        max_items = max_items or self.max_display_items

        # 优先使用内存中的条目（含过滤标记）
        items = []
        if self._last_items:
            if source_id:
                items = self._last_items.get(source_id, [])
            else:
                for src_items in self._last_items.values():
                    items.extend(src_items)
        else:
            # 回退到数据库
            items = self.manager.get_items(
                source_id=source_id,
                limit=max_items,
                filtered_only=not include_filtered,
            )

        # 过滤处理
        if not include_filtered:
            items = [item for item in items if not item.filtered_out]

        # 截取显示数量
        items = items[:max_items]

        result = []
        new_seqs = self._get_new_seqs()
        for item in items:
            item_dict = item.to_dict()
            # 添加展示相关字段
            item_dict["is_new"] = item.seq in new_seqs
            item_dict["filter_tag"] = self._get_filter_tag(item) if self.show_filter_tag else ""
            result.append(item_dict)

        return result

    def _get_new_seqs(self) -> set:
        """获取本次新增的序号集合"""
        seqs = set()
        for result in self._last_results.values():
            if result.status == FetchStatus.SUCCESS:
                # 最新的条目视为新增
                for item in result.items[:result.new_count]:
                    seqs.add(item.seq)
        return seqs

    def _get_filter_tag(self, item: CrawlerNewsItem) -> str:
        """获取过滤标签"""
        if item.filtered_out:
            return f"🚫 {item.filter_reason}"
        elif item.matched_keywords:
            return f"✓ {', '.join(item.matched_keywords)}"
        return ""

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.manager.get_stats()
        return {
            source_id: {
                "source_id": s.source_id,
                "total_fetches": s.total_fetches,
                "successful_fetches": s.successful_fetches,
                "failed_fetches": s.failed_fetches,
                "total_items": s.total_items,
                "new_items": s.new_items,
                "last_fetch_time": s.last_fetch_time,
                "last_success_time": s.last_success_time,
                "last_error": s.last_error,
            }
            for source_id, s in stats.items()
        }

    def get_errors(self, limit: int = 50) -> List[Dict]:
        """获取错误日志"""
        errors = self.manager.get_errors(limit=limit)
        return [e.to_dict() for e in errors]

    def on_new_items(self, callback: Callable) -> None:
        """注册新条目回调"""
        self._on_new_items.append(callback)
        self.manager.on_new_items(lambda sid, items: callback(sid, items))

    def on_filtered(self, callback: Callable) -> None:
        """注册过滤完成回调"""
        self._on_filtered.append(callback)

    def convert_to_rss_format(
        self,
        items: List[CrawlerNewsItem]
    ) -> List[Dict[str, Any]]:
        """将爬虫条目转换为 RSS 格式（兼容现有推送逻辑）

        Args:
            items: 爬虫条目列表

        Returns:
            RSS 格式的条目列表
        """
        rss_items = []
        for item in items:
            rss_item = {
                "title": item.title,
                "feed_id": "ths-realtime",
                "feed_name": "同花顺7x24",
                "url": item.url,
                "published_at": item.published_at,
                "summary": item.summary or item.full_content[:200] if item.full_content else "",
                "author": item.source,
                "full_content": item.full_content,
                # 过滤相关
                "matched_keywords": item.matched_keywords,
                "filtered_out": item.filtered_out,
                "filter_reason": item.filter_reason,
                # 扩展信息
                "extra": item.extra,
            }
            rss_items.append(rss_item)
        return rss_items

    def cleanup(self) -> None:
        """清理资源"""
        self.stop_polling()
        # 清理旧数据
        deleted = self.manager.cleanup_old_data(
            max_items=self.max_items,
            max_days=self.max_days,
        )
        if deleted > 0:
            logger.info("清理了 %d 条旧数据", deleted)
        self.manager.cleanup()


def create_crawler_runner(config: Dict, ctx=None) -> CrawlerRunner:
    """创建爬虫运行器

    Args:
        config: 配置字典
        ctx: AppContext 实例

    Returns:
        CrawlerRunner 实例
    """
    return CrawlerRunner(config, ctx)
