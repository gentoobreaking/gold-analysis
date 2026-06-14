"""
MACD 模組 (Moving Average Convergence Divergence)

純 Python 實現 MACD 計算、信號線、柱狀圖、趨勢判斷。

使用範例：
    macd_line, signal_line, histogram = compute_macd(closes)
    trend = determine_macd_trend(macd_line, signal_line, histogram)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ─── 常量 ─────────────────────────────────────────────────────────────────────

DEFAULT_FAST = 12
DEFAULT_SLOW = 26
DEFAULT_SIGNAL = 9


# ─── 數據類別 ─────────────────────────────────────────────────────────────────

class MACDTrend(str, Enum):
    """MACD 趨勢類型"""
    BULLISH = "bullish"         # 看多（MACD > 信號線）
    BEARISH = "bearish"         # 看空（MACD < 信號線）
    WEAKENING_BULL = "weakening_bull"  # 多頭減弱（柱狀圖遞減但仍 > 0）
    STRENGTHENING_BEAR = "strengthening_bear"  # 空頭減弱（柱狀圖遞增但仍 < 0）
    NEUTRAL = "neutral"


@dataclass
class MACDCrossSignal:
    """MACD 交叉信號"""
    cross_type: str             # "golden" 或 "death"
    index: int
    macd_value: float
    signal_value: float
    histogram: float


# ─── MACD 計算 ────────────────────────────────────────────────────────────────

class MACD:
    """
    MACD 指標

    MACD Line = EMA(fast) - EMA(slow)
    Signal Line = EMA(MACD, signal_period)
    Histogram = MACD - Signal
    """

    def __init__(
        self,
        fast_period: int = DEFAULT_FAST,
        slow_period: int = DEFAULT_SLOW,
        signal_period: int = DEFAULT_SIGNAL,
    ):
        if fast_period >= slow_period:
            raise ValueError("fast_period 必須 < slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def compute(self, data: Sequence[float]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        計算 MACD

        Args:
            data: 價格序列（由舊到新）

        Returns:
            (macd_line, signal_line, histogram) 三個等長序列
        """
        arr = np.array(data, dtype=np.float64)
        n = len(arr)
        macd_line = np.full(n, np.nan)
        signal_line = np.full(n, np.nan)
        histogram = np.full(n, np.nan)

        if n <= self.slow_period:
            return macd_line, signal_line, histogram

        # 計算快慢 EMA
        alpha_fast = 2.0 / (self.fast_period + 1)
        alpha_slow = 2.0 / (self.slow_period + 1)
        alpha_signal = 2.0 / (self.signal_period + 1)

        # EMA 初始化用 SMA
        ema_fast = np.mean(arr[:self.fast_period])
        ema_slow = np.mean(arr[:self.slow_period])

        macd_values = []
        start_idx = self.slow_period - 1

        for i in range(self.slow_period, n):
            ema_fast = alpha_fast * arr[i] + (1 - alpha_fast) * ema_fast
            ema_slow = alpha_slow * arr[i] + (1 - alpha_slow) * ema_slow
            macd_val = ema_fast - ema_slow
            macd_line[i] = macd_val
            macd_values.append(macd_val)

        if len(macd_values) < self.signal_period:
            return macd_line, signal_line, histogram

        # 信號線（MACD 的 EMA）
        ema_signal = np.mean(macd_values[:self.signal_period])
        signal_start = start_idx + self.signal_period

        for i, val in enumerate(macd_values[self.signal_period:]):
            ema_signal = alpha_signal * val + (1 - alpha_signal) * ema_signal
            idx = signal_start + i
            signal_line[idx] = ema_signal
            histogram[idx] = macd_line[idx] - ema_signal

        return macd_line, signal_line, histogram


def compute_macd(
    data: Sequence[float],
    fast_period: int = DEFAULT_FAST,
    slow_period: int = DEFAULT_SLOW,
    signal_period: int = DEFAULT_SIGNAL,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """快捷函數：計算 MACD"""
    return MACD(fast_period, slow_period, signal_period).compute(data)


# ─── 趨勢判斷 ─────────────────────────────────────────────────────────────────

def determine_macd_trend(
    macd_line: Sequence[float],
    signal_line: Sequence[float],
    histogram: Optional[Sequence[float]] = None,
    lookback: int = 5,
) -> MACDTrend:
    """
    判斷 MACD 趨勢

    Args:
        macd_line: MACD 線
        signal_line: 信號線
        histogram: 柱狀圖（可選，自動計算）
        lookback: 回顧期數

    Returns:
        趨勢類型
    """
    macd = np.array(macd_line, dtype=np.float64)
    signal = np.array(signal_line, dtype=np.float64)

    # 去除 NaN 取尾部
    valid = ~(np.isnan(macd) | np.isnan(signal))
    if np.sum(valid) < lookback:
        return MACDTrend.NEUTRAL

    macd_v = macd[valid][-lookback:]
    signal_v = signal[valid][-lookback:]

    if histogram is not None:
        hist = np.array(histogram, dtype=np.float64)
        hist_v = hist[valid][-lookback:]
    else:
        hist_v = macd_v - signal_v

    current_diff = macd_v[-1] - signal_v[-1]

    if current_diff > 0:
        # MACD > 信號線，看多
        if len(hist_v) >= 2:
            if hist_v[-1] < hist_v[-2]:
                return MACDTrend.WEAKENING_BULL
        return MACDTrend.BULLISH
    elif current_diff < 0:
        # MACD < 信號線，看空
        if len(hist_v) >= 2:
            if hist_v[-1] > hist_v[-2]:
                return MACDTrend.STRENGTHENING_BEAR
        return MACDTrend.BEARISH
    else:
        return MACDTrend.NEUTRAL


def detect_macd_cross(
    macd_line: Sequence[float],
    signal_line: Sequence[float],
) -> List[MACDCrossSignal]:
    """
    檢測 MACD 金叉/死叉

    Args:
        macd_line: MACD 線
        signal_line: 信號線

    Returns:
        交叉信號列表
    """
    macd = np.array(macd_line, dtype=np.float64)
    signal = np.array(signal_line, dtype=np.float64)

    if len(macd) != len(signal):
        raise ValueError("MACD 線與信號線長度必須相同")

    crosses = []
    for i in range(1, len(macd)):
        if np.isnan(macd[i]) or np.isnan(signal[i]):
            continue
        if np.isnan(macd[i - 1]) or np.isnan(signal[i - 1]):
            continue

        prev = macd[i - 1] - signal[i - 1]
        curr = macd[i] - signal[i]

        if prev <= 0 and curr > 0:
            crosses.append(MACDCrossSignal(
                cross_type="golden",
                index=i,
                macd_value=float(macd[i]),
                signal_value=float(signal[i]),
                histogram=float(curr),
            ))
        elif prev >= 0 and curr < 0:
            crosses.append(MACDCrossSignal(
                cross_type="death",
                index=i,
                macd_value=float(macd[i]),
                signal_value=float(signal[i]),
                histogram=float(curr),
            ))

    return crosses
