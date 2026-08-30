"""Daily Price model - maps to core.daily_prices table in PostgreSQL"""

from __future__ import annotations

from datetime import date

from app.db.config import Base
from sqlalchemy import Float, Integer, String
from sqlalchemy.dialects.postgresql import DATE, NUMERIC
from sqlalchemy.orm import Mapped, mapped_column


class DailyPrice(Base):
    """Represents a daily price record from core.daily_prices."""

    __table_args__ = {"schema": "core"}
    __tablename__ = "daily_prices"

    symbol: Mapped[str] = mapped_column(String(10), primary_key=True)
    trade_date: Mapped[date] = mapped_column(DATE, primary_key=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    adjusted_close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(Integer)
    turnover: Mapped[float | None] = mapped_column(NUMERIC(20, 2))
    source: Mapped[str | None] = mapped_column(String(100))
    freshness: Mapped[str | None] = mapped_column(String(30))
    source_role: Mapped[str] = mapped_column(String(30), nullable=False, default="CANONICAL")
