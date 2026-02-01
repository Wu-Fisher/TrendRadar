# TrendRadar AI 实现方案

> 版本：v1.0
> 日期：2026-01-30

---

## 一、方案选型结论

### 1.1 推荐方案

| 层级 | 技术选型 | 理由 |
|------|----------|------|
| **AI 框架** | CrewAI | 轻量、多Agent协作、API简洁 |
| **RAG/向量库** | LlamaIndex + ChromaDB | RAG能力强、向量库集成好 |
| **LLM 后端** | SiliconFlow (GLM-4) | 国内访问稳定、成本低 |
| **队列** | 内存队列 (后续可切 Redis) | 简单起步、易于扩展 |

### 1.2 框架对比结论

```
推荐度排序:
1. CrewAI ⭐⭐⭐⭐⭐ - 多Agent协作最佳，新闻分析场景契合
2. LlamaIndex ⭐⭐⭐⭐ - RAG能力强，适合知识库/向量检索
3. LangChain ⭐⭐⭐⭐ - 功能全面，但依赖重、学习曲线陡
4. Haystack ⭐⭐⭐ - 管道架构好，但社区相对小
5. AutoGen ⭐⭐⭐ - 正在重构，不推荐现在接入
```

---

## 二、核心流程图

### 2.1 整体数据流

```
                                    TrendRadar AI 数据流
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                                                                          │
    │   ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐   │
    │   │  同花顺  │ ──▶  │  过滤器  │ ──▶  │ AI 队列 │ ──▶  │  推送器  │   │
    │   │   爬虫   │      │ (关键词) │      │ (分析)  │      │ (多渠道) │   │
    │   └──────────┘      └──────────┘      └──────────┘      └──────────┘   │
    │        │                  │                 │                 │         │
    │        │                  │                 │                 │         │
    │        ▼                  ▼                 ▼                 ▼         │
    │   ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐   │
    │   │  TAPP    │      │ 匹配的   │      │ AI增强   │      │  飞书    │   │
    │   │  API     │      │ 新闻条目 │      │ 结果     │      │  钉钉    │   │
    │   └──────────┘      └──────────┘      └──────────┘      │  邮件    │   │
    │                                                          │  ...     │   │
    │                                                          └──────────┘   │
    │                                                                          │
    └─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 两阶段推送流程

```
    Phase 1: 即时推送 (延迟 < 1秒)
    ════════════════════════════════════════════════════════════════════════════

    新闻爬取 ──▶ 关键词过滤 ──▶ 即时推送
                    │              │
                    │              ▼
                    │         ┌─────────────┐
                    │         │ 推送内容:   │
                    │         │ - 标题      │
                    │         │ - 原始摘要  │
                    │         │ - 链接      │
                    │         └─────────────┘
                    │
                    ▼
    Phase 2: AI增强推送 (延迟 10-30秒)
    ════════════════════════════════════════════════════════════════════════════

    入队等待 ──▶ AI 分析 ──▶ 结果推送
                    │              │
                    ▼              ▼
            ┌──────────────┐  ┌─────────────┐
            │ AI 处理:     │  │ 推送内容:   │
            │ - 摘要生成   │  │ - AI摘要    │
            │ - 关键词提取 │  │ - 关键词    │
            │ - 情感分析   │  │ - 情感标签  │
            │ - 重要性评分 │  │ - 重要性    │
            └──────────────┘  └─────────────┘
```

---

## 三、目录结构

```
trendradar/
├── ai/                           # AI 层 (新增)
│   ├── __init__.py
│   ├── config.py                 # AI 配置管理
│   ├── base.py                   # 基类和接口定义
│   │
│   ├── queue/                    # 队列管理
│   │   ├── __init__.py
│   │   ├── manager.py            # 队列管理器
│   │   └── worker.py             # 工作线程
│   │
│   ├── pipeline/                 # 处理管道
│   │   ├── __init__.py
│   │   ├── engine.py             # 管道引擎
│   │   └── steps.py              # 管道步骤
│   │
│   ├── analyzers/                # 分析器实现
│   │   ├── __init__.py
│   │   ├── summarizer.py         # 摘要生成
│   │   ├── keywords.py           # 关键词提取
│   │   ├── sentiment.py          # 情感分析
│   │   └── aggregator.py         # 聚合分析
│   │
│   ├── agents/                   # Agent 框架适配
│   │   ├── __init__.py
│   │   ├── crewai_adapter.py     # CrewAI 适配器
│   │   └── simple_adapter.py     # 简单 LLM 调用
│   │
│   └── prompts/                  # Prompt 模板
│       ├── summarize.txt
│       ├── keywords.txt
│       └── aggregate.txt
│
├── crawler/                      # 爬虫层 (已有)
│   ├── runner.py                 # 修改: 添加 AI 集成点
│   └── ...
│
└── notification/                 # 推送层 (已有)
    ├── dispatcher.py             # 修改: 支持两阶段推送
    └── ...
