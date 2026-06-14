"""
K 線形態模組 (Candlestick Patterns)

單根/兩根/三根 K 線形態識別 + 支撐阻力位 + 綜合趨勢評分。

使用範例：
    patterns = detect_patterns(df)
    sr_levels = find_support_resistance(df)
    score = compute_trend_score(df)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)


# ─── 數據類別 ─────────────────────────────────────────────────────────────────

class PatternType(str, Enum):
    """K 線形態枚舉"""
    DOJI = "doji"                     # 十字星
    HAMMER = "hammer"                 # 錘子線
    HANGING_MAN = "hanging_man"       # 上吊線
    BULLISH_ENGULFING = "bullish_engulfing"   # 看漲吞噬
    BEARISH_ENGULFING = "bearish_engulfing"   # 看跌吞噬
    MORNING_STAR = "morning_star"     # 晨星
    EVENING_STAR = "evening_star"     # 暮星
    THREE_WHITE_SOLDIERS = "three_white_soldiers"  # 三白兵
    THREE_BLACK_CROWS = "three_black_crows"        # 三黑鴉
    NONE = "none"


@dataclass
class CandlestickPattern:
    """K 線形態"""
    pattern_type: PatternType
    start_idx: int
    end_idx: int
    strength: float          # 1.0 ~ 3.0
    direction: str           # "bullish" / "bearish" / "neutral"


@dataclass
class SupportResistance:
    """支撐/阻力位"""
    level: float
    level_type: str         # "support" / "resistance"
    touch_count: int        # 被觸碰次數
    last_touch_idx: int


@dataclass
class TrendScore:
    """綜合趨勢評分"""
    score: float             # -100 到 100
    trend: str               # "bullish" / "bearish" / "neutral"
    confidence: float        # 0.0 ~ 1.0
    breakdown: Dict[str, float]


# ─── 形態偵測器封裝類 ────────────────────────────────────────────────────────

class PatternDetector:
    """
    K 線形態偵測器

    封裝 detect_patterns() 為類，方便配置參數。
    """

    def __init__(self, min_strength: float = 1.0):
        self.min_strength = min_strength

    def detect(self, df) -> List[CandlestickPattern]:
        return detect_patterns(df, min_strength=self.min_strength)

    def bullish_count(self, df) -> int:
        patterns = self.detect(df)
        return sum(1 for p in patterns if p.direction == "bullish")

    def bearish_count(self, df) -> int:
        patterns = self.detect(df)
        return sum(1 for p in patterns if p.direction == "bearish")


class TrendScorer:
    """
    趨勢評分器

    封裝 compute_trend_score() 為類，方便配置均線參數。
    """

    def __init__(self, ma_short: int = 20, ma_long: int = 60):
        self.ma_short = ma_short
        self.ma_long = ma_long

    def score(self, df) -> TrendScore:
        return compute_trend_score(df, self.ma_short, self.ma_long)

    def is_bullish(self, df, threshold: float = 20.0) -> bool:
        return self.score(df).score > threshold

    def is_bearish(self, df, threshold: float = -20.0) -> bool:
        return self.score(df).score < threshold


# ─── 形態識別 ─────────────────────────────────────────────────────────────────

def _ohlc(series, idx) -> tuple:
    """取第 idx 根 K 線的 OHLC"""
    return (
        float(series["open"].iloc[idx]),
        float(series["high"].iloc[idx]),
        float(series["low"].iloc[idx]),
        float(series["close"].iloc[idx]),
    )


def _is_doji(open_: float, close: float, high: float, low: float, threshold: float = 0.1) -> bool:
    """十字星：實體很小，上下影線差不多長"""
    body = abs(close - open_)
    range_ = high - low
    if range_ == 0:
        return False
    return body / range_ < threshold


def _is_hammer(open_: float, close: float, high: float, low: float) -> bool:
    """錘子線：下影線很長（> 2倍實體），實體小，在高位"""
    body = abs(close - open_)
    upper_shadow = high - max(open_, close)
    lower_shadow = min(open_, close) - low
    return lower_shadow > 2 * body and upper_shadow < body and body > 0


def _is_bullish_engulfing(o1, c1, o2, c2) -> bool:
    """看漲吞噬：第二根吃掉第一根，且第二根收漲"""
    return c1 < o1 and c2 > o2 and c2 >= o1 and c2 > c1


def _is_bearish_engulfing(o1, c1, o2, c2) -> bool:
    """看跌吞噬：第二根吃掉第一根，且第二根收跌"""
    return c1 > o1 and c2 < o2 and c2 <= o1 and c2 < c1


def detect_patterns(df, min_strength: float = 1.0) -> List[CandlestickPattern]:
    """
    檢測 K 線形態

    Args:
        df: 含 OHLC 的 DataFrame
        min_strength: 最低強度閾值

    Returns:
        形態列表
    """
    n = len(df)
    patterns = []

    for i in range(n - 1):
        o1, h1, l1, c1 = _ohlc(df, i)
        o2, h2, l2, c2 = _ohlc(df, i + 1)

        # 十字星
        if _is_doji(o1, c1, h1, l1):
            patterns.append(CandlestickPattern(
                pattern_type=PatternType.DOJI,
                start_idx=i, end_idx=i,
                strength=1.5, direction="neutral",
            ))

        # 錘子線
        if _is_hammer(o1, c1, h1, l1):
            patterns.append(CandlestickPattern(
                pattern_type=PatternType.HAMMER,
                start_idx=i, end_idx=i,
                strength=2.0, direction="bullish",
            ))

        # 吞噬
        if _is_bullish_engulfing(o1, c1, o2, c2):
            patterns.append(CandlestickPattern(
                pattern_type=PatternType.BULLISH_ENGULFING,
                start_idx=i, end_idx=i + 1,
                strength=2.5, direction="bullish",
            ))
        if _is_bearish_engulfing(o1, c1, o2, c2):
            patterns.append(CandlestickPattern(
                pattern_type=PatternType.BEARISH_ENGULFING,
                start_idx=i, end_idx=i + 1,
                strength=2.5, direction="bearish",
            ))

    # 三根 K 線形態（晨星/暮星/三白兵/三黑鴉）
    for i in range(n - 2):
        o1, h1, l1, c1 = _ohlc(df, i)
        o2, h2, l2, c2 = _ohlc(df, i + 1)
        o3, h3, l3, c3 = _ohlc(df, i + 2)

        # 晨星（看漲）
        if c1 < o1 and abs(c2 - o2) < (o2 - c2 if o2 != c2 else 1) * 0.5 and c3 > o3 and c3 > (o1 + c1) / 2:
            patterns.append(CandlestickPattern(
                pattern_type=PatternType.MORNING_STAR,
                start_idx=i, end_idx=i + 2,
                strength=3.0, direction="bullish",
            ))

        # 暮星（看跌）
        if c1 > o1 and abs(c2 - o2) < (c2 - o2 if c2 != o2 else 1) * 0.5 and c3 < o3 and c3 < (o1 + c1) / 2:
            patterns.append(CandlestickPattern(
                pattern_type=PatternType.EVENING_STAR,
                start_idx=i, end_idx=i + 2,
                strength=3.0, direction="bearish",
            ))

        # 三白兵
        if c1 > o1 and c2 > o2 and c3 > o3 and c1 > c2 > c3:
            patterns.append(CandlestickPattern(
                pattern_type=PatternType.THREE_WHITE_SOLDIERS,
                start_idx=i, end_idx=i + 2,
                strength=3.0, direction="bullish",
            ))

        # 三黑鴉
        if c1 < o1 and c2 < o2 and c3 < o3 and c1 < c2 < c3:
            patterns.append(CandlestickPattern(
                pattern_type=PatternType.THREE_BLACK_CROWS,
                start_idx=i, end_idx=i + 2,
                strength=3.0, direction="bearish",
            ))

    return [p for p in patterns if p.strength >= min_strength]


# ─── 支撐阻力位 ───────────────────────────────────────────────────────────────

def find_support_resistance(
    df,
    lookback: int = 50,
    min_touches: int = 2,
    tolerance: float = 0.005,
) -> List[SupportResistance]:
    """
    基於局部極值識別支撐阻力位

    Args:
        df: 含 OHLC 的 DataFrame
        lookback: 回顧窗口
        min_touches: 最小觸碰次數
        tolerance: 價格容差（5 日均值百分比）

    Returns:
        支撐阻力位列表
    """
    n = len(df)
    if n < lookback:
        lookback = n

    lows = df["low"].iloc[-lookback:].values
    highs = df["high"].iloc[-lookback:].values

    avg_price = np.mean(lows)

    def find_local_max(arr):
        peaks = []
        for i in range(1, len(arr) - 1):
            if arr[i] > arr[i - 1] and arr[i] > arr[i + 1]:
                peaks.append((i, arr[i]))
        return peaks

    def find_local_min(arr):
        troughs = []
        for i in range(1, len(arr) - 1):
            if arr[i] < arr[i - 1] and arr[i] < arr[i + 1]:
                troughs.append((i, arr[i]))
        return troughs

    levels: List[SupportResistance] = []

    # 聚合相近極值
    def aggregate_levels(extrema, level_type, tolerance_pct):
        nonlocal avg_price
        sorted_ext = sorted(extrema, key=lambda x: x[1])
        clusters = []
        current = [sorted_ext[0]] if sorted_ext else []

        for i in range(1, len(sorted_ext)):
            if abs(sorted_ext[i][1] - current[-1][1]) < avg_price * tolerance_pct:
                current.append(sorted_ext[i])
            else:
                clusters.append(current)
                current = [sorted_ext[i]]
        if current:
            clusters.append(current)

        for cluster in clusters:
            if len(cluster) >= min_touches:
                avg_level = np.mean([e[1] for e in cluster])
                levels.append(SupportResistance(
                    level=float(avg_level),
                    level_type=level_type,
                    touch_count=len(cluster),
                    last_touch_idx=int(cluster[-1][0]),
                ))

    aggregate_levels(find_local_max(highs), "resistance", tolerance)
    aggregate_levels(find_local_min(lows), "support", tolerance)

    levels.sort(key=lambda x: x.touch_count, reverse=True)
    return levels


# ─── 綜合趨勢評分 ─────────────────────────────────────────────────────────────

def compute_trend_score(
    df,
    ma_short: int = 20,
    ma_long: int = 60,
) -> TrendScore:
    """
    計算綜合趨勢評分（-100 到 100）

    維度：
    - 均線方向（40%）
    - 動量（30%）
    - 形態信號（20%）
    - 成交量（10%）

    Args:
        df: 含 OHLCV 的 DataFrame
        ma_short: 短均線週期
        ma_long: 長均線週期

    Returns:
        趨勢評分
    """
    n = len(df)
    closes = df["close"].values

    breakdown: Dict[str, float] = {}

    # 1. 均線方向
    ma_s = np.full(n, np.nan)
    ma_l = np.full(n, np.nan)
    if n >= ma_short:
        for i in range(ma_short - 1, n):
            ma_s[i] = np.mean(closes[i - ma_short + 1:i + 1])
    if n >= ma_long:
        for i in range(ma_long - 1, n):
            ma_l[i] = np.mean(closes[i - ma_long + 1:i + 1])

    ma_score = 0.0
    if n >= ma_long:
        valid = ~(np.isnan(ma_s) | np.isnan(ma_l))
        if np.sum(valid) >= 2:
            diff = ma_s[valid][-1] - ma_l[valid][-1]
            diff_prev = ma_s[valid][-2] - ma_l[valid][-2]
            # 價格高於兩條均線，且均線多頭排列
            ma_score = 40 if diff > 0 and diff > diff_prev else (-40 if diff < 0 and diff < diff_prev else 0)
    breakdown["ma_direction"] = ma_score

    # 2. 動量（RSI）
    rsi_vals = []
    for i in range(n):
        if i < 14:
            rsi_vals.append(np.nan)
        else:
            gains = np.where(np.diff(closes[max(0, i - 14):i + 1]) > 0,
                             np.diff(closes[max(0, i - 14):i + 1]), 0)
            losses = np.where(np.diff(closes[max(0, i - 14):i + 1]) < 0,
                              -np.diff(closes[max(0, i - 14):i + 1]), 0)
            avg_gain = np.mean(gains) if len(gains) > 0 else 0
            avg_loss = np.mean(losses) if len(losses) > 0 else 0
            rsi_vals.append(50 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / max(avg_loss, 1e-9))))

    rsi_arr = np.array(rsi_vals)
    momentum_score = 0.0
    if not np.isnan(rsi_arr[-1]):
        if rsi_arr[-1] > 60:
            momentum_score = 30
        elif rsi_arr[-1] < 40:
            momentum_score = -30
    breakdown["momentum"] = momentum_score

    # 3. 形態信號
    patterns = detect_patterns(df, min_strength=2.0)
    bullish_count = sum(1 for p in patterns if p.direction == "bullish")
    bearish_count = sum(1 for p in patterns if p.direction == "bearish")
    pattern_score = 20 if bullish_count > bearish_count else (-20 if bearish_count > bullish_count else 0)
    breakdown["patterns"] = pattern_score

    # 4. 成交量（如果有 volume）
    vol_score = 0.0
    if "volume" in df.columns and n >= 5:
        vol = df["volume"].values
        avg_vol = np.mean(vol[-20:]) if n >= 20 else np.mean(vol)
        recent_vol = np.mean(vol[-5:])
        if recent_vol > avg_vol * 1.2:
            vol_score = 10
        elif recent_vol < avg_vol * 0.8:
            vol_score = -10
    breakdown["volume"] = vol_score

    total = ma_score + momentum_score + pattern_score + vol_score
    total = max(-100, min(100, total))

    trend = "bullish" if total > 20 else ("bearish" if total < -20 else "neutral")
    confidence = abs(total) / 100.0

    return TrendScore(
        score=float(total),
        trend=trend,
        confidence=confidence,
        breakdown=breakdown,
    )
