"""
Decision model - stores AI decision records
"""
from datetime import datetime
from typing import Optional
from enum import Enum

from sqlalchemy import String, Boolean, DateTime, Text, Integer, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.config import Base


class DecisionType(str, Enum):
    """Decision type enumeration"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    WATCH = "watch"


class DecisionSource(str, Enum):
    """Decision source enumeration"""
    AI_ANALYSIS = "ai_analysis"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    SENTIMENT = "sentiment"
    MANUAL = "manual"


class Decision(Base):
    """
    Decision model - stores AI trading decisions
    """
    __tablename__ = "decisions"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Foreign keys
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    portfolio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("portfolios.id"), nullable=True, index=True)
    
    # Decision details
    decision_type: Mapped[DecisionType] = mapped_column(SQLEnum(DecisionType), nullable=False)
    source: Mapped[DecisionSource] = mapped_column(SQLEnum(DecisionSource), nullable=False)
    asset: Mapped[str] = mapped_column(String(20), default="GOLD", index=True)
    
    # Decision data
    signal_strength: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 1.0
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 1.0
    price_target: Mapped[Optional[float]] = mapped_column(Float)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float)
    
    # Reasoning
    reason_zh: Mapped[Optional[str]] = mapped_column(Text)  # Chinese reasoning
    reason_en: Mapped[Optional[str]] = mapped_column(Text)  # English reasoning
    
    # Technical indicators snapshot (JSON string)
    indicators_snapshot: Mapped[Optional[str]] = mapped_column(Text)
    
    # Analysis dimensions scores (JSON string)
    analysis_scores: Mapped[Optional[str]] = mapped_column(Text)
    
    # Execution status
    is_executed: Mapped[bool] = mapped_column(Boolean, default=False)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    execution_price: Mapped[Optional[float]] = mapped_column(Float)
    
    # Metadata
    model_version: Mapped[str] = mapped_column(String(50), default="v1")
    extra_data: Mapped[Optional[str]] = mapped_column(Text)  # Additional JSON metadata
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="decisions")
    portfolio: Mapped[Optional["Portfolio"]] = relationship(back_populates="decisions")

    def __repr__(self):
        return f"<Decision(id={self.id}, type={self.decision_type}, asset={self.asset}, strength={self.signal_strength})>"