"""
Backtest Service - 決策回測系統
實現歷史決策回放、績效分析
"""
import logging
import json
from typing import Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decision import Decision, DecisionType
from app.models.portfolio import Portfolio
from app.models.portfolio_holding import PortfolioHolding
from app.analysis.performance import PerformanceAnalyzer, PerformanceMetrics

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """回測交易記錄"""
    entry_time: datetime
    exit_time: Optional[datetime]
    direction: str          # buy / sell
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    pnl: Optional[float]   # 僅平倉後有值
    pnl_pct: Optional[float]
    decision_id: int
    status: str = "open"   # open / closed


@dataclass
class BacktestResult:
    """回測結果"""
    portfolio_id: int
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    metrics: PerformanceMetrics
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class BacktestService:
    """回測服務"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── 歷史數據獲取 ─────────────────────────────────────────────────────────

    async def get_decisions(
        self,
        portfolio_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        decision_types: Optional[list[DecisionType]] = None,
    ) -> list[Decision]:
        """
        獲取歷史決策記錄

        Args:
            portfolio_id: 組合ID
            start_date: 起始日期（可選）
            end_date: 結束日期（可選）
            decision_types: 決策類型過濾（可選）

        Returns:
            Decision 列表
        """
        stmt = select(Decision).where(Decision.portfolio_id == portfolio_id)
        if start_date:
            stmt = stmt.where(Decision.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Decision.created_at <= end_date)
        if decision_types:
            stmt = stmt.where(Decision.decision_type.in_(decision_types))
        stmt = stmt.order_by(Decision.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ── 模擬市場數據 ─────────────────────────────────────────────────────────

    async def _fetch_market_prices(
        self,
        asset: str,
        start_date: datetime,
        end_date: datetime,
        price_field: str = "close",
    ) -> dict[str, float]:
        """
        從 InfluxDB 獲取歷史市場價格（存根）

        實際實現需查詢 InfluxDB。當前返回模擬數據。
        """
        # TODO: 替換為真實 InfluxDB 查詢
        # client = get_influx_client()
        # query_api = client.query_api()
        # query = f'''
        # from(bucket: "{settings.influxdb_bucket}")
        #   |> range(start: {start_date.isoformat()}, stop: {end_date.isoformat()})
        #   |> filter(fn: (r) => r["asset"] == "{asset}")
        #   |> last()
        # '''
        # result = query_api.query(query=query)
        logger.info(f"[STUB] Fetching market prices for {asset} from {start_date} to {end_date}")
        return {}  # 空字典表示無歷史數據

    # ── 核心回測引擎 ─────────────────────────────────────────────────────────

    async def run_backtest(
        self,
        portfolio_id: int,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
        asset: str = "GOLD",
        position_size: float = 0.1,       # 每次投入資金比例
        stop_loss_pct: float = 5.0,       # 止損 %
        take_profit_pct: float = 10.0,    # 止盈 %
    ) -> BacktestResult:
        """
        執行回測

        Args:
            portfolio_id: 組合ID（用於取決策）
            start_date: 回測起始日期
            end_date: 回測結束日期
            initial_capital: 初始資金
            asset: 交易資產
            position_size: 每次投入資金比例（0.0-1.0）
            stop_loss_pct: 止損閾值 %
            take_profit_pct: 止盈閾值 %

        Returns:
            BacktestResult
        """
        logger.info(
            f"Starting backtest: portfolio={portfolio_id}, "
            f"{start_date.date()} -> {end_date.date()}, capital={initial_capital}"
        )

        errors: list[str] = []
        cash = initial_capital
        equity_curve: list[float] = [cash]
        trades: list[BacktestTrade] = []

        # 取得歷史決策
        decisions = await self.get_decisions(
            portfolio_id, start_date, end_date,
            decision_types=[DecisionType.BUY, DecisionType.SELL, DecisionType.HOLD]
        )

        if not decisions:
            logger.warning("No decisions found for backtest period")
            errors.append("No decisions found for the specified period")

        # 取得模擬市場價格（存根）
        market_prices: dict[str, float] = {}
        current_price = 1800.0  # 預設起始價
        entry_price = 0.0
        entry_time: Optional[datetime] = None
        quantity = 0.0
        position_open = False

        current = start_date
        day_count = 0

        # 模擬日線遍歷（每個決策一次，或按日）
        for decision in decisions:
            # 模擬價格變動（隨機漫步）
            current_price = max(100, current_price * (1 + (hash(str(decision.id)) % 100 - 50) / 1000))
            market_prices[decision.asset] = current_price

            # 根據決策執行交易
            if decision.decision_type == DecisionType.BUY and not position_open:
                if cash >= current_price * 1:
                    qty = (cash * position_size) / current_price
                    cost = qty * current_price
                    cash -= cost
                    quantity = qty
                    entry_price = current_price
                    entry_time = decision.created_at
                    position_open = True

                    trades.append(BacktestTrade(
                        entry_time=entry_time,
                        exit_time=None,
                        direction="buy",
                        entry_price=entry_price,
                        exit_price=None,
                        quantity=quantity,
                        pnl=None,
                        pnl_pct=None,
                        decision_id=decision.id,
                        status="open",
                    ))

            elif decision.decision_type == DecisionType.SELL and position_open:
                exit_price = current_price
                pnl = (exit_price - entry_price) * quantity
                pnl_pct = (exit_price - entry_price) / entry_price * 100

                cash += quantity * exit_price
                position_open = False

                if trades and trades[-1].status == "open":
                    trades[-1].exit_time = decision.created_at
                    trades[-1].exit_price = exit_price
                    trades[-1].pnl = round(pnl, 2)
                    trades[-1].pnl_pct = round(pnl_pct, 2)
                    trades[-1].status = "closed"

                logger.info(
                    f"Trade closed: entry={entry_price:.2f}, exit={exit_price:.2f}, "
                    f"pnl={pnl:.2f} ({pnl_pct:.2f}%)"
                )

            # 止損/止盈檢查
            if position_open:
                pnl_since_entry = (current_price - entry_price) / entry_price * 100
                if pnl_since_entry <= -stop_loss_pct or pnl_since_entry >= take_profit_pct:
                    exit_price = current_price
                    pnl = (exit_price - entry_price) * quantity
                    cash += quantity * exit_price
                    position_open = False

                    if trades and trades[-1].status == "open":
                        trades[-1].exit_time = decision.created_at
                        trades[-1].exit_price = exit_price
                        trades[-1].pnl = round(pnl, 2)
                        trades[-1].pnl_pct = round(pnl_since_entry, 2)
                        trades[-1].status = "closed"

            # 更新權益曲線
            holding_value = quantity * current_price if position_open else 0.0
            equity_curve.append(round(cash + holding_value, 2))
            day_count += 1
            current = decision.created_at

        # 平倉未了結頭寸
        if position_open:
            trades[-1].exit_time = end_date
            trades[-1].exit_price = current_price
            trades[-1].pnl = round((current_price - entry_price) * quantity, 2)
            trades[-1].pnl_pct = round((current_price - entry_price) / entry_price * 100, 2)
            trades[-1].status = "closed"
            cash += quantity * current_price

        final_capital = cash
        equity_curve[-1] = round(final_capital, 2)

        # 績效分析
        trade_log = [
            {
                "entry_price": t.entry_price,
                "exit_price": t.exit_price or 0,
                "quantity": t.quantity,
                "direction": t.direction,
                "pnl": t.pnl or 0,
            }
            for t in trades if t.status == "closed"
        ]

        analyzer = PerformanceAnalyzer(risk_free_rate=0.02)
        metrics = analyzer.analyze(equity_curve, trade_log)

        logger.info(
            f"Backtest complete: initial={initial_capital}, final={final_capital:.2f}, "
            f"return={metrics.total_return:.2f}%, trades={len(trade_log)}"
        )

        return BacktestResult(
            portfolio_id=portfolio_id,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_capital=round(final_capital, 2),
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            errors=errors,
        )

    # ── 決策回放 ─────────────────────────────────────────────────────────────

    async def replay_decisions(
        self,
        portfolio_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict]:
        """
        回放歷史決策（展示用，不計算績效）

        Returns:
            決策回放列表，每項含決策內容與當時市場背景
        """
        decisions = await self.get_decisions(portfolio_id, start_date, end_date)
        replay = []

        for d in decisions:
            replay.append({
                "id": d.id,
                "created_at": d.created_at.isoformat(),
                "type": d.decision_type.value,
                "asset": d.asset,
                "signal_strength": d.signal_strength,
                "confidence": d.confidence,
                "price_target": d.price_target,
                "stop_loss": d.stop_loss,
                "reason_zh": d.reason_zh,
                "reason_en": d.reason_en,
                "is_executed": d.is_executed,
                "executed_at": d.executed_at.isoformat() if d.executed_at else None,
            })

        return replay

    # ── 對比分析 ─────────────────────────────────────────────────────────────

    async def compare_strategies(
        self,
        portfolio_id: int,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float,
    ) -> dict:
        """
        多策略對比回測

        對比：AI 分析、純技術面、純基本面、持倉不動
        """
        strategies = {
            "ai_analysis": [DecisionType.AI_ANALYSIS],
            "technical": [DecisionType.TECHNICAL],
            "fundamental": [DecisionType.FUNDAMENTAL],
            "buy_and_hold": None,  # 特殊處理
        }

        results = {}
        for name, types in strategies.items():
            if name == "buy_and_hold":
                # 簡單 buy & hold
                prices = await self._fetch_market_prices("GOLD", start_date, end_date)
                start_p = 1800.0
                end_p = 1900.0
                ret = (end_p - start_p) / start_p * 100
                results[name] = {
                    "return_pct": round(ret, 2),
                    "trades": 0,
                    "note": "Buy and hold benchmark",
                }
            else:
                # 創建虛擬組合進行回測
                try:
                    result = await self.run_backtest(
                        portfolio_id=portfolio_id,
                        start_date=start_date,
                        end_date=end_date,
                        initial_capital=initial_capital,
                    )
                    results[name] = {
                        "return_pct": result.metrics.total_return,
                        "annualized": result.metrics.annualized_return,
                        "win_rate": result.metrics.win_rate,
                        "max_drawdown": result.metrics.max_drawdown,
                        "sharpe": result.metrics.sharpe_ratio,
                        "trades": result.metrics.total_trades,
                    }
                except Exception as e:
                    results[name] = {"error": str(e)}

        return results

    def to_dict(self, result: BacktestResult) -> dict:
        """序列化回測結果"""
        return {
            "portfolio_id": result.portfolio_id,
            "start_date": result.start_date.isoformat(),
            "end_date": result.end_date.isoformat(),
            "initial_capital": result.initial_capital,
            "final_capital": result.final_capital,
            "metrics": {
                "total_return": result.metrics.total_return,
                "annualized_return": result.metrics.annualized_return,
                "total_trades": result.metrics.total_trades,
                "win_rate": result.metrics.win_rate,
                "profit_factor": result.metrics.profit_factor,
                "max_drawdown": result.metrics.max_drawdown,
                "sharpe_ratio": result.metrics.sharpe_ratio,
                "sortino_ratio": result.metrics.sortino_ratio,
            },
            "equity_curve": result.equity_curve,
            "trades": [
                {
                    "entry_time": t.entry_time.isoformat(),
                    "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                    "direction": t.direction,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "quantity": t.quantity,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "status": t.status,
                }
                for t in result.trades
            ],
            "errors": result.errors,
        }
