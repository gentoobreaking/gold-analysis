"""
T063 - 回測引擎單元測試（向量化 / walk-forward / paper replay / 策略比較）
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from app.services.backtest_engine import (
    BUILTIN_STRATEGIES,
    BacktestEngine,
    combined_signals,
    ma_crossover_signals,
    macd_signals,
    rsi_signals,
)


def _make_prices(n: int = 300, seed: int = 7, trend: float = 0.0005) -> list[float]:
    rng = np.random.default_rng(seed)
    steps = rng.normal(loc=trend, scale=0.01, size=n)
    return list(1800.0 * np.exp(np.cumsum(steps)))


def test_signal_generators_return_binary_series():
    prices = pd.Series(_make_prices(200))
    for fn in (ma_crossover_signals, rsi_signals, macd_signals, combined_signals):
        sig = fn(prices)
        assert len(sig) == 200
        assert set(np.unique(np.asarray(sig))).issubset({0.0, 1.0})


def test_run_produces_finite_metrics_and_equity_curve():
    s = pd.Series(_make_prices(300))
    engine = BacktestEngine()
    res = engine.run(s.tolist(), ma_crossover_signals(s).tolist())
    assert not res.errors
    assert len(res.equity_curve) == len(s)
    assert np.isfinite(res.final_equity)
    assert np.isfinite(res.sharpe_ratio)
    assert np.isfinite(res.max_drawdown)
    # PerformanceAnalyzer.max_drawdown 為正值幅度（0~100）
    assert 0.0 <= res.max_drawdown <= 100.0
    # 績效指標數值合理（非未定義）
    assert np.isfinite(res.total_return)
    assert res.n_trades >= 0


def test_run_rejects_mismatched_lengths():
    engine = BacktestEngine()
    res = engine.run([1.0, 2.0, 3.0], [1.0, 0.0])
    assert res.errors  # 長度不符應記錄錯誤而非拋例外


def test_run_handles_short_series_gracefully():
    engine = BacktestEngine()
    res = engine.run([1.0, 2.0], [0.0, 1.0])
    assert res.errors  # 過短應記錄錯誤


def test_walk_forward_returns_out_of_sample_folds():
    prices = _make_prices(400, seed=11)
    engine = BacktestEngine()
    grid = [{"fast": 10, "slow": 30}, {"fast": 20, "slow": 50}, {"fast": 30, "slow": 90}]
    result = engine.walk_forward(
        prices, ma_crossover_signals, grid, train_days=120, test_days=30, step=30
    )
    assert "folds" in result
    assert result["n_folds"] >= 1
    fold = result["folds"][0]
    assert "best_params" in fold
    assert "out_of_sample" in fold
    assert "sharpe_ratio" in fold["out_of_sample"]
    # 樣本外 Sharpe 應為有限數
    assert np.isfinite(fold["out_of_sample"]["sharpe_ratio"])
    assert np.isfinite(result["avg_out_of_sample_sharpe"])


def test_paper_replay_compares_against_buy_and_hold():
    prices = _make_prices(250, seed=3)
    engine = BacktestEngine()
    # 一個簡單的「突破追漲」歷史信號
    signals = [1.0 if p > prices[0] else 0.0 for p in prices]
    result = engine.paper_replay(prices, signals)
    assert "strategy" in result and "buy_and_hold" in result
    assert isinstance(result["outperformed"], bool)
    assert np.isfinite(result["strategy"]["final_equity"])
    assert np.isfinite(result["buy_and_hold"]["final_equity"])


def test_compare_strategies_runs_all_builtins():
    prices = _make_prices(300, seed=5)
    engine = BacktestEngine()
    out = engine.compare_strategies(prices, BUILTIN_STRATEGIES)
    assert set(out.keys()) == set(BUILTIN_STRATEGIES.keys())
    for name, item in out.items():
        assert "error" not in item, f"{name} 回測失敗: {item}"
        assert np.isfinite(item["sharpe_ratio"])
        assert np.isfinite(item["max_drawdown"])
        assert len(item["equity_curve"]) == len(prices)
