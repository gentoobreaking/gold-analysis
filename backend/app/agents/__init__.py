"""
Agents 模塊 - OpenClaw Agent 框架集成

提供黃金分析系統的多 Agent 協作能力。
"""

from .base import GoldAnalysisAgent
from .coordinator import AgentCoordinator, PipelineStage
from .decision_recommender import (
    DecisionRecommendationAgent,
    DecisionType,
    PositionSize,
    TradingRecommendation,
)
from .fundamental_analyzer import FactorAnalysis, FactorDirection, FactorType, FundamentalAnalyzer

__all__ = [
    "AgentCoordinator",
    # Decision Recommendation
    "DecisionRecommendationAgent",
    "DecisionType",
    "FactorAnalysis",
    "FactorDirection",
    "FactorType",
    # Fundamental Analysis
    "FundamentalAnalyzer",
    # Base
    "GoldAnalysisAgent",
    "PipelineStage",
    "PositionSize",
    "TradingRecommendation",
]
