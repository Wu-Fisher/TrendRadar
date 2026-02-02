# coding=utf-8
"""
CrewAI 新闻分析器

使用 CrewAI 框架进行新闻分析，支持：
- 单 Agent 快速分析模式
- 多 Agent 深度分析模式
- 自定义 LLM 配置（SiliconFlow/OpenAI 兼容）
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from crewai import Agent, Task, Crew, Process, LLM
from pydantic import BaseModel

from .simple import AnalysisResult


class NewsAnalysisOutput(BaseModel):
    """新闻分析结构化输出"""
    summary: str
    keywords: List[str]
    sentiment: str
    importance: int
    category: str


class CrewAnalyzer:
    """CrewAI 新闻分析器

    使用 CrewAI 框架进行新闻分析，支持自定义 LLM。
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化分析器

        Args:
            config: 配置字典，包含 AI 配置（由 loader.py 标准化为大写键名）
        """
        # 提取 AI 配置（loader.py 已标准化为大写键名）
        ai_config = config.get("AI", config)

        # 直接使用大写键名（loader.py 已保证标准化）
        self.model = ai_config.get("MODEL", "")
        self.api_key = ai_config.get("API_KEY", "")
        self.api_base = ai_config.get("API_BASE", "")
        self.temperature = float(ai_config.get("TEMPERATURE", 0.7))
        self.max_tokens = int(ai_config.get("MAX_TOKENS", 2000))
        self.timeout = int(ai_config.get("TIMEOUT", 120))

        # 初始化 LLM
        self._llm = self._create_llm()

        # 创建 Agent
        self._analyst_agent = self._create_analyst_agent()

        # Prompt 文件目录
        self.prompts_dir = Path(__file__).parent.parent / "prompts"
        self._prompts: Dict[str, str] = {}
        self._load_prompts()

    def _create_llm(self) -> LLM:
        """创建 LLM 实例"""
        # 设置环境变量（CrewAI 会读取）
        if self.api_key:
            os.environ["OPENAI_API_KEY"] = self.api_key
        if self.api_base:
            os.environ["OPENAI_API_BASE"] = self.api_base

        return LLM(
            model=self.model,
            api_key=self.api_key,
            base_url=self.api_base if self.api_base else None,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout,
        )

    def _create_analyst_agent(self) -> Agent:
        """创建新闻分析 Agent"""
        return Agent(
            role="财经新闻分析师",
            goal="分析财经新闻，提取关键信息，判断市场影响",
            backstory="""你是一位资深的财经新闻分析师，拥有多年金融市场分析经验。
            你擅长从新闻中提取关键信息，判断新闻对市场的潜在影响，
            并能准确识别新闻的情感倾向和重要性。
            你的分析简洁、准确、专业。""",
            llm=self._llm,
            verbose=False,
            allow_delegation=False,
        )

    def _load_prompts(self):
        """加载 Prompt 文件"""
        if not self.prompts_dir.exists():
            return

        for file in self.prompts_dir.glob("*.txt"):
            try:
                self._prompts[file.stem] = file.read_text(encoding="utf-8")
            except Exception as e:
                print(f"[CrewAnalyzer] 加载 Prompt 失败 {file}: {e}")

    def _get_prompt(self, name: str) -> str:
        """获取 Prompt 模板"""
        default = """分析以下新闻，返回 JSON 格式结果。

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
        return self._prompts.get(name, default)

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
            model_used=self.model
        )

        try:
            # 准备 Prompt
            prompt_template = self._get_prompt(prompt_name)
            description = prompt_template.format(
                title=title,
                content=content[:1500] if len(content) > 1500 else content
            )

            # 创建分析任务
            analysis_task = Task(
                description=description,
                expected_output="JSON 格式的分析结果",
                agent=self._analyst_agent,
            )

            # 创建 Crew 并执行
            crew = Crew(
                agents=[self._analyst_agent],
                tasks=[analysis_task],
                process=Process.sequential,
                verbose=False,
            )

            # 执行分析
            crew_result = crew.kickoff()

            # 解析结果
            result.raw_response = str(crew_result)
            result = self._parse_response(result, str(crew_result))

        except Exception as e:
            result.success = False
            result.error = str(e)[:200]
            print(f"[CrewAnalyzer] 分析失败: {e}")

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

    def analyze_batch(
        self,
        news_items: List[Dict[str, str]],
        prompt_name: str = "analyze"
    ) -> List[AnalysisResult]:
        """
        批量分析新闻

        Args:
            news_items: 新闻列表，每项包含 id, title, content
            prompt_name: Prompt 模板名称

        Returns:
            分析结果列表
        """
        results = []
        for item in news_items:
            result = self.analyze(
                news_id=item.get("id", ""),
                title=item.get("title", ""),
                content=item.get("content", ""),
                prompt_name=prompt_name
            )
            results.append(result)
        return results


