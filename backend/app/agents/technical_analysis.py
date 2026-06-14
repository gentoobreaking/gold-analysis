"""
技術分析 Agent

整合 MA/RSI/MACD/Bollinger/Patterns 所有指標，輸出綜合技術分析結果。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..agents.base import GoldAnalysisAgent
from ..indicators.moving_averages import SMA, EMA, detect_crossover
from ..indicators.rsi import RSI, RSIDivergence, generate_rsi_signals, detect_rsi_divergence
from ..indicators.macd import MACD, determine_macd_trend, detect_macd_cross
from ..indicators.bollinger import BollingerBands, detect_bollinger_squeeze
from ..indicators.patterns import (
    PatternDetector, SupportResistance,
    TrendScorer, detect_patterns,
    find_support_resistance, compute_trend_score,
)

logger = logging.getLogger(__name__)


class TechnicalAnalysisAgent(GoldAnalysisAgent):
    """
    技術分析 Agent

    接收 OHLC 價格數據，輸出：
    - 各項技術指標數值
    - 買賣信號
    - 風險等級（低/中/高）
    - 操作建議
    """

    def __init__(
        self,
        model: str = "qclaw/modelroute",
        temperature: float = 0.3,
        max_tokens: int = 1500,
    ):
        super().__init__(
            name="TechnicalAnalysisAgent",
            role="technical_analyst",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.rsi = RSI(period=14)
        self.macd = MACD(fast_period=12, slow_period=26, signal_period=9)
        self.bollinger = BollingerBands(period=20, std_mult=2.0)
        self.ma_short = SMA(period=20)
        self.ma_long = SMA(period=60)

    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        執行技術分析

        Args:
            context: {
                "prices": List[float] 或 pd.DataFrame（含 OHLC），
                "symbol": str，資產代碼，
                "timeframe": str（可選），
            }

        Returns:
            {
                "symbol": str,
                "timeframe": str,
                "indicators": {...},
                "signals": [...],
                "trend_score": float,
                "risk_level": str,
                "recommendation": str,
                "support_resistance": [...],
            }
        """
        symbol = context.get("symbol", "UNKNOWN")
        timeframe = context.get("timeframe", "1D")

        # 支援 list[float] 或 DataFrame
        if isinstance(context.get("prices"), pd.DataFrame):
            df = context["prices"]
            closes = df["close"].values.tolist()
            ohlc_df = df
        else:
            closes = context.get("prices", [])
            ohlc_df = None
            logger.warning("無 OHLC DataFrame，形態識別跳過")

        if len(closes) < 8:
            return {
                "symbol": symbol,
                "error": "數據不足，至少需要 8 根 K 線",
                "risk_level": "unknown",
                "recommendation": "等待更多數據（目前 10 筆，gold_monitor 每日增加）",
            }

        # ── 各項指標計算（動態週期：小樣本專用）─────────────────────────────
        n = len(closes)
        # RSI：固定 14，但 n<14 時用可用資料
        rsi_period = min(14, max(7, n - 5))
        rsi = RSI(period=rsi_period)
        rsi_vals = rsi.compute(closes)
        # MACD：n 不足時縮短參數
        fast_p = min(12, max(5, n // 2))
        slow_p = min(26, max(fast_p + 1, n - 3))
        sig_p  = min(9, max(3, n // 4))
        macd = MACD(fast_period=fast_p, slow_period=slow_p, signal_period=sig_p)
        macd_line, signal_line, histogram = macd.compute(closes)
        # Bollinger：週期 min(20, n-2)
        bb_period = min(20, max(5, n - 2))
        bb = BollingerBands(period=bb_period, std_mult=2.0)
        upper, middle, lower, percent_b, bandwidth = bb.compute(closes)
        # MA：短=min(20,n-2)，長=min(60,n-5)，至少差 3
        ma_s = min(20, max(3, n - 3))
        ma_l = min(60, max(ma_s + 3, n - 2))
        ma_short_vals = SMA(period=ma_s).compute(closes)
        ma_long_vals  = SMA(period=ma_l).compute(closes)

        # 當前值
        rsi_current = float(rsi_vals[-1]) if not np.isnan(rsi_vals[-1]) else None
        macd_current = float(macd_line[-1]) if not np.isnan(macd_line[-1]) else None
        signal_current = float(signal_line[-1]) if not np.isnan(signal_line[-1]) else None
        bb_upper = float(upper[-1]) if not np.isnan(upper[-1]) else None
        bb_middle = float(middle[-1]) if not np.isnan(middle[-1]) else None
        bb_lower = float(lower[-1]) if not np.isnan(lower[-1]) else None
        bb_percent_b = float(percent_b[-1]) if not np.isnan(percent_b[-1]) else None
        close_current = float(closes[-1])

        # ── 信號生成 ──────────────────────────────────────────────────────

        signals: List[Dict[str, Any]] = []

        # RSI 超買超賣
        rsi_signals = generate_rsi_signals(rsi_vals.tolist())
        for s in rsi_signals[-5:]:  # 只取最近 5 個
            signals.append({
                "type": "rsi",
                "action": "buy" if s.signal_type.value == "oversold" else ("sell" if s.signal_type.value == "overbought" else "hold"),
                "value": round(s.value, 2),
                "description": f"RSI {s.signal_type.value.upper()}（{s.value:.1f}）",
            })

        # MACD 交叉
        macd_trend = determine_macd_trend(macd_vals := macd_line.tolist(), signal_line.tolist())
        crosses = detect_macd_cross(macd_vals, signal_line.tolist())
        if crosses:
            last_cross = crosses[-1]
            signals.append({
                "type": "macd_cross",
                "action": "buy" if last_cross.cross_type == "golden" else "sell",
                "description": f"MACD {'金叉' if last_cross.cross_type == 'golden' else '死叉'}",
            })

        # 布林帶位置
        if bb_percent_b is not None:
            if bb_percent_b > 1.0:
                signals.append({"type": "bollinger", "action": "sell", "description": "價格突破布林上軌（超買區）"})
            elif bb_percent_b < 0.0:
                signals.append({"type": "bollinger", "action": "buy", "description": "價格跌破布林下軌（超賣區）"})

        # 均線交叉
        ma_crosses = detect_crossover(ma_short_vals.tolist(), ma_long_vals.tolist())
        if ma_crosses:
            last_ma = ma_crosses[-1]
            signals.append({
                "type": "ma_cross",
                "action": "buy" if last_ma.cross_type.value == "golden_cross" else "sell",
                "description": f"{'MA20/MA60 金叉' if last_ma.cross_type.value == 'golden_cross' else 'MA20/MA60 死叉'}",
            })

        # ── 形態識別 ─────────────────────────────────────────────────────

        pattern_signals: List[Dict[str, Any]] = []
        if ohlc_df is not None:
            detected = detect_patterns(ohlc_df)
            for p in detected[-5:]:
                pattern_signals.append({
                    "type": "candlestick",
                    "pattern": p.pattern_type.value,
                    "direction": p.direction,
                    "strength": p.strength,
                })
            sr_levels = find_support_resistance(ohlc_df)
        else:
            sr_levels = []

        # ── 趨勢評分 ─────────────────────────────────────────────────────

        trend_result = compute_trend_score(ohlc_df) if ohlc_df is not None else None

        # ── 綜合建議 ─────────────────────────────────────────────────────

        buy_signals = sum(1 for s in signals if s.get("action") == "buy")
        sell_signals = sum(1 for s in signals if s.get("action") == "sell")

        risk_level = "low"
        recommendation = "持有觀望"

        if rsi_current and (rsi_current > 75 or rsi_current < 25):
            risk_level = "high"
        elif rsi_current and (rsi_current > 65 or rsi_current < 35):
            risk_level = "medium"

        if buy_signals >= 3:
            recommendation = "建議買入"
        elif sell_signals >= 3:
            recommendation = "建議賣出"
        elif trend_result and trend_result.trend == "bullish":
            recommendation = "偏多持有"
        elif trend_result and trend_result.trend == "bearish":
            recommendation = "偏空觀望"

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": pd.Timestamp.now().isoformat(),
            "indicators": {
                "rsi": round(rsi_current, 2) if rsi_current else None,
                "macd": round(macd_current, 2) if macd_current else None,
                "macd_signal": round(signal_current, 2) if signal_current else None,
                "bollinger": {
                    "upper": round(bb_upper, 2) if bb_upper else None,
                    "middle": round(bb_middle, 2) if bb_middle else None,
                    "lower": round(bb_lower, 2) if bb_lower else None,
                    "percent_b": round(bb_percent_b, 3) if bb_percent_b else None,
                },
                "ma": {
                    "ma20": round(float(ma_short_vals[-1]), 2) if not np.isnan(ma_short_vals[-1]) else None,
                    "ma60": round(float(ma_long_vals[-1]), 2) if not np.isnan(ma_long_vals[-1]) else None,
                },
                "macd_trend": macd_trend.value,
            },
            "signals": signals,
            "pattern_signals": pattern_signals,
            "trend_score": trend_result.score if trend_result else None,
            "trend_direction": trend_result.trend if trend_result else None,
            "risk_level": risk_level,
            "recommendation": recommendation,
            "support_resistance": [
                {"level": round(sr.level, 2), "type": sr.level_type, "touches": sr.touch_count}
                for sr in sr_levels[:5]
            ],
        }
