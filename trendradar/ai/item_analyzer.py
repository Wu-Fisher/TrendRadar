# coding=utf-8
"""
新闻条目 AI 分析器（预留接口）

为自定义爬虫条目提供 AI 分析能力：
- 情感分析
- 重要性评分
- 关键实体提取
- 简短摘要生成

使用方式:
    analyzer = NewsItemAnalyzer(ai_config)
    result = await analyzer.analyze_item(item)
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from trendradar.crawler.custom.base import CrawlerNewsItem
from trendradar.models import NewsAnalysisResult

# 向后兼容别名
ItemAnalysisResult = NewsAnalysisResult


class NewsItemAnalyzer:
    """新闻条目 AI 分析器

    预留接口，支持异步分析单条或批量新闻。
    """

    # 默认提示词模板
    DEFAULT_PROMPT = """分析以下财经新闻，返回 JSON 格式结果：

标题: {title}
内容: {content}

返回格式:
{{
    "sentiment": "positive/negative/neutral",
    "importance": 1-10,
    "entities": ["实体1", "实体2"],
    "summary": "50字以内摘要",
    "tags": ["标签1", "标签2"]
}}

只返回 JSON，不要其他内容。"""

    def __init__(self, ai_config: Dict[str, Any] = None):
        """初始化分析器

        Args:
            ai_config: AI 配置，与 AIAnalyzer 共用配置格式
        """
        self.ai_config = ai_config or {}
        self._client = None
        self._enabled = ai_config.get("ENABLED", False) if ai_config else False

    def _init_client(self):
        """延迟初始化 AI 客户端"""
        if self._client is not None:
            return

        if not self._enabled:
            return

        try:
            from trendradar.ai.client import AIClient
            self._client = AIClient(self.ai_config)
        except Exception as e:
            print(f"[NewsItemAnalyzer] 初始化 AI 客户端失败: {e}")
            self._client = None

    def analyze_item_sync(self, item: CrawlerNewsItem) -> ItemAnalysisResult:
        """同步分析单条新闻

        Args:
            item: 爬虫新闻条目

        Returns:
            ItemAnalysisResult: 分析结果
        """
        result = ItemAnalysisResult(news_id=item.seq)
        result.success = False  # 默认失败，成功时显式设置

        if not self._enabled:
            result.error = "AI 分析未启用"
            return result

        self._init_client()
        if not self._client:
            result.error = "AI 客户端初始化失败"
            return result

        try:
            # 准备内容
            content = item.full_content or item.summary or ""
            if not content:
                result.error = "无可分析内容"
                return result

            # 截断过长内容
            if len(content) > 1000:
                content = content[:1000] + "..."

            # 构建提示词
            prompt = self.DEFAULT_PROMPT.format(
                title=item.title,
                content=content,
            )

            # 调用 AI
            messages = [{"role": "user", "content": prompt}]
            response = self._client.chat(messages)

            # 解析响应
            result = self._parse_response(item.seq, response)

            # 更新原始条目
            item.ai_analysis = json.dumps(result.to_dict(), ensure_ascii=False)
            item.ai_analysis_time = result.analyzed_at

            return result

        except Exception as e:
            result.error = f"分析失败: {str(e)[:100]}"
            return result

    async def analyze_item(self, item: CrawlerNewsItem) -> ItemAnalysisResult:
        """异步分析单条新闻

        Args:
            item: 爬虫新闻条目

        Returns:
            ItemAnalysisResult: 分析结果
        """
        # 当前使用同步实现，后续可改为真正的异步
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.analyze_item_sync, item)

    async def analyze_batch(
        self,
        items: List[CrawlerNewsItem],
        max_concurrent: int = 3,
    ) -> List[ItemAnalysisResult]:
        """批量异步分析

        Args:
            items: 新闻条目列表
            max_concurrent: 最大并发数

        Returns:
            分析结果列表
        """
        if not items:
            return []

        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_limit(item):
            async with semaphore:
                return await self.analyze_item(item)

        tasks = [analyze_with_limit(item) for item in items]
        return await asyncio.gather(*tasks)

    def _parse_response(self, news_id: str, response: str) -> ItemAnalysisResult:
        """解析 AI 响应"""
        result = ItemAnalysisResult(news_id=news_id, raw_response=response)
        result.success = False  # 默认失败

        try:
            # 提取 JSON
            json_str = response.strip()

            # 处理 markdown 代码块
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            result.sentiment = data.get("sentiment", "neutral")
            result.importance = int(data.get("importance", 5))
            result.entities = data.get("entities", [])
            result.summary = data.get("summary", "")
            result.tags = data.get("tags", [])
            result.success = True

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            result.error = f"解析响应失败: {str(e)[:50]}"

        return result

    @property
    def enabled(self) -> bool:
        """是否启用"""
        return self._enabled


# 便捷函数
def create_news_item_analyzer(config: Dict) -> NewsItemAnalyzer:
    """创建新闻条目分析器

    Args:
        config: 完整配置字典

    Returns:
        NewsItemAnalyzer 实例
    """
    ai_config = config.get("AI", {})
    analysis_config = config.get("AI_ANALYSIS", {})

    # 合并配置
    merged_config = {**ai_config}
    merged_config["ENABLED"] = analysis_config.get("ENABLED", False)

    return NewsItemAnalyzer(merged_config)
