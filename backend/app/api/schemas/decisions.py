"""
Decision request/response schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from app.models.decision import DecisionType, DecisionSource


# ── Request Schemas ────────────────────────────────────────────────────────────

class CreateDecisionRequest(BaseModel):
    """Create new decision request"""
    decision_type: DecisionType = Field(..., description="決策類型: buy, sell, hold, watch")
    source: DecisionSource = Field(..., description="決策來源")
    asset: str = Field(default="GOLD", description="資產")
    signal_strength: float = Field(..., ge=0.0, le=1.0, description="信號強度")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    price_target: Optional[float] = Field(None, description="目標價")
    stop_loss: Optional[float] = Field(None, description="止損價")
    reason_zh: Optional[str] = Field(None, description="決策原因（中文）")
    reason_en: Optional[str] = Field(None, description="決策原因（英文）")
    portfolio_id: Optional[int] = Field(None, description="投資組合 ID")


class UpdateDecisionRequest(BaseModel):
    """Update existing decision request"""
    price_target: Optional[float] = Field(None)
    stop_loss: Optional[float] = Field(None)
    reason_zh: Optional[str] = Field(None)
    reason_en: Optional[str] = Field(None)


class ExecuteDecisionRequest(BaseModel):
    """Execute a decision request"""
    execution_price: Optional[float] = Field(None, description="執行價格（可選，默認使用市價）")
    notes: Optional[str] = Field(None, description="執行備註")


# ── Response Schemas ────────────────────────────────────────────────────────────

class DecisionResponse(BaseModel):
    """Decision response"""
    id: int
    user_id: int
    decision_type: DecisionType
    source: DecisionSource
    asset: str
    signal_strength: float
    confidence: float
    price_target: Optional[float]
    stop_loss: Optional[float]
    reason_zh: Optional[str]
    reason_en: Optional[str]
    indicators_snapshot: Optional[str]
    analysis_scores: Optional[str]
    is_executed: bool
    executed_at: Optional[datetime]
    execution_price: Optional[float]
    model_version: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DecisionListResponse(BaseModel):
    """Decision list response with pagination"""
    items: List[DecisionResponse]
    total: int
    page: int
    page_size: int
    pages: int


class RecommendationResponse(BaseModel):
    """AI recommendation response"""
    decision: DecisionResponse
    reasoning: str = Field(..., description="推薦理由")
    risk_level: str = Field(..., description="風險等級: low, medium, high")
    suggestions: List[str] = Field(default_factory=list, description="建議")
    warnings: List[str] = Field(default_factory=list, description="警告")


class DecisionStatsResponse(BaseModel):
    """Decision statistics response"""
    total_decisions: int
    buy_count: int
    sell_count: int
    hold_count: int
    watch_count: int
    executed_count: int
    pending_count: int
    avg_confidence: float
    avg_signal_strength: float
    win_rate: Optional[float] = Field(None, description="勝率（需歷史數據）")
