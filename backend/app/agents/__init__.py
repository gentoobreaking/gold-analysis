"""
Agents 模塊 - OpenClaw Agent 框架集成

提供黃金分析系統的多 Agent 協作能力。
"""

from .base import GoldAnalysisAgent
from .coordinator import AgentCoordinator, PipelineStage
from .fundamental_analyzer import FundamentalAnalyzer, FactorType, FactorDirection, FactorAnalysis
from .decision_recommender import (
    DecisionRecommendationAgent,
    DecisionType,
    PositionSize,
    TradingRecommendation
)

__all__ = [
    # Base
    "GoldAnalysisAgent",
    "AgentCoordinator",
    "PipelineStage",
    # Fundamental Analysis
    "FundamentalAnalyzer",
    "FactorType",
    "FactorDirection",
    "FactorAnalysis",
    # Decision Recommendation
    "DecisionRecommendationAgent",
    "DecisionType",
    "PositionSize",
    "TradingRecommendation",
]
