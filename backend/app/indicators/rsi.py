"""
RSI 模組 (Relative Strength Index)

純 Python 實現 RSI 計算、超買超賣判斷、背離檢測。

使用範例：
    rsi_vals = compute_rsi(closes, period=14)
    signals  = generate_rsi_signals(rsi_vals)
    divs     = detect_rsi_divergence(closes, rsi_vals)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)


# ─── 常量 ─────────────────────────────────────────────────────────────────────

DEFAULT_PERIOD = 14
OVERBOUGHT = 70.0
OVERSOLD = 30.0


# ─── 數據類別 ─────────────────────────────────────────────────────────────────

class RSISignalType(str, Enum):
    """RSI 信號類型"""
    OVERBOUGHT = "overbought"   # 超買
    OVERSOLD = "oversold"       # 超賣
    NEUTRAL = "neutral"         # 中性


@dataclass
class RSIDivergence:
    """RSI 背離"""
    div_type: str               # "bearish" 或 "bullish"
    start_idx: int              # 背離起始索引
    end_idx: int                # 背離結束索引
    price_delta: float          # 價格變化幅度
    rsi_delta: float            # RSI 變化幅度


@dataclass
class RSISignal:
    """RSI 信號"""
    index: int
    signal_type: RSISignalType
    value: float


# ─── RSI 計算 ─────────────────────────────────────────────────────────────────

class RSI:
    """
    相對強弱指數 (Relative Strength Index)

    公式：
        RS = avg_gain / avg_loss
        RSI = 100 - (100 / (1 + RS))
    """

    def __init__(self, period: int = DEFAULT_PERIOD):
        if period < 2:
            raise ValueError("RSI period 必須 >= 2")
        self.period = period

    def compute(self, data: Sequence[float]) -> np.ndarray:
        """
        計算 RSI 序列

        Args:
            data: 價格序列（由舊到新）

        Returns:
            RSI 序列（長度與 data 相同，前 period 個為 NaN）
        """
        arr = np.array(data, dtype=np.float64)
        n = len(arr)
        result = np.full(n, np.nan, dtype=np.float64)

        if n <= self.period:
            return result

        # 計算價格變動
        deltas = np.diff(arr)

        # 分離漲跌
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # 初始均值（簡單平均）
        avg_gain = np.mean(gains[:self.period])
        avg_loss = np.mean(losses[:self.period])

        if avg_loss == 0:
            result[self.period] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[self.period] = 100.0 - (100.0 / (1.0 + rs))

        # 遞推計算（Wilder 平滑）
        for i in range(self.period + 1, n):
            avg_gain = (avg_gain * (self.period - 1) + gains[i - 1]) / self.period
            avg_loss = (avg_loss * (self.period - 1) + losses[i - 1]) / self.period

            if avg_loss == 0:
                result[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                result[i] = 100.0 - (100.0 / (1.0 + rs))

        return result


def compute_rsi(data: Sequence[float], period: int = DEFAULT_PERIOD) -> np.ndarray:
    """快捷函數：計算 RSI"""
    return RSI(period).compute(data)


# ─── 超買超賣信號 ─────────────────────────────────────────────────────────────

def generate_rsi_signals(
    rsi_values: Sequence[float],
    overbought: float = OVERBOUGHT,
    oversold: float = OVERSOLD,
) -> List[RSISignal]:
    """
    生成 RSI 超買超賣信號

    Args:
        rsi_values: RSI 序列
        overbought: 超買閾值（默認 70）
        oversold: 超賣閾值（默認 30）

    Returns:
        信號列表
    """
    signals = []
    for i, val in enumerate(rsi_values):
        if np.isnan(val):
            continue
        if val >= overbought:
            signals.append(RSISignal(index=i, signal_type=RSISignalType.OVERBOUGHT, value=float(val)))
        elif val <= oversold:
            signals.append(RSISignal(index=i, signal_type=RSISignalType.OVERSOLD, value=float(val)))
    return signals


# ─── 背離檢測 ─────────────────────────────────────────────────────────────────

def detect_rsi_divergence(
    prices: Sequence[float],
    rsi_values: Sequence[float],
    lookback: int = 20,
    min_swing: float = 1.0,
) -> List[RSIDivergence]:
    """
    檢測 RSI 背離

    看跌背離（頂背離）：價格創新高但 RSI 未創新高
    看漲背離（底背離）：價格創新低但 RSI 未創新低

    Args:
        prices: 價格序列
        rsi_values: RSI 序列（與 prices 等長）
        lookback: 回顧窗口
        min_swing: 最小擺動幅度（百分比）

    Returns:
        背離列表
    """
    prices = np.array(prices, dtype=np.float64)
    rsi = np.array(rsi_values, dtype=np.float64)
    n = len(prices)
    if n < lookback + 5:
        return []

    divergences = []

    # 找局部極值
    def find_local_maxima(arr, start, end):
        peaks = []
        for i in range(start + 1, end - 1):
            if arr[i] > arr[i - 1] and arr[i] > arr[i + 1] and not np.isnan(arr[i]):
                peaks.append(i)
        return peaks

    def find_local_minima(arr, start, end):
        troughs = []
        for i in range(start + 1, end - 1):
            if arr[i] < arr[i - 1] and arr[i] < arr[i + 1] and not np.isnan(arr[i]):
                troughs.append(i)
        return troughs

    # 看跌背離（頂背離）
    price_peaks = find_local_maxima(prices, max(0, n - lookback), n)
    rsi_peaks = find_local_maxima(rsi, max(0, n - lookback), n)

    if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
        # 最近兩個價格高點
        p1, p2 = price_peaks[-2], price_peaks[-1]
        if prices[p2] > prices[p1] * (1 + min_swing / 100):
            # 價格新高，找對應的 RSI 高點
            for r1, r2 in zip(rsi_peaks[-2:], rsi_peaks[-1:]):
                if r2 > r1 and rsi[r2] <= rsi[r1]:
                    divergences.append(RSIDivergence(
                        div_type="bearish",
                        start_idx=int(r1),
                        end_idx=int(r2),
                        price_delta=float(prices[p2] - prices[p1]),
                        rsi_delta=float(rsi[r2] - rsi[r1]),
                    ))
                    break

    # 看漲背離（底背離）
    price_troughs = find_local_minima(prices, max(0, n - lookback), n)
    rsi_troughs = find_local_minima(rsi, max(0, n - lookback), n)

    if len(price_troughs) >= 2 and len(rsi_troughs) >= 2:
        p1, p2 = price_troughs[-2], price_troughs[-1]
        if prices[p2] < prices[p1] * (1 - min_swing / 100):
            for r1, r2 in zip(rsi_troughs[-2:], rsi_troughs[-1:]):
                if r2 > r1 and rsi[r2] >= rsi[r1]:
                    divergences.append(RSIDivergence(
                        div_type="bullish",
                        start_idx=int(r1),
                        end_idx=int(r2),
                        price_delta=float(prices[p2] - prices[p1]),
                        rsi_delta=float(rsi[r2] - rsi[r1]),
                    ))
                    break

    return divergences
