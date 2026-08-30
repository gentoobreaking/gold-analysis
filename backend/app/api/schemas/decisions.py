"""
Decision request/response schemas
"""

from datetime import datetime
from typing import Any

from app.models.decision import DecisionSource, DecisionType
from pydantic import BaseModel, Field

# ── Request Schemas ────────────────────────────────────────────────────────────


class CreateDecisionRequest(BaseModel):
    """Create new decision request"""

    decision_type: DecisionType = Field(..., description="決策類型: buy, sell, hold, watch")
    source: DecisionSource = Field(..., description="決策來源")
    asset: str = Field(default="GOLD", description="資產")
    signal_strength: float = Field(..., ge=0.0, le=1.0, description="信號強度")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    price_target: float | None = Field(None, description="目標價")
    stop_loss: float | None = Field(None, description="止損價")
    reason_zh: str | None = Field(None, description="決策原因（中文）")
    reason_en: str | None = Field(None, description="決策原因（英文）")
    portfolio_id: int | None = Field(None, description="投資組合 ID")


class UpdateDecisionRequest(BaseModel):
    """Update existing decision request"""

    price_target: float | None = Field(None)
    stop_loss: float | None = Field(None)
    reason_zh: str | None = Field(None)
    reason_en: str | None = Field(None)


class ExecuteDecisionRequest(BaseModel):
    """Execute a decision request"""

    execution_price: float | None = Field(None, description="執行價格（可選，默認使用市價）")
    notes: str | None = Field(None, description="執行備註")


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
    price_target: float | None
    stop_loss: float | None
    reason_zh: str | None
    reason_en: str | None
    indicators_snapshot: str | None
    analysis_scores: str | None
    is_executed: bool
    executed_at: datetime | None
    execution_price: float | None
    model_version: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DecisionListResponse(BaseModel):
    """Decision list response with pagination"""

    items: list[DecisionResponse]
    total: int
    page: int
    page_size: int
    pages: int


class RecommendationResponse(BaseModel):
    """AI recommendation response"""

    decision: DecisionResponse
    reasoning: str = Field(..., description="推薦理由")
    risk_level: str = Field(..., description="風險等級: low, medium, high")
    suggestions: list[str] = Field(default_factory=list, description="建議")
    warnings: list[str] = Field(default_factory=list, description="警告")
    explanation: dict[str, Any] | None = Field(
        None, description="決策可解釋性：ML 用 SHAP/feature_importance，規則用觸發因子 (T062)"
    )


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
    win_rate: float | None = Field(None, description="勝率（需歷史數據）")
