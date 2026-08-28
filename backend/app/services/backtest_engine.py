"""
Backtest engine (T063) - 向量化回測 + 模擬下單(paper replay) + walk-forward + 策略比較

與既有的 BacktestService (DB/決策回放) 互補：本模組為「純函數 / 無 DB」的向量化引擎，
直接對價格序列 + 信號序列做回測，便於單元測試與前端比較視圖。

設計：
- 信號為 0/1 序列（1=全倉多頭，黃金無槓桿空單簡化）；為避免未來函數，下期才依信號建倉。
- 成本 = 換倉當日 (commission + slippage)。
- 績效指標複用 app.analysis.performance.PerformanceAnalyzer（Sharpe/Sortino/MaxDD/WinRate）。
- walk-forward：在 in-sample 訓練窗選最佳參數，在 out-of-sample 測試窗驗證，輸出樣本外績效。
- paper replay：重放歷史信號序列，對比實際走勢與 buy & hold 基準。
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from app.analysis.performance import PerformanceAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    commission_rate: float = 0.001
    slippage: float = 0.001
    position_size: float = 1.0  # 投入資金比例 (0-1)


# ── 策略信號產生器 ────────────────────────────────────────────────────────────

def ma_crossover_signals(prices: pd.Series, fast: int = 20, slow: int = 50) -> pd.Series:
    ma_fast = prices.rolling(fast, min_periods=fast // 2).mean()
    ma_slow = prices.rolling(slow, min_periods=slow // 2).mean()
    signal = (ma_fast > ma_slow).astype(float).fillna(0.0)
    return signal


def rsi_signals(prices: pd.Series, period: int = 14, buy: float = 30.0, sell: float = 70.0) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(period, min_periods=period).mean()
    rs = gain / loss.replace(0.0, np.nan)
    rsi = 100 - 100 / (1.0 + rs)
    sig = pd.Series(np.nan, index=prices.index)
    sig[rsi < buy] = 1.0
    sig[rsi > sell] = 0.0
    # 買賣之間維持前一狀態（ffill），其餘視為空手
    sig = sig.ffill().fillna(0.0)
    return sig


def macd_signals(prices: pd.Series, fast: int = 12, slow: int = 26, signal_p: int = 9) -> pd.Series:
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal_p, adjust=False).mean()
    hist = macd - macd_signal
    return (hist > 0).astype(float).fillna(0.0)


def combined_signals(
    prices: pd.Series,
    fast: int = 20,
    slow: int = 50,
    rsi_period: int = 14,
    rsi_buy: float = 30.0,
    rsi_sell: float = 70.0,
) -> pd.Series:
    ma = ma_crossover_signals(prices, fast, slow)
    rsi = rsi_signals(prices, rsi_period, rsi_buy, rsi_sell)
    macd = macd_signals(prices)
    combo = (ma + rsi + macd) >= 2.0  # 多數決
    return combo.astype(float)


# 內建策略登錄（供 compare_strategies / 路由使用）
BUILTIN_STRATEGIES: dict[str, Callable[..., pd.Series]] = {
    "ma_crossover": ma_crossover_signals,
    "rsi": rsi_signals,
    "macd": macd_signals,
    "combined": combined_signals,
}


@dataclass
class BacktestResult:
    equity_curve: list[float] = field(default_factory=list)
    final_equity: float = 0.0
    metrics: Any = None
    n_trades: int = 0
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    errors: list[str] = field(default_factory=list)


class BacktestEngine:
    """向量化回測引擎（無 DB 依賴）"""

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()

    # ── 核心：對價格 + 信號做回測 ──────────────────────────────────────────

    def run(self, prices: Sequence[float], signals: Sequence[float]) -> BacktestResult:
        cfg = self.config
        prices = pd.Series(np.asarray(prices, dtype=float)).reset_index(drop=True)
        signals = pd.Series(np.asarray(signals, dtype=float)).reset_index(drop=True)
        errors: list[str] = []

        if len(prices) < 3:
            errors.append("價格序列過短（需 >= 3 筆）")
            return BacktestResult(errors=errors)
        if len(prices) != len(signals):
            errors.append("prices 與 signals 長度必須一致")
            return BacktestResult(errors=errors)

        # 避免未來函數：本期末信號 -> 下期初建倉
        position = signals.shift(1).fillna(0.0).clip(0.0, 1.0) * cfg.position_size
        ret = prices.pct_change().fillna(0.0)
        turnover = position.diff().abs().fillna(position.abs())
        cost = turnover * (cfg.commission_rate + cfg.slippage)
        strat_ret = position * ret - cost

        equity = (1.0 + strat_ret).cumprod() * cfg.initial_capital
        equity_curve = [round(float(x), 4) for x in equity.tolist()]
        n_trades = int(round(float(turnover.sum()), 0))

        analyzer = PerformanceAnalyzer(risk_free_rate=0.02)
        metrics = analyzer.analyze(equity_curve, None, periods_per_year=252)

        return BacktestResult(
            equity_curve=equity_curve,
            final_equity=float(equity_curve[-1]) if equity_curve else cfg.initial_capital,
            metrics=metrics,
            n_trades=n_trades,
            total_return=metrics.total_return,
            annualized_return=metrics.annualized_return,
            sharpe_ratio=metrics.sharpe_ratio,
            sortino_ratio=metrics.sortino_ratio,
            max_drawdown=metrics.max_drawdown,
            win_rate=metrics.win_rate,
            errors=errors,
        )

    # ── Walk-forward（樣本外驗證）───────────────────────────────────────────

    def walk_forward(
        self,
        prices: Sequence[float],
        strategy_fn: Callable[..., pd.Series],
        param_grid: list[dict[str, Any]],
        train_days: int = 120,
        test_days: int = 30,
        step: int = 30,
    ) -> dict[str, Any]:
        prices = pd.Series(np.asarray(prices, dtype=float)).reset_index(drop=True)
        n = len(prices)
        folds: list[dict[str, Any]] = []
        i = 0
        while i + train_days + test_days <= n:
            train = prices.iloc[i : i + train_days]
            test = prices.iloc[i + train_days : i + train_days + test_days]

            # in-sample：選最佳參數（以樣內 sharpe 最大）
            best_params, best_sharpe = None, -np.inf
            for params in param_grid:
                sig = strategy_fn(train, **params)
                res = self.run(train.tolist(), sig.tolist())
                if res.errors:
                    continue
                if res.sharpe_ratio > best_sharpe:
                    best_sharpe, best_params = res.sharpe_ratio, params

            if best_params is None:
                i += step
                continue

            oos = self.run(test.tolist(), strategy_fn(test, **best_params).tolist())
            folds.append(
                {
                    "train_range": [i, i + train_days],
                    "test_range": [i + train_days, i + train_days + test_days],
                    "best_params": best_params,
                    "in_sample_sharpe": round(float(best_sharpe), 4),
                    "out_of_sample": {
                        "total_return": round(oos.total_return, 4),
                        "sharpe_ratio": round(oos.sharpe_ratio, 4),
                        "max_drawdown": round(oos.max_drawdown, 4),
                        "final_equity": round(oos.final_equity, 4),
                    },
                }
            )
            i += step

        if not folds:
            return {"folds": [], "errors": ["資料不足以產生任何 walk-forward 窗口"]}

        oos_sharpes = [f["out_of_sample"]["sharpe_ratio"] for f in folds]
        return {
            "folds": folds,
            "n_folds": len(folds),
            "avg_out_of_sample_sharpe": round(float(np.mean(oos_sharpes)), 4),
            "robust": bool(np.mean(oos_sharpes) > 0),
        }

    # ── 模擬下單（paper replay）：重放歷史信號，對比實際走勢 ────────────────

    def paper_replay(self, prices: Sequence[float], decision_signals: Sequence[float]) -> dict[str, Any]:
        strategy = self.run(prices, decision_signals)
        buy_hold = self.run(prices, [1.0] * len(list(prices)))
        return {
            "strategy": self._result_to_dict(strategy),
            "buy_and_hold": self._result_to_dict(buy_hold),
            "outperformed": bool(strategy.final_equity > buy_hold.final_equity),
        }

    # ── 策略比較視圖資料 ──────────────────────────────────────────────────────

    def compare_strategies(
        self, prices: Sequence[float], strategies: dict[str, Callable[..., pd.Series]]
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, fn in strategies.items():
            try:
                sig = fn(pd.Series(np.asarray(prices, dtype=float)))
                res = self.run(prices, sig.tolist())
                out[name] = self._result_to_dict(res)
            except Exception as exc:  # noqa: BLE001 - 單一策略失敗不影響其他
                out[name] = {"error": str(exc)}
        return out

    # ── 工具 ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _result_to_dict(r: BacktestResult) -> dict[str, Any]:
        return {
            "final_equity": round(r.final_equity, 4),
            "total_return": round(r.total_return, 4),
            "annualized_return": round(r.annualized_return, 4),
            "sharpe_ratio": round(r.sharpe_ratio, 4),
            "sortino_ratio": round(r.sortino_ratio, 4),
            "max_drawdown": round(r.max_drawdown, 4),
            "win_rate": round(r.win_rate, 4),
            "n_trades": r.n_trades,
            "equity_curve": r.equity_curve,
            "errors": r.errors,
        }
