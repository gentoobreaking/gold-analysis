"""
Performance Analysis Module - 績效指標計算
計算收益率、勝率、最大回撤、夏普比率等
"""
import logging
from typing import Optional
from dataclasses import dataclass, field
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """績效指標 dataclass"""
    total_return: float          # 總收益率 %
    annualized_return: float     # 年化收益率 %
    total_trades: int            # 總交易次數
    winning_trades: int          # 盈利交易次數
    losing_trades: int           # 虧損交易次數
    win_rate: float              # 勝率 %
    avg_win: float               # 平均盈利金額
    avg_loss: float              # 平均虧損金額
    profit_factor: float         # 盈虧比
    max_drawdown: float          # 最大回撤 %
    max_drawdown_duration: int   # 最大回撤持續天數
    sharpe_ratio: float          # 夏普比率
    calmar_ratio: float          # 卡爾瑪比率
    sortino_ratio: float         # 索提諾比率
    total_return_pct: float      # 總收益 %
    running_balance: float        # 期末餘額

    # 可選明細
    equity_curve: list[float] = field(default_factory=list)
    drawdown_curve: list[float] = field(default_factory=list)
    trade_log: list[dict] = field(default_factory=list)


class PerformanceAnalyzer:
    """績效分析器"""

    def __init__(self, risk_free_rate: float = 0.0):
        """
        Args:
            risk_free_rate: 無風險利率（年化，預設 0%）
        """
        self.risk_free_rate = risk_free_rate

    def analyze(
        self,
        equity_curve: list[float],
        trade_log: Optional[list[dict]] = None,
        periods_per_year: int = 252,
    ) -> PerformanceMetrics:
        """
        根據權益曲線計算完整績效指標

        Args:
            equity_curve: 每日/每期帳戶餘額列表
            trade_log: 交易記錄列表（可選），每條格式:
                { "entry_price": float, "exit_price": float,
                  "quantity": float, "direction": str, "pnl": float }
            periods_per_year: 每年交易日數（預設 252）
        """
        if not equity_curve or len(equity_curve) < 2:
            logger.warning("Insufficient equity curve data")
            return self._empty_metrics()

        equity = np.array(equity_curve)
        initial = equity[0]

        # 基本指標
        total_return = float((equity[-1] - initial) / initial * 100) if initial > 0 else 0.0
        n_periods = len(equity)
        annualized = self._annualized_return(equity, n_periods, periods_per_year)

        # 回撤
        max_dd, dd_duration = self._max_drawdown(equity)

        # 交易統計
        trades, wins, losses, avg_w, avg_l, pf = self._trade_stats(trade_log or [])
        win_rate = (wins / trades * 100) if trades > 0 else 0.0

        # 風險調整指標
        returns_series = np.diff(equity) / equity[:-1]
        returns_series = np.nan_to_num(returns_series, nan=0.0)
        sharpe = self._sharpe_ratio(returns_series, periods_per_year)
        sortino = self._sortino_ratio(returns_series, periods_per_year)
        calmar = abs(annualized / max_dd) if max_dd != 0 else 0.0

        return PerformanceMetrics(
            total_return=round(total_return, 2),
            annualized_return=round(annualized, 2),
            total_trades=trades,
            winning_trades=wins,
            losing_trades=losses,
            win_rate=round(win_rate, 2),
            avg_win=round(avg_w, 2),
            avg_loss=round(avg_l, 2),
            profit_factor=round(pf, 2),
            max_drawdown=round(max_dd, 2),
            max_drawdown_duration=dd_duration,
            sharpe_ratio=round(sharpe, 3),
            calmar_ratio=round(calmar, 3),
            sortino_ratio=round(sortino, 3),
            total_return_pct=round(total_return, 2),
            running_balance=round(equity[-1], 2),
            equity_curve=[round(float(x), 2) for x in equity.tolist()],
            drawdown_curve=self._drawdown_curve(equity),
            trade_log=trade_log or [],
        )

    def _annualized_return(
        self,
        equity: np.ndarray,
        n_periods: int,
        periods_per_year: int,
    ) -> float:
        """計算年化收益率"""
        if equity[0] <= 0 or n_periods < 2:
            return 0.0
        total = equity[-1] / equity[0]
        years = n_periods / periods_per_year
        return (total ** (1 / years) - 1) * 100 if years > 0 else 0.0

    def _max_drawdown(self, equity: np.ndarray) -> tuple[float, int]:
        """計算最大回撤和持續天數"""
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak * 100
        max_dd = float(np.min(drawdown))  # 負值

        # 最大回撤持續天數
        dd_curve = self._drawdown_curve(equity)
        dd_array = np.array(dd_curve)
        current_dd = 0.0
        max_duration = 0
        current_duration = 0
        in_drawdown = False

        for dd in dd_array:
            if dd < -0.1:  # 回撤閾值
                in_drawdown = True
                current_duration += 1
                current_dd = min(current_dd, dd)
                if current_duration > max_duration:
                    max_duration = current_duration
            else:
                in_drawdown = False
                current_duration = 0

        return abs(max_dd), max_duration

    def _drawdown_curve(self, equity: np.ndarray) -> list[float]:
        """計算回撤曲線（%）"""
        peak = np.maximum.accumulate(equity)
        dd = (equity - peak) / peak * 100
        return [round(float(x), 4) for x in dd.tolist()]

    def _trade_stats(
        self, trade_log: list[dict]
    ) -> tuple[int, int, int, float, float, float]:
        """計算交易統計"""
        if not trade_log:
            return 0, 0, 0, 0.0, 0.0, 0.0

        trades = len(trade_log)
        wins = sum(1 for t in trade_log if t.get("pnl", 0) > 0)
        losses = sum(1 for t in trade_log if t.get("pnl", 0) < 0)

        win_amounts = [t["pnl"] for t in trade_log if t.get("pnl", 0) > 0]
        loss_amounts = [abs(t["pnl"]) for t in trade_log if t.get("pnl", 0) < 0]

        avg_win = float(np.mean(win_amounts)) if win_amounts else 0.0
        avg_loss = float(np.mean(loss_amounts)) if loss_amounts else 0.0

        total_wins = sum(win_amounts)
        total_losses = sum(loss_amounts)
        pf = total_wins / total_losses if total_losses > 0 else 0.0

        return trades, wins, losses, avg_win, avg_loss, pf

    def _sharpe_ratio(
        self, returns: np.ndarray, periods_per_year: int
    ) -> float:
        """計算夏普比率"""
        if len(returns) < 2:
            return 0.0
        excess = returns - (self.risk_free_rate / periods_per_year)
        std = np.std(excess)
        if std == 0:
            return 0.0
        return float(np.mean(excess) / std * np.sqrt(periods_per_year))

    def _sortino_ratio(
        self, returns: np.ndarray, periods_per_year: int
    ) -> float:
        """計算索提諾比率（只考慮下行偏差）"""
        if len(returns) < 2:
            return 0.0
        excess = returns - (self.risk_free_rate / periods_per_year)
        downside = excess[excess < 0]
        if len(downside) == 0 or np.std(downside) == 0:
            return 0.0
        return float(np.mean(excess) / np.std(downside) * np.sqrt(periods_per_year))

    def _empty_metrics(self) -> PerformanceMetrics:
        """返回空指標"""
        return PerformanceMetrics(
            total_return=0.0, annualized_return=0.0,
            total_trades=0, winning_trades=0, losing_trades=0,
            win_rate=0.0, avg_win=0.0, avg_loss=0.0, profit_factor=0.0,
            max_drawdown=0.0, max_drawdown_duration=0,
            sharpe_ratio=0.0, calmar_ratio=0.0, sortino_ratio=0.0,
            total_return_pct=0.0, running_balance=0.0,
        )

    def summary_text(self, metrics: PerformanceMetrics) -> str:
        """生成文字摘要"""
        lines = [
            "📊 回測績效摘要",
            "=" * 40,
            f"總收益率:    {metrics.total_return:+.2f}%",
            f"年化收益率:  {metrics.annualized_return:+.2f}%",
            f"總交易次數:  {metrics.total_trades}",
            f"勝率:        {metrics.win_rate:.1f}%",
            f"盈虧比:      {metrics.profit_factor:.2f}",
            f"最大回撤:    {metrics.max_drawdown:.2f}%",
            f"夏普比率:    {metrics.sharpe_ratio:.3f}",
            f"索提諾比率:  {metrics.sortino_ratio:.3f}",
            f"期末餘額:    {metrics.running_balance:.2f}",
        ]
        return "\n".join(lines)