```

---

## 四、核心代码结构

### 4.1 基类定义 (ai/base.py)

```python
"""AI 层基类定义"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class NewsItemForAI:
    """传递给 AI 层的新闻数据"""
    id: str
    title: str
    content: str
    full_content: str = ""
    url: str = ""
    published_at: str = ""
    source: str = ""
    matched_keywords: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """AI 分析结果"""
    news_id: str
    summary: str = ""
    keywords: List[str] = field(default_factory=list)
    sentiment: str = "neutral"    # positive/negative/neutral
    importance: int = 3           # 1-5
    category: str = ""
    analyzed_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    model_used: str = ""
    raw_response: str = ""
    success: bool = True
    error: str = ""


class AIAnalyzerBase(ABC):
    """AI 分析器基类"""

    @abstractmethod
    async def analyze(
        self,
        item: NewsItemForAI,
        prompt: Optional[str] = None
    ) -> AnalysisResult:
        """分析单条新闻"""
        pass

    @abstractmethod
    async def batch_analyze(
        self,
        items: List[NewsItemForAI]
    ) -> List[AnalysisResult]:
        """批量分析"""
        pass


class PipelineStep(ABC):
    """管道步骤基类"""

    @abstractmethod
    async def process(
        self,
        item: NewsItemForAI,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理一个步骤，返回更新后的 context"""
        pass
```

### 4.2 队列管理器 (ai/queue/manager.py)

```python
"""AI 队列管理器"""

import asyncio
import uuid
from typing import Dict, Optional, Callable
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from ..base import NewsItemForAI, AnalysisResult, TaskStatus


@dataclass
class QueueTask:
    """队列任务"""
    id: str
    item: NewsItemForAI
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[AnalysisResult] = None
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    retry_count: int = 0


class AIQueueManager:
    """AI 队列管理器"""

    def __init__(
        self,
        max_size: int = 100,
        max_workers: int = 2,
        max_retries: int = 3
    ):
        self.max_size = max_size
        self.max_workers = max_workers
        self.max_retries = max_retries

        self._queue: deque[QueueTask] = deque(maxlen=max_size)
        self._tasks: Dict[str, QueueTask] = {}
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._processor: Optional[Callable] = None

    def set_processor(self, processor: Callable):
        """设置处理函数"""
        self._processor = processor

    async def enqueue(self, item: NewsItemForAI) -> str:
        """入队，返回任务 ID"""
        task_id = str(uuid.uuid4())
        task = QueueTask(id=task_id, item=item)
        self._queue.append(task)
        self._tasks[task_id] = task
        return task_id

    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        task = self._tasks.get(task_id)
        return task.status if task else None

    def get_result(self, task_id: str) -> Optional[AnalysisResult]:
        """获取分析结果"""
        task = self._tasks.get(task_id)
        return task.result if task else None

    async def start(self):
        """启动工作线程"""
        if self._running:
            return
        self._running = True
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)

    async def stop(self):
        """停止工作线程"""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        self._workers.clear()

    async def _worker_loop(self, worker_id: int):
        """工作循环"""
        while self._running:
            try:
                if not self._queue:
                    await asyncio.sleep(0.1)
                    continue

                task = self._queue.popleft()
                task.status = TaskStatus.PROCESSING

                try:
                    if self._processor:
                        result = await self._processor(task.item)
                        task.result = result
                        task.status = TaskStatus.COMPLETED
                except Exception as e:
                    task.retry_count += 1
                    if task.retry_count < self.max_retries:
                        task.status = TaskStatus.PENDING
                        self._queue.append(task)
                    else:
                        task.status = TaskStatus.FAILED
                        task.result = AnalysisResult(
                            news_id=task.item.id,
                            success=False,
                            error=str(e)
                        )
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[AI Worker {worker_id}] Error: {e}")
                await asyncio.sleep(1)
```

### 4.3 CrewAI 适配器 (ai/agents/crewai_adapter.py)

```python
"""CrewAI 框架适配器"""

