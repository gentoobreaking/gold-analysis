"""
Webhook signal schemas (T067)

TradingView / 外部 JSON webhook 訊號對應到內部 Decision 結構。
"""
from __future__ import annotations

from app.models.decision import DecisionType
from pydantic import BaseModel, Field


class WebhookSignal(BaseModel):
    """外部 webhook payload 標準格式。

    TradingView 警報 webhook 的典型 JSON：
    {
      "symbol": "XAUUSD",
      "action": "buy",
      "price": 2050.5,
      "confidence": 0.75,
      "signal": "RSI oversold bounce",
      "reason": ["RSI < 30", "MA5 > MA20"],
      "timestamp": "2026-08-28T03:34:16Z"
    }
    """

    symbol: str = Field(default="GOLD", description="資產符號")
    action: DecisionType = Field(..., description="買入/賣出/持有/觀望")
    price: float | None = Field(None, description="價格")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="置信度")
    signal: str = Field(..., description="訊號描述")
    reason: list[str] = Field(default_factory=list, description="理由列表")
    timestamp: str | None = Field(None, description="ISO 時間戳")


class WebhookResponse(BaseModel):
    """Webhook 接收響應"""

    accepted: bool
    decision_id: int | None = None
    action_taken: str = Field(..., description="accepted / simulated / rejected")
    source: str = "external"
    message: str = ""
