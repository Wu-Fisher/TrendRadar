# coding=utf-8
"""AI 分析器模块"""

from .simple import SimpleAnalyzer, AnalysisResult, create_analyzer

# CrewAI 分析器（可选，需要 crewai 依赖）
try:
    from .crew_analyzer import (
        CrewAnalyzer,
        MultiAgentCrewAnalyzer,
        create_crew_analyzer,
    )
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    CrewAnalyzer = None
    MultiAgentCrewAnalyzer = None
    create_crew_analyzer = None

__all__ = [
    "SimpleAnalyzer",
    "AnalysisResult",
    "create_analyzer",
    "CrewAnalyzer",
    "MultiAgentCrewAnalyzer",
    "create_crew_analyzer",
    "CREWAI_AVAILABLE",
]