from typing import List, Optional
from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI

from ..base import (
    AIAnalyzerBase,
    NewsItemForAI,
    AnalysisResult
)


class CrewAIAnalyzer(AIAnalyzerBase):
    """基于 CrewAI 的新闻分析器"""

    def __init__(self, config: dict):
        self.config = config
        self._init_llm()
        self._init_agents()

    def _init_llm(self):
        """初始化 LLM"""
        self.llm = ChatOpenAI(
            model=self.config.get("model", "gpt-4o-mini"),
            api_key=self.config.get("api_key"),
            base_url=self.config.get("base_url"),
            temperature=0.3
        )

    def _init_agents(self):
        """初始化 Agent"""
        # 新闻分析师
        self.analyst = Agent(
            role="财经新闻分析师",
            goal="深入分析财经新闻，提取关键信息和投资机会",
            backstory="""你是一位资深财经分析师，拥有20年从业经验。
            你擅长快速识别新闻中的关键信息，评估其对市场的影响。""",
            llm=self.llm,
            verbose=False
        )

        # 摘要专家
        self.summarizer = Agent(
            role="摘要撰写专家",
            goal="将复杂信息提炼为简洁摘要",
            backstory="""你是专业的内容编辑，擅长用精炼的语言
            总结复杂信息，确保读者快速理解要点。""",
            llm=self.llm,
            verbose=False
        )

    async def analyze(
        self,
        item: NewsItemForAI,
        prompt: Optional[str] = None
    ) -> AnalysisResult:
        """分析单条新闻"""
        try:
            # 创建分析任务
            analyze_task = Task(
                description=f"""
                分析以下财经新闻，提取关键信息:

                标题: {item.title}
                内容: {item.content or item.full_content[:500]}

                请提供:
                1. 3-5个关键词
                2. 情感倾向 (积极/消极/中性)
                3. 重要性评分 (1-5)
                """,
                agent=self.analyst,
                expected_output="结构化的分析结果"
            )

            # 创建摘要任务
            summary_task = Task(
                description="基于分析结果，生成一句话摘要（不超过50字）",
                agent=self.summarizer,
                expected_output="简洁摘要",
                context=[analyze_task]
            )

            # 执行
            crew = Crew(
                agents=[self.analyst, self.summarizer],
                tasks=[analyze_task, summary_task],
                verbose=False
            )
            result = crew.kickoff()

            # 解析结果
            return self._parse_crew_result(item.id, result)

        except Exception as e:
            return AnalysisResult(
                news_id=item.id,
                success=False,
                error=str(e)
            )

    async def batch_analyze(
        self,
        items: List[NewsItemForAI]
    ) -> List[AnalysisResult]:
        """批量分析"""
        results = []
        for item in items:
            result = await self.analyze(item)
            results.append(result)
        return results

    def _parse_crew_result(
        self,
        news_id: str,
        crew_output
    ) -> AnalysisResult:
        """解析 CrewAI 输出"""
        # 简化解析，实际需要更复杂的解析逻辑
        output_str = str(crew_output)

        return AnalysisResult(
            news_id=news_id,
            summary=output_str[:100],
            keywords=[],  # 从输出中提取
            sentiment="neutral",
            importance=3,
            model_used=self.config.get("model", "unknown"),
            raw_response=output_str,
            success=True
        )
```

### 4.4 简单 LLM 分析器 (ai/agents/simple_adapter.py)

```python
"""简单 LLM 直调分析器"""

import json
from typing import List, Optional
from openai import AsyncOpenAI

from ..base import (
    AIAnalyzerBase,
    NewsItemForAI,
    AnalysisResult
)


