"""
Alert model - user-defined price alerts and notifications
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from enum import Enum

from app.db.config import Base


class AlertType(str, Enum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    INDICATOR_CROSS = "indicator_cross"
    VOLUME_SPIKE = "volume_spike"


class Alert(Base):
    """Alert model for price or indicator notifications"""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    alert_type: Mapped[AlertType] = mapped_column(SQLEnum(AlertType), nullable=False)
    asset: Mapped[str] = mapped_column(String(20), nullable=False)
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    extra_data: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationship
    user: Mapped["User"] = relationship(back_populates="alerts")

    def __repr__(self):
        return f"<Alert(id={self.id}, asset={self.asset}, target={self.target_price}, active={self.is_active})>"