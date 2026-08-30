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

from .bollinger import (
    BollingerBands,
    BollingerSqueeze,
    compute_bollinger,
    detect_bollinger_squeeze,
)
from .macd import (
    MACD,
    MACDTrend,
    compute_macd,
    determine_macd_trend,
)
from .moving_averages import (
    EMA,
    SMA,
    WMA,
    MovingAverageCrossover,
    compute_ema,
    compute_sma,
    compute_wma,
    detect_crossover,
)
from .patterns import (
    PatternDetector,
    SupportResistance,
    TrendScorer,
    compute_trend_score,
    detect_patterns,
    find_support_resistance,
)
from .rsi import (
    RSI,
    RSIDivergence,
    compute_rsi,
    detect_rsi_divergence,
)

__all__ = [
    "EMA",
    # MACD
    "MACD",
    # RSI
    "RSI",
    # Moving Averages
    "SMA",
    "WMA",
    # Bollinger
    "BollingerBands",
    "BollingerSqueeze",
    "MACDTrend",
    "MovingAverageCrossover",
    # Patterns
    "PatternDetector",
    "RSIDivergence",
    "SupportResistance",
    "TrendScorer",
    "compute_bollinger",
    "compute_ema",
    "compute_macd",
    "compute_rsi",
    "compute_sma",
    "compute_trend_score",
    "compute_wma",
    "detect_bollinger_squeeze",
    "detect_crossover",
    "detect_patterns",
    "detect_rsi_divergence",
    "determine_macd_trend",
    "find_support_resistance",
]