class SimpleLLMAnalyzer(AIAnalyzerBase):
    """简单的 LLM 直调分析器"""

    DEFAULT_PROMPT = """你是一位专业的财经新闻分析师。请分析以下新闻内容，并以 JSON 格式返回结果。

新闻标题: {title}
新闻内容: {content}

请返回以下格式的 JSON:
{{
    "summary": "一句话摘要（不超过50字）",
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "sentiment": "positive/negative/neutral",
    "importance": 1-5的整数
}}

只返回 JSON，不要其他内容。"""

    def __init__(self, config: dict):
        self.config = config
        self.client = AsyncOpenAI(
            api_key=config.get("api_key"),
            base_url=config.get("base_url")
        )
        self.model = config.get("model", "gpt-4o-mini")
        self.prompt = config.get("prompt", self.DEFAULT_PROMPT)

    async def analyze(
        self,
        item: NewsItemForAI,
        prompt: Optional[str] = None
    ) -> AnalysisResult:
        """分析单条新闻"""
        try:
            user_prompt = (prompt or self.prompt).format(
                title=item.title,
                content=item.content or item.full_content[:500]
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            content = response.choices[0].message.content
            return self._parse_response(item.id, content)

        except Exception as e:
            return AnalysisResult(
                news_id=item.id,
                success=False,
                error=str(e)
            )

    async def batch_analyze(
        self,
        items: List[NewsItemForAI]
    ) -> List[AnalysisResult]:
        """批量分析"""
        import asyncio
        tasks = [self.analyze(item) for item in items]
        return await asyncio.gather(*tasks)

    def _parse_response(
        self,
        news_id: str,
        content: str
    ) -> AnalysisResult:
        """解析 LLM 响应"""
        try:
            # 尝试提取 JSON
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            data = json.loads(content)

            return AnalysisResult(
                news_id=news_id,
                summary=data.get("summary", ""),
                keywords=data.get("keywords", []),
                sentiment=data.get("sentiment", "neutral"),
                importance=int(data.get("importance", 3)),
                model_used=self.model,
                raw_response=content,
                success=True
            )
        except Exception as e:
            return AnalysisResult(
                news_id=news_id,
                summary=content[:100] if content else "",
                model_used=self.model,
                raw_response=content,
                success=True,
                error=f"Parse warning: {e}"
            )
```

---

## 五、集成点修改

### 5.1 CrawlerDaemon 修改

```python
# scripts/run_crawler_daemon.py 中需要添加的代码

class CrawlerDaemon:
    def __init__(self, ...):
        # ... 现有代码 ...

        # AI 分析器 (新增)
        self._ai_analyzer = None
        self._ai_queue = None
        if self.config.get("AI", {}).get("ENABLED", False):
            self._init_ai()

    def _init_ai(self):
        """初始化 AI 组件"""
        from trendradar.ai.queue.manager import AIQueueManager
        from trendradar.ai.agents import create_analyzer

        ai_config = self.config.get("AI", {})

        # 创建分析器
        self._ai_analyzer = create_analyzer(ai_config)

        # 创建队列
        queue_config = ai_config.get("QUEUE", {})
        self._ai_queue = AIQueueManager(
            max_size=queue_config.get("MAX_SIZE", 100),
            max_workers=queue_config.get("WORKERS", 2)
        )
        self._ai_queue.set_processor(self._process_ai_item)

    async def _process_ai_item(self, item):
        """处理 AI 分析"""
        result = await self._ai_analyzer.analyze(item)
        if result.success:
            # Phase 2 推送
            await self._send_enhanced_notification(result)
        return result

    def _send_notification(self, new_items: list):
        """发送即时通知 (Phase 1)"""
        # ... 现有推送逻辑 ...

        # 新增: 入队 AI 分析
        if self._ai_queue and self.config.get("AI", {}).get("TWO_PHASE_PUSH", {}).get("ENABLED"):
            for item in new_items:
                if not item.filtered_out:
                    ai_item = self._convert_to_ai_item(item)
                    asyncio.create_task(self._ai_queue.enqueue(ai_item))
```

---

## 六、配置示例

```yaml
# config.yaml 完整示例

AI:
  ENABLED: true

  LLM:
    PROVIDER: "siliconflow"
    MODEL: "glm-4-flash"
    API_KEY: "${SILICONFLOW_API_KEY}"
    BASE_URL: "https://api.siliconflow.cn/v1"

  FRAMEWORK: "simple"  # simple | crewai

  QUEUE:
    ENABLED: true
    MAX_SIZE: 100
    WORKERS: 2
    RETRY_COUNT: 3

  TWO_PHASE_PUSH:
    ENABLED: true
    PHASE1_IMMEDIATE: true
    PHASE2_ENHANCED: true
    PHASE2_CHANNELS:
      - feishu
      - email

  PROMPTS:
    DIR: "prompts"
    SUMMARIZE: "summarize.txt"
```

---

## 七、下一步行动

1. **创建 AI 模块目录结构**
2. **实现基类和简单分析器**
3. **修改 CrawlerDaemon 添加 AI 集成点**
4. **测试无 AI 时基础流程正常**
5. **逐步添加 CrewAI 和向量库支持**
