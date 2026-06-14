"""
技術指標模組 (Technical Indicators)

提供純 Python 實現的技術分析指標，無需 TA-Lib 依賴。

子模組：
- moving_averages: SMA / EMA / WMA + 交叉檢測
- rsi: RSI + 超買超賣 + 背離檢測
- macd: MACD + 信號線 + 趨勢判斷
- bollinger: 布林帶 + %B + 收窄檢測
- patterns: K 線形態 + 支撐阻力 + 趨勢評分
"""

from .moving_averages import (
    SMA,
    EMA,
    WMA,
    MovingAverageCrossover,
    compute_sma,
    compute_ema,
    compute_wma,
    detect_crossover,
)
from .rsi import (
    RSI,
    compute_rsi,
    RSIDivergence,
    detect_rsi_divergence,
)
from .macd import (
    MACD,
    compute_macd,
    MACDTrend,
    determine_macd_trend,
)
from .bollinger import (
    BollingerBands,
    compute_bollinger,
    BollingerSqueeze,
    detect_bollinger_squeeze,
)
from .patterns import (
    PatternDetector,
    SupportResistance,
    TrendScorer,
    detect_patterns,
    find_support_resistance,
    compute_trend_score,
)

__all__ = [
    # Moving Averages
    "SMA",
    "EMA",
    "WMA",
    "MovingAverageCrossover",
    "compute_sma",
    "compute_ema",
    "compute_wma",
    "detect_crossover",
    # RSI
    "RSI",
    "compute_rsi",
    "RSIDivergence",
    "detect_rsi_divergence",
    # MACD
    "MACD",
    "compute_macd",
    "MACDTrend",
    "determine_macd_trend",
    # Bollinger
    "BollingerBands",
    "compute_bollinger",
    "BollingerSqueeze",
    "detect_bollinger_squeeze",
    # Patterns
    "PatternDetector",
    "SupportResistance",
    "TrendScorer",
    "detect_patterns",
    "find_support_resistance",
    "compute_trend_score",
]
