"""
Portfolio model - represents a user's investment portfolio
"""

from datetime import datetime, timezone

from app.db.config import Base
from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Portfolio(Base):
    """Portfolio model"""

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    initial_capital: Mapped[float] = mapped_column(Float, default=0.0)
    current_value: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc)
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="portfolios")  # noqa: F821
    holdings: Mapped[list["PortfolioHolding"]] = relationship(  # noqa: F821
        back_populates="portfolio", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["Decision"]] = relationship(back_populates="portfolio")  # noqa: F821

    def __repr__(self):
        return f"<Portfolio(id={self.id}, name={self.name}, capital={self.initial_capital})>"
