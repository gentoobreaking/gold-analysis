"""
止損與倉位管理模組

支持五種止損策略（波動率/支撐位/VaR/追蹤止損/固定比例）和三種倉位算法（Kelly/ATR/固定風險）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)


# ─── 風險等級 ─────────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# ─── 止損策略 ─────────────────────────────────────────────────────────────────

class StopLossStrategy(str, Enum):
    VOLATILITY = "volatility"       # ATR/波動率止損
    SUPPORT = "support"            # 支撐位止損
    VAR = "var"                    # VaR 止損
    TRAILING = "trailing"          # 追蹤止損
    FIXED_PCT = "fixed_pct"        # 固定比例止損


@dataclass
class StopLossResult:
    """止損結果"""
    stop_price: float
    strategy: StopLossStrategy
    atr_or_volatility: Optional[float]
    risk_amount: float
    risk_pct: float


@dataclass
class PositionResult:
    """倉位計算結果"""
    size: float
    units: float
    risk_per_unit: float
    total_risk: float
    method: str


# ─── ATR 計算 ─────────────────────────────────────────────────────────────────

def _compute_atr(highs, lows, closes, period: int = 14) -> np.ndarray:
    """計算 ATR（True Range）"""
    n = len(highs)
    tr = np.zeros(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr[i] = max(hl, hc, lc)

    atr = np.full(n, np.nan)
    if n < period:
        return atr
    atr[period - 1] = np.mean(tr[:period])
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


# ─── 止損計算 ─────────────────────────────────────────────────────────────────

def calculate_stop_loss(
    entry_price: float,
    position_type: str,          # "long" 或 "short"
    closes: Sequence[float],
    highs: Optional[Sequence[float]] = None,
    lows: Optional[Sequence[float]] = None,
    atr_period: int = 14,
    atr_multiplier: float = 2.0,
    volatility_mult: float = 2.0,
    var_value: Optional[float] = None,
    support_level: Optional[float] = None,
    fixed_pct: float = 0.02,
    trailing_pct: float = 0.015,
) -> StopLossResult:
    """
    計算止損位（預設使用波動率止損）

    Args:
        entry_price: 進場價格
        position_type: "long" 或 "short"
        closes: 收盤價序列
        highs: 最高價序列（可選）
        lows: 最低價序列（可選）
        atr_multiplier: ATR 倍數
        volatility_mult: 波動率倍數
        var_value: VaR 值（可選）
        support_level: 支撐位（可選）
        fixed_pct: 固定止損比例（預設 2%）
        trailing_pct: 追蹤止損比例（預設 1.5%）

    Returns:
        StopLossResult
    """
    recent = np.array(closes[-atr_period * 2:], dtype=np.float64)

    if len(recent) >= atr_period and highs is not None and lows is not None:
        highs_arr = np.array(highs[-len(recent):], dtype=np.float64)
        lows_arr = np.array(lows[-len(recent):], dtype=np.float64)
        closes_arr = np.array(closes[-len(recent):], dtype=np.float64)
        atr = _compute_atr(highs_arr, lows_arr, closes_arr, atr_period)
        current_atr = float(atr[-1]) if not np.isnan(atr[-1]) else float(np.std(recent))
    else:
        current_atr = float(np.std(recent[-atr_period:]))

    # 波動率止損（ATR）
    if position_type == "long":
        atr_stop = entry_price - atr_multiplier * current_atr
    else:
        atr_stop = entry_price + atr_multiplier * current_atr

    # 固定比例止損
    if position_type == "long":
        fixed_stop = entry_price * (1 - fixed_pct)
    else:
        fixed_stop = entry_price * (1 + fixed_pct)

    # 默認用波動率止損
    final_stop = atr_stop

    if support_level is not None:
        if position_type == "long" and support_level < atr_stop:
            final_stop = support_level
        elif position_type == "short" and support_level > atr_stop:
            final_stop = support_level

    if var_value is not None:
        var_stop = entry_price * (1 - var_value / 100)
        if position_type == "long":
            final_stop = max(final_stop, var_stop)
        else:
            final_stop = min(final_stop, var_stop)

    risk_pct = abs(entry_price - final_stop) / entry_price

    return StopLossResult(
        stop_price=round(float(final_stop), 2),
        strategy=StopLossStrategy.VOLATILITY,
        atr_or_volatility=round(current_atr, 4),
        risk_amount=round(float(abs(entry_price - final_stop)), 2),
        risk_pct=round(float(risk_pct), 4),
    )


# ─── 倉位計算 ─────────────────────────────────────────────────────────────────

class PositionSizer:
    """
    倉位計算器

    支持：Kelly Criterion / ATR-based / 固定風險比例
    """

    @staticmethod
    def kelly(
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        capital: float,
        risk_fraction: float = 0.25,
    ) -> PositionResult:
        """
        Kelly Criterion 倉位

        f* = (bp - q) / b
        其中 b = avg_win / avg_loss，p = win_rate，q = 1 - p

        Args:
            win_rate: 勝率（0~1）
            avg_win: 平均獲利金額
            avg_loss: 平均虧損金額
            capital: 總資金
            risk_fraction: Kelly 分數使用比例（建議 0.25 避免過度槓桿）

        Returns:
            PositionResult
        """
        if avg_loss == 0 or win_rate >= 1.0:
            return PositionResult(
                size=0.0, units=0.0,
                risk_per_unit=0.0, total_risk=0.0,
                method="kelly",
            )

        b = avg_win / avg_loss
        q = 1 - win_rate
        kelly_fraction = (b * win_rate - q) / b
        kelly_fraction = max(0, kelly_fraction) * risk_fraction

        position_value = capital * kelly_fraction
        units = position_value / avg_win if avg_win > 0 else 0
        risk_amount = units * avg_loss

        return PositionResult(
            size=round(float(position_value), 2),
            units=round(float(units), 4),
            risk_per_unit=round(float(avg_loss), 2),
            total_risk=round(float(risk_amount), 2),
            method="kelly",
        )

    @staticmethod
    def atr_based(
        entry_price: float,
        atr: float,
        capital: float,
        risk_pct: float = 0.01,
    ) -> PositionResult:
        """
        ATR 倉位演算法

        倉位 = 風險金額 / (ATR × 倍數)
        風險金額 = 總資金 × 風險比例

        Args:
            entry_price: 進場價格
            atr: ATR 值
            capital: 總資金
            risk_pct: 每筆風險比例（預設 1%）

        Returns:
            PositionResult
        """
        risk_amount = capital * risk_pct
        risk_per_unit = atr * 2  # 止損距離
        if risk_per_unit == 0:
            return PositionResult(
                size=0.0, units=0.0,
                risk_per_unit=0.0, total_risk=0.0,
                method="atr",
            )

        units = risk_amount / risk_per_unit
        position_value = units * entry_price

        return PositionResult(
            size=round(float(position_value), 2),
            units=round(float(units), 4),
            risk_per_unit=round(float(risk_per_unit), 4),
            total_risk=round(float(risk_amount), 2),
            method="atr",
        )

    @staticmethod
    def fixed_risk(
        entry_price: float,
        stop_price: float,
        capital: float,
        risk_pct: float = 0.02,
    ) -> PositionResult:
        """
        固定風險比例倉位

        Args:
            entry_price: 進場價格
            stop_price: 止損價格
            capital: 總資金
            risk_pct: 每筆風險比例（預設 2%）

        Returns:
            PositionResult
        """
        risk_amount = capital * risk_pct
        risk_per_unit = abs(entry_price - stop_price)
        if risk_per_unit == 0:
            return PositionResult(
                size=0.0, units=0.0,
                risk_per_unit=0.0, total_risk=0.0,
                method="fixed_risk",
            )

        units = risk_amount / risk_per_unit
        position_value = units * entry_price

        return PositionResult(
            size=round(float(position_value), 2),
            units=round(float(units), 4),
            risk_per_unit=round(float(risk_per_unit), 4),
            total_risk=round(float(risk_amount), 2),
            method="fixed_risk",
        )


def calculate_position_size(**kwargs) -> PositionResult:
    """快捷函數：自動調用對應演算法"""
    method = kwargs.get("method", "atr")
    if method == "kelly":
        return PositionSizer.kelly(**kwargs)
    elif method == "fixed_risk":
        return PositionSizer.fixed_risk(**kwargs)
    else:
        return PositionSizer.atr_based(**kwargs)


# ─── 風險評估 ─────────────────────────────────────────────────────────────────

def assess_risk_level(
    var_pct: float,
    volatility: float,
    drawdown: float,
) -> RiskLevel:
    """
    給定 VaR、波動率、最大回撤，評估風險等級

    Args:
        var_pct: VaR 百分比（如 0.05 = 5%）
        volatility: 年化波動率（小數）
        drawdown: 最大回撤（小數）

    Returns:
        風險等級
    """
    score = var_pct * 100 * 0.4 + volatility * 100 * 0.3 + drawdown * 100 * 0.3
    if score >= 8:
        return RiskLevel.VERY_HIGH
    elif score >= 5:
        return RiskLevel.HIGH
    elif score >= 3:
        return RiskLevel.MEDIUM
    elif score >= 1.5:
        return RiskLevel.LOW
    else:
        return RiskLevel.VERY_LOW
