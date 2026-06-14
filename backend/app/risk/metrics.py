"""
風險指標計算模組

波動率、VaR、CVaR、夏普比率、索提諾比率、最大回撤、Calmar 比率。
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


# ─── 波動率 ────────────────────────────────────────────────────────────────────

def calculate_volatility(
    returns: Sequence[float],
    annualize: bool = True,
    periods_per_year: int = 252,
) -> float:
    """
    計算歷史波動率（年化標準差）

    Args:
        returns: 收益率序列
        annualize: 是否年化
        periods_per_year: 年化週期（默認 252 交易日）

    Returns:
        波動率（小數，如 0.15 = 15%）
    """
    arr = np.array(returns, dtype=np.float64)
    if len(arr) < 2:
        return 0.0
    vol = np.std(arr, ddof=1)
    if annualize:
        vol *= np.sqrt(periods_per_year)
    return float(vol)


# ─── VaR ────────────────────────────────────────────────────────────────────────

def calculate_var_historical(
    returns: Sequence[float],
    confidence: float = 0.95,
    portfolio_value: float = 1.0,
) -> float:
    """
    歷史模擬法 VaR

    Args:
        returns: 收益率序列
        confidence: 信心水平（默認 95%）
        portfolio_value: 組合價值

    Returns:
        VaR（絕對損失金額）
    """
    arr = np.array(returns, dtype=np.float64)
    if len(arr) < 10:
        return portfolio_value * 0.05
    percentile = (1 - confidence) * 100
    var = np.percentile(arr, percentile)
    return float(abs(var * portfolio_value))


def calculate_var_parametric(
    returns: Sequence[float],
    confidence: float = 0.95,
    portfolio_value: float = 1.0,
) -> float:
    """
    參數法 VaR（方差-共變異數法）

    假設收益率服從正態分佈。

    Args:
        returns: 收益率序列
        confidence: 信心水平
        portfolio_value: 組合價值

    Returns:
        VaR
    """
    arr = np.array(returns, dtype=np.float64)
    if len(arr) < 2:
        return portfolio_value * 0.05
    mu = np.mean(arr)
    sigma = np.std(arr, ddof=1)
    z = stats.norm.ppf(1 - confidence)
    var = abs(mu + z * sigma)
    return float(var * portfolio_value)


def calculate_var_cornish_fisher(
    returns: Sequence[float],
    confidence: float = 0.95,
    portfolio_value: float = 1.0,
) -> float:
    """
    Cornish-Fisher 展開 VaR（考慮收益率分佈的偏度和峰度）

    Args:
        returns: 收益率序列
        confidence: 信心水平
        portfolio_value: 組合價值

    Returns:
        VaR
    """
    arr = np.array(returns, dtype=np.float64)
    if len(arr) < 30:
        return calculate_var_parametric(returns, confidence, portfolio_value)

    r = np.sort(arr)
    n = len(r)
    z = stats.norm.ppf(1 - confidence)
    s = stats.skew(arr)           # 偏度
    k = stats.kurtosis(arr)       # 峰度（超額峰度）

    # Cornish-Fisher 調整
    z_cf = (
        z
        + (z ** 2 - 1) * s / 6
        + (z ** 3 - 3 * z) * (k - 3) / 24
        - (2 * z ** 3 - 5 * z) * s ** 2 / 36
    )

    var = np.percentile(arr, stats.norm.cdf(z_cf) * 100)
    return float(abs(var * portfolio_value))


def calculate_cvar(
    returns: Sequence[float],
    confidence: float = 0.95,
    portfolio_value: float = 1.0,
) -> float:
    """
    條件 VaR（CVaR / Expected Shortfall）

    超出 VaR 的平均損失。

    Args:
        returns: 收益率序列
        confidence: 信心水平
        portfolio_value: 組合價值

    Returns:
        CVaR
    """
    arr = np.array(returns, dtype=np.float64)
    if len(arr) < 10:
        return portfolio_value * 0.075
    percentile = (1 - confidence) * 100
    var_threshold = np.percentile(arr, percentile)
    tail_losses = arr[arr <= var_threshold]
    if len(tail_losses) == 0:
        return abs(var_threshold * portfolio_value)
    cvar = abs(np.mean(tail_losses))
    return float(cvar * portfolio_value)


# ─── 比率 ──────────────────────────────────────────────────────────────────────

def calculate_sharpe_ratio(
    returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """
    夏普比率

    Args:
        returns: 收益率序列
        risk_free_rate: 年化無風險利率
        periods_per_year: 年化週期

    Returns:
        夏普比率
    """
    arr = np.array(returns, dtype=np.float64)
    if len(arr) < 2:
        return 0.0
    excess = arr - risk_free_rate / periods_per_year
    excess_mean = np.mean(excess)
    excess_std = np.std(excess, ddof=1)
    if excess_std == 0:
        return 0.0
    return float(excess_mean / excess_std * np.sqrt(periods_per_year))


def calculate_sortino_ratio(
    returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
    target_return: float = 0.0,
) -> float:
    """
    索提諾比率（只用下行偏差）

    Args:
        returns: 收益率序列
        risk_free_rate: 年化無風險利率
        periods_per_year: 年化週期
        target_return: 目標收益（默認 0）

    Returns:
        索提諾比率
    """
    arr = np.array(returns, dtype=np.float64)
    if len(arr) < 2:
        return 0.0
    excess = arr - risk_free_rate / periods_per_year
    downside = arr - target_return
    downside_std = np.std(downside[downside < 0], ddof=1) if np.any(downside < 0) else 0
    if downside_std == 0:
        return 0.0
    return float(np.mean(excess) / downside_std * np.sqrt(periods_per_year))


def calculate_max_drawdown(
    prices: Sequence[float],
) -> tuple[float, int, int]:
    """
    最大回撤

    Args:
        prices: 價格序列（由舊到新）

    Returns:
        (最大回撤率, 回撤起始索引, 回撤結束索引)
    """
    arr = np.array(prices, dtype=np.float64)
    n = len(arr)
    if n < 2:
        return 0.0, 0, 0

    peak = arr[0]
    peak_idx = 0
    max_dd = 0.0
    dd_start, dd_end = 0, 0

    for i in range(n):
        if arr[i] > peak:
            peak = arr[i]
            peak_idx = i
        dd = (peak - arr[i]) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            dd_start = peak_idx
            dd_end = i

    return float(max_dd), int(dd_start), int(dd_end)


def calculate_calmar_ratio(
    returns: Sequence[float],
    prices: Sequence[float],
    periods_per_year: int = 252,
) -> float:
    """
    Calmar 比率（年化收益 / 最大回撤）

    Args:
        returns: 收益率序列
        prices: 價格序列
        periods_per_year: 年化週期

    Returns:
        Calmar 比率
    """
    if len(returns) < 2 or len(prices) < 2:
        return 0.0
    annual_return = np.mean(returns) * periods_per_year
    mdd, _, _ = calculate_max_drawdown(prices)
    if mdd == 0:
        return 0.0
    return float(annual_return / mdd)
