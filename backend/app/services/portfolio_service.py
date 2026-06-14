"""
Portfolio Service - 投資組合管理業務邏輯
"""
import logging
from typing import Optional
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.portfolio import Portfolio
from app.models.portfolio_holding import PortfolioHolding
from app.models.decision import Decision

logger = logging.getLogger(__name__)


class PortfolioService:
    """投資組合服務"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── CRUD ────────────────────────────────────────────────────────────────

    async def create_portfolio(
        self,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        initial_capital: float = 0.0,
    ) -> Portfolio:
        """創建投資組合"""
        portfolio = Portfolio(
            user_id=user_id,
            name=name,
            description=description,
            initial_capital=initial_capital,
            current_value=initial_capital,
        )
        self.session.add(portfolio)
        await self.session.commit()
        await self.session.refresh(portfolio)
        logger.info(f"Created portfolio {portfolio.id} for user {user_id}")
        return portfolio

    async def get_portfolio(self, portfolio_id: int) -> Optional[Portfolio]:
        """取得單一組合（帶持倉）"""
        stmt = (
            select(Portfolio)
            .options(selectinload(Portfolio.holdings))
            .where(Portfolio.id == portfolio_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_portfolios(self, user_id: int) -> list[Portfolio]:
        """列出用戶所有組合"""
        stmt = (
            select(Portfolio)
            .options(selectinload(Portfolio.holdings))
            .where(Portfolio.user_id == user_id)
            .order_by(Portfolio.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_portfolio(
        self,
        portfolio_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[Portfolio]:
        """更新組合基本資訊"""
        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            return None
        if name is not None:
            portfolio.name = name
        if description is not None:
            portfolio.description = description
        portfolio.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(portfolio)
        return portfolio

    async def delete_portfolio(self, portfolio_id: int) -> bool:
        """刪除組合（級聯刪除持倉）"""
        stmt = delete(Portfolio).where(Portfolio.id == portfolio_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    # ── 持倉管理 ─────────────────────────────────────────────────────────────

    async def add_holding(
        self,
        portfolio_id: int,
        asset_type: str,
        quantity: float,
        avg_cost: float,
        current_price: Optional[float] = None,
    ) -> Optional[PortfolioHolding]:
        """新增持倉"""
        # 檢查是否已存在相同資產的持倉，則合併
        existing = await self._get_holding(portfolio_id, asset_type)
        if existing:
            total_qty = existing.quantity + quantity
            existing.avg_cost = (existing.avg_cost * existing.quantity + avg_cost * quantity) / total_qty
            existing.quantity = total_qty
            if current_price is not None:
                existing.current_price = current_price
                existing.market_value = total_qty * current_price
            existing.updated_at = datetime.utcnow()
            await self.session.commit()
            await self.session.refresh(existing)
            await self._recalculate_portfolio_value(portfolio_id)
            return existing

        holding = PortfolioHolding(
            portfolio_id=portfolio_id,
            asset_type=asset_type,
            quantity=quantity,
            avg_cost=avg_cost,
            current_price=current_price,
            market_value=quantity * (current_price or avg_cost),
        )
        self.session.add(holding)
        await self.session.commit()
        await self.session.refresh(holding)
        await self._recalculate_portfolio_value(portfolio_id)
        return holding

    async def update_holding_price(
        self,
        portfolio_id: int,
        asset_type: str,
        current_price: float,
    ) -> Optional[PortfolioHolding]:
        """更新持倉市價"""
        holding = await self._get_holding(portfolio_id, asset_type)
        if not holding:
            return None
        holding.current_price = current_price
        holding.market_value = holding.quantity * current_price
        holding.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(holding)
        await self._recalculate_portfolio_value(portfolio_id)
        return holding

    async def reduce_holding(
        self,
        portfolio_id: int,
        asset_type: str,
        quantity: float,
    ) -> Optional[PortfolioHolding]:
        """減持（賣出部分持倉）"""
        holding = await self._get_holding(portfolio_id, asset_type)
        if not holding:
            return None
        if holding.quantity < quantity:
            raise ValueError(
                f"Cannot reduce holding: current={holding.quantity}, requested={quantity}"
            )
        holding.quantity -= quantity
        holding.updated_at = datetime.utcnow()
        if holding.quantity == 0:
            await self.session.delete(holding)
        await self.session.commit()
        await self._recalculate_portfolio_value(portfolio_id)
        return holding

    async def list_holdings(self, portfolio_id: int) -> list[PortfolioHolding]:
        """列出組合所有持倉"""
        stmt = select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_holding(
        self, portfolio_id: int, asset_type: str
    ) -> Optional[PortfolioHolding]:
        stmt = select(PortfolioHolding).where(
            PortfolioHolding.portfolio_id == portfolio_id,
            PortfolioHolding.asset_type == asset_type,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ── 績效計算 ─────────────────────────────────────────────────────────────

    async def calculate_performance(self, portfolio_id: int) -> dict:
        """
        計算組合績效指標

        Returns:
            {
                "total_return": float,          # 總收益率 %
                "total_gain_loss": float,       # 總損益金額
                "current_value": float,         # 當前市值
                "cash_balance": float,          # 現金餘額
                "invested_value": float,        # 已投資金額
                "unrealized_pnl": float,        # 未實現損益
                "positions": list[dict]         # 各持倉明細
            }
        """
        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        cash_balance = portfolio.current_value
        holdings = portfolio.holdings

        invested = 0.0
        current = 0.0
        positions = []

        for h in holdings:
            cost_basis = h.avg_cost * h.quantity
            market_val = (h.current_price or h.avg_cost) * h.quantity
            unrealized_pnl = market_val - cost_basis
            pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0.0

            invested += cost_basis
            current += market_val

            positions.append({
                "asset": h.asset_type,
                "quantity": h.quantity,
                "avg_cost": h.avg_cost,
                "current_price": h.current_price or h.avg_cost,
                "cost_basis": round(cost_basis, 2),
                "market_value": round(market_val, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(pnl_pct, 2),
            })

        total_invested = invested + cash_balance
        total_gain_loss = current + cash_balance - total_invested
        total_return = (total_gain_loss / total_invested * 100) if total_invested > 0 else 0.0

        return {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio.name,
            "initial_capital": round(portfolio.initial_capital, 2),
            "current_value": round(current + cash_balance, 2),
            "cash_balance": round(cash_balance, 2),
            "invested_value": round(invested, 2),
            "total_gain_loss": round(total_gain_loss, 2),
            "total_return_pct": round(total_return, 2),
            "unrealized_pnl": round(current - invested, 2),
            "positions": positions,
            "updated_at": datetime.utcnow().isoformat(),
        }

    async def add_cash(self, portfolio_id: int, amount: float) -> Portfolio:
        """存入現金"""
        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        portfolio.current_value += amount
        portfolio.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(portfolio)
        return portfolio

    async def withdraw_cash(self, portfolio_id: int, amount: float) -> Portfolio:
        """提取現金"""
        portfolio = await self.get_portfolio(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        if portfolio.current_value < amount:
            raise ValueError("Insufficient cash balance")
        portfolio.current_value -= amount
        portfolio.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(portfolio)
        return portfolio

    async def _recalculate_portfolio_value(self, portfolio_id: int) -> None:
        """重新計算並更新組合市值"""
        stmt = select(func.coalesce(func.sum(PortfolioHolding.market_value), 0)).where(
            PortfolioHolding.portfolio_id == portfolio_id
        )
        result = await self.session.execute(stmt)
        holdings_value: float = result.scalar() or 0.0

        stmt2 = select(Portfolio).where(Portfolio.id == portfolio_id)
        result2 = await self.session.execute(stmt2)
        portfolio = result2.scalar_one_or_none()
        if portfolio:
            portfolio.current_value = holdings_value + (portfolio.initial_capital - holdings_value)
            portfolio.updated_at = datetime.utcnow()
            await self.session.commit()
