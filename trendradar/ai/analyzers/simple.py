# coding=utf-8
"""
简单 LLM 分析器

直接调用 LLM API 进行新闻分析，支持：
- 外部 Prompt 文件加载
- 摘要生成
- 关键词提取
- 情感分析
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from trendradar.ai.client import AIClient


@dataclass
class AnalysisResult:
    """分析结果"""
    news_id: str                        # 新闻 ID
    summary: str = ""                   # 摘要
    keywords: List[str] = field(default_factory=list)  # 关键词
    sentiment: str = "neutral"          # 情感
    importance: int = 3                 # 重要性 1-5
    category: str = ""                  # 分类
    raw_response: str = ""              # 原始响应
    success: bool = True
    error: str = ""
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    model_used: str = ""

    def to_dict(self) -> Dict:
        return {
            "news_id": self.news_id,
            "summary": self.summary,
            "keywords": self.keywords,
            "sentiment": self.sentiment,
            "importance": self.importance,
            "category": self.category,
            "success": self.success,
            "error": self.error,
            "analyzed_at": self.analyzed_at,
            "model_used": self.model_used,
        }


class SimpleAnalyzer:
    """简单 LLM 分析器

    使用 AIClient 直接调用 LLM 进行分析。
    """

    # 默认 Prompt（如果文件不存在则使用）
    DEFAULT_PROMPT = """你是一位专业的财经新闻分析师。请分析以下新闻，返回 JSON 格式结果。

标题: {title}
内容: {content}

请返回以下格式的 JSON（只返回 JSON，不要其他内容）:
{{
    "summary": "一句话摘要（不超过50字）",
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "sentiment": "positive/negative/neutral",
    "importance": 1-5的整数,
    "category": "分类"
}}"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化分析器

        Args:
            config: 配置字典，包含 AI 配置
        """
        # 提取 AI 配置
        ai_config = config.get("AI", config)

        # 处理大小写兼容
        self.ai_config = {
            "MODEL": ai_config.get("MODEL") or ai_config.get("model", ""),
            "API_KEY": ai_config.get("API_KEY") or ai_config.get("api_key", ""),
            "API_BASE": ai_config.get("API_BASE") or ai_config.get("api_base", ""),
            "TEMPERATURE": ai_config.get("TEMPERATURE") or ai_config.get("temperature", 0.7),
            "MAX_TOKENS": ai_config.get("MAX_TOKENS") or ai_config.get("max_tokens", 2000),
            "TIMEOUT": ai_config.get("TIMEOUT") or ai_config.get("timeout", 60),
        }

        self._client: Optional[AIClient] = None
        self._prompts: Dict[str, str] = {}

        # Prompt 文件目录
        self.prompts_dir = Path(__file__).parent.parent / "prompts"

        # 加载 Prompt 文件
        self._load_prompts()

    def _load_prompts(self):
        """加载 Prompt 文件"""
        if not self.prompts_dir.exists():
            return

        for file in self.prompts_dir.glob("*.txt"):
            try:
                self._prompts[file.stem] = file.read_text(encoding="utf-8")
            except Exception as e:
                print(f"[SimpleAnalyzer] 加载 Prompt 失败 {file}: {e}")

    def _get_prompt(self, name: str) -> str:
        """获取 Prompt 模板"""
        return self._prompts.get(name, self.DEFAULT_PROMPT)

    def _init_client(self):
        """延迟初始化客户端"""
        if self._client is not None:
            return

        self._client = AIClient(self.ai_config)

    def analyze(
        self,
        news_id: str,
        title: str,
        content: str,
        prompt_name: str = "analyze"
    ) -> AnalysisResult:
        """
        分析新闻

        Args:
            news_id: 新闻 ID
            title: 标题
            content: 内容
            prompt_name: Prompt 模板名称

        Returns:
            AnalysisResult: 分析结果
        """
        result = AnalysisResult(
            news_id=news_id,
            model_used=self.ai_config.get("MODEL", "unknown")
        )

        try:
            self._init_client()

            # 准备 Prompt
            prompt_template = self._get_prompt(prompt_name)
            prompt = prompt_template.format(
                title=title,
                content=content[:1500] if len(content) > 1500 else content
            )

            # 调用 AI
            messages = [{"role": "user", "content": prompt}]
            response = self._client.chat(messages)

            result.raw_response = response
            result = self._parse_response(result, response)

        except Exception as e:
            result.success = False
            result.error = str(e)[:200]
            print(f"[SimpleAnalyzer] 分析失败: {e}")

        return result

    def _parse_response(self, result: AnalysisResult, response: str) -> AnalysisResult:
        """解析 AI 响应"""
        try:
            # 提取 JSON
            json_str = response.strip()

            # 处理 markdown 代码块
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                parts = json_str.split("```")
                if len(parts) >= 2:
                    json_str = parts[1]

            data = json.loads(json_str.strip())

            result.summary = data.get("summary", "")
            result.keywords = data.get("keywords", [])
            result.sentiment = data.get("sentiment", "neutral")
            result.importance = int(data.get("importance", 3))
            result.category = data.get("category", "")
            result.success = True

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # JSON 解析失败，尝试作为纯文本摘要
            result.summary = response[:100] if response else ""
            result.success = True
            result.error = f"JSON 解析警告: {str(e)[:50]}"

        return result

    def summarize(self, news_id: str, title: str, content: str) -> str:
        """
        仅生成摘要

        Args:
            news_id: 新闻 ID
            title: 标题
            content: 内容

        Returns:
            摘要文本
        """
        try:
            self._init_client()

            prompt_template = self._get_prompt("summarize")
            prompt = prompt_template.format(
                title=title,
                content=content[:1500] if len(content) > 1500 else content
            )

            messages = [{"role": "user", "content": prompt}]
            response = self._client.chat(messages)

            return response.strip()

        except Exception as e:
            print(f"[SimpleAnalyzer] 摘要生成失败: {e}")
            return ""

    def extract_keywords(self, news_id: str, title: str, content: str) -> List[str]:
        """
        提取关键词

        Args:
            news_id: 新闻 ID
            title: 标题
            content: 内容

        Returns:
            关键词列表
        """
        try:
            self._init_client()

            prompt_template = self._get_prompt("keywords")
            prompt = prompt_template.format(
                title=title,
                content=content[:1500] if len(content) > 1500 else content
            )

            messages = [{"role": "user", "content": prompt}]
            response = self._client.chat(messages)

            # 解析 JSON 数组
            json_str = response.strip()
            if "```" in json_str:
                json_str = json_str.split("```")[1] if "```json" not in json_str else json_str.split("```json")[1].split("```")[0]

            return json.loads(json_str.strip())

        except Exception as e:
            print(f"[SimpleAnalyzer] 关键词提取失败: {e}")
            return []

    @property
    def model(self) -> str:
        """当前使用的模型"""
        return self.ai_config.get("MODEL", "unknown")


def create_analyzer(config: Dict[str, Any]) -> SimpleAnalyzer:
    """
    创建分析器

    Args:
        config: 完整配置字典

    Returns:
        SimpleAnalyzer 实例
    """
    return SimpleAnalyzer(config)
