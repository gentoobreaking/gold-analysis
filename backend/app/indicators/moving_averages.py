"""
移動平均線模組 (Moving Averages)

純 Python 實現 SMA / EMA / WMA，以及均線交叉檢測。

使用範例：
    sma_vals = compute_sma(closes, period=20)
    ema_vals = compute_ema(closes, period=12)
    cross   = detect_crossover(short_emas, long_emas)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ─── 數據類別 ─────────────────────────────────────────────────────────────────

class MACrossType(str, Enum):
    """均線交叉類型"""
    GOLDEN_CROSS = "golden_cross"    # 短均線上穿長均線（看多）
    DEATH_CROSS = "death_cross"      # 短均線下穿長均線（看空）
    NONE = "none"                    # 無交叉


@dataclass
class MovingAverageCrossover:
    """均線交叉事件"""
    cross_type: MACrossType
    index: int                       # 發生交叉的索引位置
    short_value: float               # 交叉時短均線值
    long_value: float                # 交叉時長均線值


# ─── SMA ────────────────────────────────────────────────────────────────────────

class SMA:
    """
    簡單移動平均線 (Simple Moving Average)

    公式：SMA(n) = sum(close[-n:]) / n
    """

    def __init__(self, period: int = 20):
        if period < 2:
            raise ValueError("SMA period 必須 >= 2")
        self.period = period

    def compute(self, data: Sequence[float]) -> np.ndarray:
        """
        計算 SMA 序列

        Args:
            data: 價格序列（由舊到新）

        Returns:
            SMA 序列（長度與 data 相同，前 period-1 個為 NaN）
        """
        arr = np.array(data, dtype=np.float64)
        n = len(arr)
        result = np.full(n, np.nan, dtype=np.float64)
        if n < self.period:
            return result

        # 滑動窗口求均值
        cumsum = np.cumsum(arr)
        cumsum = np.insert(cumsum, 0, 0.0)
        window_sums = cumsum[self.period:] - cumsum[:n - self.period + 1]
        result[self.period - 1:] = window_sums / self.period
        return result


def compute_sma(data: Sequence[float], period: int = 20) -> np.ndarray:
    """快捷函數：計算 SMA"""
    return SMA(period).compute(data)


# ─── EMA ────────────────────────────────────────────────────────────────────────

class EMA:
    """
    指數移動平均線 (Exponential Moving Average)

    公式：
        EMA[0] = SMA(period)  （首個值用 SMA 初始化）
        EMA[i] = α * price[i] + (1 - α) * EMA[i-1]
        α = 2 / (period + 1)
    """

    def __init__(self, period: int = 12):
        if period < 2:
            raise ValueError("EMA period 必須 >= 2")
        self.period = period
        self.alpha = 2.0 / (period + 1)

    def compute(self, data: Sequence[float]) -> np.ndarray:
        """
        計算 EMA 序列

        Args:
            data: 價格序列（由舊到新）

        Returns:
            EMA 序列（長度與 data 相同，前 period-1 個為 NaN）
        """
        arr = np.array(data, dtype=np.float64)
        n = len(arr)
        result = np.full(n, np.nan, dtype=np.float64)
        if n < self.period:
            return result

        # 第一個 EMA 值用 SMA 初始化
        result[self.period - 1] = np.mean(arr[:self.period])

        # 遞推計算
        for i in range(self.period, n):
            result[i] = self.alpha * arr[i] + (1 - self.alpha) * result[i - 1]

        return result


def compute_ema(data: Sequence[float], period: int = 12) -> np.ndarray:
    """快捷函數：計算 EMA"""
    return EMA(period).compute(data)


# ─── WMA ────────────────────────────────────────────────────────────────────────

class WMA:
    """
    加權移動平均線 (Weighted Moving Average)

    公式：WMA(n) = Σ(w_i * price[i]) / Σ(w_i)
    其中 w_i = i+1（越新的數據權重越大）
    """

    def __init__(self, period: int = 20):
        if period < 2:
            raise ValueError("WMA period 必須 >= 2")
        self.period = period
        self._weights = np.arange(1, period + 1, dtype=np.float64)
        self._weight_sum = float(self._weights.sum())

    def compute(self, data: Sequence[float]) -> np.ndarray:
        """
        計算 WMA 序列

        Args:
            data: 價格序列（由舊到新）

        Returns:
            WMA 序列（長度與 data 相同，前 period-1 個為 NaN）
        """
        arr = np.array(data, dtype=np.float64)
        n = len(arr)
        result = np.full(n, np.nan, dtype=np.float64)
        if n < self.period:
            return result

        for i in range(self.period - 1, n):
            window = arr[i - self.period + 1:i + 1]
            result[i] = np.dot(self._weights, window) / self._weight_sum

        return result


def compute_wma(data: Sequence[float], period: int = 20) -> np.ndarray:
    """快捷函數：計算 WMA"""
    return WMA(period).compute(data)


# ─── 均線交叉檢測 ───────────────────────────────────────────────────────────────

def detect_crossover(
    short_ma: Sequence[float],
    long_ma: Sequence[float],
) -> List[MovingAverageCrossover]:
    """
    檢測均線交叉事件

    遍歷短均線與長均線序列，找出所有交叉點：
    - 金叉：短均線由下往上穿越長均線
    - 死叉：短均線由上往下跌破長均線

    Args:
        short_ma: 短週期均線序列
        long_ma: 長週期均線序列

    Returns:
        交叉事件列表（按時間順序）
    """
    short = np.array(short_ma, dtype=np.float64)
    long_ = np.array(long_ma, dtype=np.float64)

    if len(short) != len(long_):
        raise ValueError("短均線與長均線長度必須相同")

    n = len(short)
    crossovers: List[MovingAverageCrossover] = []

    for i in range(1, n):
        # 跳過 NaN（前期數據不足）
        if np.isnan(short[i]) or np.isnan(long_[i]):
            continue
        if np.isnan(short[i - 1]) or np.isnan(long_[i - 1]):
            continue

        prev_diff = short[i - 1] - long_[i - 1]
        curr_diff = short[i] - long_[i]

        # 短均線上穿長均線 → 金叉
        if prev_diff <= 0 and curr_diff > 0:
            crossovers.append(MovingAverageCrossover(
                cross_type=MACrossType.GOLDEN_CROSS,
                index=i,
                short_value=float(short[i]),
                long_value=float(long_[i]),
            ))
        # 短均線下穿長均線 → 死叉
        elif prev_diff >= 0 and curr_diff < 0:
            crossovers.append(MovingAverageCrossover(
                cross_type=MACrossType.DEATH_CROSS,
                index=i,
                short_value=float(short[i]),
                long_value=float(long_[i]),
            ))

    return crossovers