class MultiAgentCrewAnalyzer(CrewAnalyzer):
    """多 Agent 深度分析器

    使用多个专业 Agent 进行更深入的分析：
    - 新闻分析师：提取基本信息
    - 市场影响分析师：分析市场影响
    - 风险评估师：评估潜在风险
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        # 创建额外的 Agents
        self._market_agent = self._create_market_agent()
        self._risk_agent = self._create_risk_agent()

    def _create_market_agent(self) -> Agent:
        """创建市场影响分析 Agent"""
        return Agent(
            role="市场影响分析师",
            goal="分析新闻对金融市场的潜在影响",
            backstory="""你是一位专注于市场影响分析的专家，
            能够准确判断新闻事件对股票、债券、商品等市场的影响。
            你善于识别利好和利空因素，并给出专业的市场展望。""",
            llm=self._llm,
            verbose=False,
            allow_delegation=False,
        )

    def _create_risk_agent(self) -> Agent:
        """创建风险评估 Agent"""
        return Agent(
            role="风险评估师",
            goal="评估新闻事件的潜在风险和不确定性",
            backstory="""你是一位经验丰富的风险评估专家，
            擅长识别新闻中的潜在风险因素和不确定性。
            你的分析客观、谨慎，能够帮助投资者规避风险。""",
            llm=self._llm,
            verbose=False,
            allow_delegation=False,
        )

    def deep_analyze(
        self,
        news_id: str,
        title: str,
        content: str,
    ) -> Dict[str, Any]:
        """
        深度分析新闻（多 Agent 协作）

        Args:
            news_id: 新闻 ID
            title: 标题
            content: 内容

        Returns:
            包含多维度分析结果的字典
        """
        try:
            truncated_content = content[:1500] if len(content) > 1500 else content

            # 创建任务链
            basic_analysis_task = Task(
                description=f"""分析以下新闻的基本信息：

标题: {title}
内容: {truncated_content}

提取：摘要、关键词、情感倾向、重要性（1-5）、分类""",
                expected_output="基本分析结果",
                agent=self._analyst_agent,
            )

            market_impact_task = Task(
                description=f"""基于以下新闻，分析对市场的潜在影响：

标题: {title}
内容: {truncated_content}

分析：受影响的市场/板块、影响方向（利好/利空）、影响程度""",
                expected_output="市场影响分析",
                agent=self._market_agent,
            )

            risk_assessment_task = Task(
                description=f"""评估以下新闻的潜在风险：

标题: {title}
内容: {truncated_content}

评估：主要风险因素、不确定性来源、建议关注点""",
                expected_output="风险评估结果",
                agent=self._risk_agent,
            )

            # 创建 Crew
            crew = Crew(
                agents=[self._analyst_agent, self._market_agent, self._risk_agent],
                tasks=[basic_analysis_task, market_impact_task, risk_assessment_task],
                process=Process.sequential,
                verbose=False,
            )

            # 执行分析
            result = crew.kickoff()

            return {
                "news_id": news_id,
                "success": True,
                "analysis": str(result),
                "model_used": self.model,
                "analyzed_at": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "news_id": news_id,
                "success": False,
                "error": str(e)[:200],
                "model_used": self.model,
                "analyzed_at": datetime.now().isoformat(),
            }


def create_crew_analyzer(config: Dict[str, Any], multi_agent: bool = False):
    """
    创建 CrewAI 分析器

    Args:
        config: 完整配置字典
        multi_agent: 是否使用多 Agent 模式

    Returns:
        CrewAnalyzer 或 MultiAgentCrewAnalyzer 实例
    """
    if multi_agent:
        return MultiAgentCrewAnalyzer(config)
    return CrewAnalyzer(config)
