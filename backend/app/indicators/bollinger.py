"""
布林帶模組 (Bollinger Bands)

純 Python 實現布林帶計算、%B、帶寬收窄檢測。

使用範例：
    upper, middle, lower, percent_b, bandwidth = compute_bollinger(closes)
    squeeze = detect_bollinger_squeeze(bandwidth)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ─── 常量 ─────────────────────────────────────────────────────────────────────

DEFAULT_PERIOD = 20
DEFAULT_STD_MULT = 2.0
SQUEEZE_RATIO = 0.10  # 帶寬 < 收盤價的 10% 視為收窄


# ─── 數據類別 ─────────────────────────────────────────────────────────────────

@dataclass
class BollingerSqueeze:
    """布林帶收窄事件"""
    start_idx: int
    end_idx: int
    min_bandwidth: float
    avg_bandwidth: float


# ─── 布林帶計算 ────────────────────────────────────────────────────────────────

class BollingerBands:
    """
    布林帶

    Middle = SMA(period)
    Upper = Middle + std_mult * StdDev
    Lower = Middle - std_mult * StdDev
    %B = (price - Lower) / (Upper - Lower)
    Bandwidth = (Upper - Lower) / Middle
    """

    def __init__(
        self,
        period: int = DEFAULT_PERIOD,
        std_mult: float = DEFAULT_STD_MULT,
    ):
        if period < 2:
            raise ValueError("布林帶 period 必須 >= 2")
        self.period = period
        self.std_mult = std_mult

    def compute(
        self,
        data: Sequence[float],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        計算布林帶

        Args:
            data: 價格序列（由舊到新）

        Returns:
            (upper, middle, lower, percent_b, bandwidth)
        """
        arr = np.array(data, dtype=np.float64)
        n = len(arr)
        upper = np.full(n, np.nan)
        middle = np.full(n, np.nan)
        lower = np.full(n, np.nan)
        percent_b = np.full(n, np.nan)
        bandwidth = np.full(n, np.nan)

        if n < self.period:
            return upper, middle, lower, percent_b, bandwidth

        for i in range(self.period - 1, n):
            window = arr[i - self.period + 1:i + 1]
            sma = np.mean(window)
            std = np.std(window, ddof=0)

            middle[i] = sma
            upper[i] = sma + self.std_mult * std
            lower[i] = sma - self.std_mult * std

            band_width = upper[i] - lower[i]
            if band_width > 0:
                percent_b[i] = (arr[i] - lower[i]) / band_width
                bandwidth[i] = band_width / sma if sma > 0 else 0

        return upper, middle, lower, percent_b, bandwidth


def compute_bollinger(
    data: Sequence[float],
    period: int = DEFAULT_PERIOD,
    std_mult: float = DEFAULT_STD_MULT,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """快捷函數：計算布林帶"""
    return BollingerBands(period, std_mult).compute(data)


# ─── 收窄檢測 ─────────────────────────────────────────────────────────────────

def detect_bollinger_squeeze(
    bandwidth: Sequence[float],
    threshold: float = SQUEEZE_RATIO,
    min_duration: int = 3,
) -> List[BollingerSqueeze]:
    """
    檢測布林帶收窄（Squeeze）

    當帶寬連續 N 根 K 線低於閾值時判定為收窄。

    Args:
        bandwidth: 帶寬序列
        threshold: 收窄閾值（默認 0.10 = 10%）
        min_duration: 最小持續期數

    Returns:
        收窄事件列表
    """
    bw = np.array(bandwidth, dtype=np.float64)
    n = len(bw)
    squeezes = []

    i = 0
    while i < n:
        if np.isnan(bw[i]) or bw[i] >= threshold:
            i += 1
            continue

        # 找到收窄區間
        start = i
        while i < n and not np.isnan(bw[i]) and bw[i] < threshold:
            i += 1
        end = i  # exclusive

        if end - start >= min_duration:
            segment = bw[start:end]
            squeezes.append(BollingerSqueeze(
                start_idx=start,
                end_idx=end - 1,
                min_bandwidth=float(np.min(segment)),
                avg_bandwidth=float(np.mean(segment)),
            ))

    return squeezes
