"""
Portfolio model - represents a user's investment portfolio
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Float, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.config import Base


class Portfolio(Base):
    """Portfolio model"""
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    initial_capital: Mapped[float] = mapped_column(Float, default=0.0)
    current_value: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="portfolios")
    holdings: Mapped[List["PortfolioHolding"]] = relationship(back_populates="portfolio", cascade="all, delete-orphan")
    decisions: Mapped[List["Decision"]] = relationship(back_populates="portfolio")

    def __repr__(self):
        return f"<Portfolio(id={self.id}, name={self.name}, capital={self.initial_capital})>"