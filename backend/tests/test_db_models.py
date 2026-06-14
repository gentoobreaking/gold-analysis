"""Tests for database models in gold-analysis project.

These tests verify that the SQLAlchemy ORM models can be instantiated,
that relationships are correctly configured, and that the Pydantic settings
for the database connection are loadable.
"""

import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.app.db.config import Settings, Base, get_postgres_engine
from backend.app.models.user import User
from backend.app.models.portfolio import Portfolio
from backend.app.models.portfolio_holding import PortfolioHolding
from backend.app.models.decision import Decision, DecisionType, DecisionSource
from backend.app.models.alert import Alert, AlertType

# Use an in‑memory SQLite database for fast isolated testing.
# In production the project uses PostgreSQL, but SQLite supports the
# same schema for unit tests.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="module")
async def async_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture(scope="function")
async def async_session(async_engine) -> AsyncSession:
    async_session_factory = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as session:
        yield session
        await session.rollback()

@pytest.mark.asyncio
async def test_create_user(async_session: AsyncSession):
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed",
    )
    async_session.add(user)
    await async_session.commit()
    assert user.id is not None

@pytest.mark.asyncio
async def test_portfolio_relationship(async_session: AsyncSession):
    # Create a user first
    user = User(username="port_user", email="port@example.com", hashed_password="pwd")
    async_session.add(user)
    await async_session.flush()

    portfolio = Portfolio(user_id=user.id, name="My Portfolio", initial_capital=1000)
    async_session.add(portfolio)
    await async_session.commit()
    assert portfolio.id is not None
    # Verify relationship back to user
    await async_session.refresh(portfolio)
    assert portfolio.user.id == user.id

@pytest.mark.asyncio
async def test_holding_and_decision(async_session: AsyncSession):
    # User & portfolio
    user = User(username="hold_user", email="hold@example.com", hashed_password="pwd")
    portfolio = Portfolio(name="HoldPort", user=user, initial_capital=5000)
    async_session.add_all([user, portfolio])
    await async_session.flush()

    holding = PortfolioHolding(
        portfolio_id=portfolio.id,
        asset_type="GOLD",
        quantity=10,
        avg_cost=1800,
    )
    decision = Decision(
        user_id=user.id,
        portfolio_id=portfolio.id,
        decision_type=DecisionType.BUY,
        source=DecisionSource.AI_ANALYSIS,
        asset="GOLD",
        signal_strength=0.9,
        confidence=0.95,
    )
    async_session.add_all([holding, decision])
    await async_session.commit()

    assert holding.id is not None
    assert decision.id is not None
    # Verify relationships
    await async_session.refresh(holding)
    await async_session.refresh(decision)
    assert holding.portfolio.id == portfolio.id
    assert decision.user.id == user.id
    assert decision.portfolio.id == portfolio.id

@pytest.mark.asyncio
async def test_alert_model(async_session: AsyncSession):
    user = User(username="alert_user", email="alert@example.com", hashed_password="pwd")
    async_session.add(user)
    await async_session.flush()

    alert = Alert(
        user_id=user.id,
        alert_type=AlertType.PRICE_ABOVE,
        asset="GOLD",
        target_price=2000,
    )
    async_session.add(alert)
    await async_session.commit()
    assert alert.id is not None
    await async_session.refresh(alert)
    assert alert.user.id == user.id

def test_settings_load():
    # Ensure Settings can load defaults from .env.example without error
    settings = Settings(_env_file="backend/.env.example")
    assert settings.database_url.startswith("postgresql+asyncpg://")
