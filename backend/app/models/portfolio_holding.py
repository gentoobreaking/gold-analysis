"""
PortfolioHolding model - individual asset positions within a portfolio
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.config import Base


class PortfolioHolding(Base):
    """Holding model inside a portfolio"""
    __tablename__ = "portfolio_holdings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)  # GOLD, DXY, etc.
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_price: Mapped[Optional[float]] = mapped_column(Float)
    market_value: Mapped[Optional[float]] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    portfolio: Mapped["Portfolio"] = relationship(back_populates="holdings")

    def __repr__(self):
        return f"<Holding(id={self.id}, asset={self.asset_type}, qty={self.quantity})>"