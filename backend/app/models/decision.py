"""
Decision model - stores AI decision records
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from app.db.config import Base
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship


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
    EXTERNAL = "external"


class Decision(Base):
    """
    Decision model - stores AI trading decisions
    """

    __table_args__ = {"schema": "core"}
    __tablename__ = "decisions"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign keys
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    portfolio_id: Mapped[int | None] = mapped_column(
        ForeignKey("portfolios.id"), nullable=True, index=True
    )

    # Decision details
    decision_type: Mapped[DecisionType] = mapped_column(SQLEnum(DecisionType), nullable=False)
    source: Mapped[DecisionSource] = mapped_column(SQLEnum(DecisionSource), nullable=False)
    asset: Mapped[str] = mapped_column(String(20), default="GOLD", index=True)

    # Decision data
    signal_strength: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 1.0
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 1.0
    price_target: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)

    # Reasoning
    reason_zh: Mapped[str | None] = mapped_column(Text)  # Chinese reasoning
    reason_en: Mapped[str | None] = mapped_column(Text)  # English reasoning

    # Technical indicators snapshot (JSON string)
    indicators_snapshot: Mapped[str | None] = mapped_column(Text)

    # Analysis dimensions scores (JSON string)
    analysis_scores: Mapped[str | None] = mapped_column(Text)

    # Execution status
    is_executed: Mapped[bool] = mapped_column(Boolean, default=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_price: Mapped[float | None] = mapped_column(Float)

    # Metadata
    model_version: Mapped[str] = mapped_column(String(50), default="v1")
    extra_data: Mapped[str | None] = mapped_column(Text)  # Additional JSON metadata

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="decisions")  # noqa: F821
    portfolio: Mapped[Optional["Portfolio"]] = relationship(back_populates="decisions")  # noqa: F821

    def __repr__(self):
        return f"<Decision(id={self.id}, type={self.decision_type}, asset={self.asset}, strength={self.signal_strength})>"  # noqa: E501
