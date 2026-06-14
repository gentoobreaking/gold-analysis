"""
Feature Engineering Module - 特徵工程模組
負責從市場數據中提取有意義的特徵，供機器學習模型使用。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """特徵工程配置"""
    lookback_short: int = 5        # 短期回顧窗口（天）
    lookback_medium: int = 20      # 中期回顧窗口（天）
    lookback_long: int = 60       # 長期回顧窗口（天）
    rsi_period: int = 14           # RSI 計算週期
    macd_fast: int = 12           # MACD 快線
    macd_slow: int = 26           # MACD 慢線
    macd_signal: int = 9          # MACD 信號線
    bollinger_period: int = 20    # 布林帶週期
    bollinger_std: float = 2.0    # 布林帶標準差倍數


class FeatureEngineer:
    """
    特徵工程師 - 負責特徵提取與轉換
    
    從原始市場數據（OHLCV + 經濟指標）生成模型可用的特徵。
    遵循現有決策系統的指標風格，確保兼容性。
    
    Attributes:
        config: 特徵工程配置
        feature_names: 生成的特徵名稱列表
    """
    
    # 目標變量類型
    LABEL_BUY = 1
    LABEL_SELL = -1
    LABEL_HOLD = 0
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        初始化特徵工程師
        
        Args:
            config: 特徵工程配置，預設使用合理預設值
        """
        self.config = config or FeatureConfig()
        self.feature_names: List[str] = []
        self._fitted = False
    
    # ─── 公開 API ─────────────────────────────────────────────────────────────
    
    def fit_transform(self, df: pd.DataFrame, label_col: str = "label") -> pd.DataFrame:
        """
        擬合並轉換數據（訓練時使用）
        
        Args:
            df: 輸入數據框，需包含 OHLCV 列
            label_col: 標籤列名稱
            
        Returns:
            包含特徵和標籤的數據框
        """
        self._validate_required_columns(df, required=["close"])
        df = df.copy()
        
        # 生成所有特徵
        df = self._add_price_features(df)
        df = self._add_technical_indicators(df)
        df = self._add_momentum_features(df)
        df = self._add_volatility_features(df)
        df = self._add_pattern_features(df)
        df = self._add_time_features(df)
        
        # 生成標籤（若不存在）
        if label_col not in df.columns:
            df = self._generate_labels(df)
        
        # 移除 NaN 行（特徵計算需要歷史數據）
        df = df.dropna()
        
        # 記錄特徵名稱
        self.feature_names = [c for c in df.columns if c not in ["close", "open", "high", "low", "volume", label_col]]
        self._fitted = True
        
        logger.info(f"特徵工程完成，共生成 {len(self.feature_names)} 個特徵")
        return df
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        轉換新數據（預測時使用）
        
        Args:
            df: 輸入數據框
            
        Returns:
            包含特徵的數據框
        """
        if not self._fitted:
            raise RuntimeError("FeatureEngineer 尚未擬合，請先調用 fit_transform")
        
        df = df.copy()
        df = self._add_price_features(df)
        df = self._add_technical_indicators(df)
        df = self._add_momentum_features(df)
        df = self._add_volatility_features(df)
        df = self._add_pattern_features(df)
        df = self._add_time_features(df)
        
        return df.dropna()
    
    def get_feature_names(self) -> List[str]:
        """返回特徵名稱列表"""
        return self.feature_names.copy()
    
    def get_latest_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        獲取最新一行數據的特徵值（用於即時預測）
        
        Args:
            df: 市場數據
            
        Returns:
            特徵名 -> 特徵值 字典
        """
        transformed = self.transform(df)
        if transformed.empty:
            return {}
        
        latest = transformed.iloc[-1]
        return {k: float(v) for k, v in latest.items() if k in self.feature_names}
    
    # ─── 價格特徵 ─────────────────────────────────────────────────────────────
    
    def _add_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加價格相關特徵"""
        cfg = self.config
        
        # 移動平均線
        df["sma_short"] = df["close"].rolling(window=cfg.lookback_short).mean()
        df["sma_medium"] = df["close"].rolling(window=cfg.lookback_medium).mean()
        df["sma_long"] = df["close"].rolling(window=cfg.lookback_long).mean()
        
        # 價格相對位置
        df["price_vs_sma_short"] = (df["close"] - df["sma_short"]) / df["sma_short"]
        df["price_vs_sma_medium"] = (df["close"] - df["sma_medium"]) / df["sma_medium"]
        df["price_vs_sma_long"] = (df["close"] - df["sma_long"]) / df["sma_long"]
        
        # SMA 排列方向（市場趨勢）
        df["sma_trend"] = (
            (df["sma_short"] > df["sma_medium"]).astype(int) +
            (df["sma_medium"] > df["sma_long"]).astype(int)
        )  # 0=下跌, 1=中性, 2=上漲
        
        # 價格動量（回報率）
        for period in [1, cfg.lookback_short, cfg.lookback_medium, cfg.lookback_long]:
            df[f"return_{period}d"] = df["close"].pct_change(periods=period)
        
        return df
    
    # ─── 技術指標特徵 ─────────────────────────────────────────────────────────
    
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加技術指標特徵"""
        cfg = self.config
        
        # RSI
        df["rsi"] = self._compute_rsi(df["close"], period=cfg.rsi_period)
        
        # MACD
        macd_data = self._compute_macd(
            df["close"],
            fast=cfg.macd_fast,
            slow=cfg.macd_slow,
            signal=cfg.macd_signal
        )
        df["macd"] = macd_data["macd"]
        df["macd_signal"] = macd_data["signal"]
        df["macd_hist"] = macd_data["histogram"]
        
        # MACD 標準化（百分比變化）
        df["macd_hist_pct"] = df["macd_hist"] / df["close"]
        
        # 布林帶
        bollinger = self._compute_bollinger(df["close"], period=cfg.bollinger_period, num_std=cfg.bollinger_std)
        df["bb_upper"] = bollinger["upper"]
        df["bb_middle"] = bollinger["middle"]
        df["bb_lower"] = bollinger["lower"]
        df["bb_width"] = (bollinger["upper"] - bollinger["lower"]) / bollinger["middle"]
        df["bb_position"] = (df["close"] - bollinger["lower"]) / (bollinger["upper"] - bollinger["lower"])
        
        # ATR（Average True Range）
        df["atr"] = self._compute_atr(df, period=14)
        df["atr_pct"] = df["atr"] / df["close"]  # 標準化 ATR
        
        return df
    
    # ─── 動量特徵 ─────────────────────────────────────────────────────────────
    
    def _add_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加動量特徵"""
        cfg = self.config
        
        # 動量震盪指標
        for period in [5, 10, 20]:
            df[f"momentum_{period}"] = df["close"] / df["close"].shift(period) - 1
        
        # ROC（Rate of Change）
        for period in [5, 10, 20]:
            df[f"roc_{period}"] = self._compute_roc(df["close"], period=period)
        
        # CCI（Commodity Channel Index）
        df["cci"] = self._compute_cci(df, period=20)
        
        # Stochastic Oscillator
        stoch = self._compute_stochastic(df, k_period=14, d_period=3)
        df["stoch_k"] = stoch["k"]
        df["stoch_d"] = stoch["d"]
        
        return df
    
    # ─── 波動性特徵 ────────────────────────────────────────────────────────────
    
    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加波動性特徵"""
        cfg = self.config
        
        # 歷史波動率（使用日回報率標準差）
        for period in [5, 10, 20]:
            df[f"volatility_{period}d"] = df["return_1d"].rolling(window=period).std()
        
        # 、波幅範圍
        if "high" in df.columns and "low" in df.columns:
            df["daily_range_pct"] = (df["high"] - df["low"]) / df["close"]
            
            # 過去 N 日平均波幅
            df["avg_range_pct"] = df["daily_range_pct"].rolling(window=5).mean()
        
        return df
    
    # ─── 形態特徵 ─────────────────────────────────────────────────────────────
    
    def _add_pattern_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加價格形態特徵"""
        cfg = self.config
        
        # 價格相對於近期高低點
        df["price_vs_20d_high"] = (df["close"] - df["close"].rolling(20).max()) / df["close"]
        df["price_vs_20d_low"] = (df["close"] - df["close"].rolling(20).min()) / df["close"]
        
        # 缺口標誌
        if "open" in df.columns:
            df["gap_up"] = (df["open"] > df["close"].shift(1)).astype(int)
            df["gap_down"] = (df["open"] < df["close"].shift(1)).astype(int)
        
        # 成交量特徵（若可用）
        if "volume" in df.columns:
            df["volume_sma"] = df["volume"].rolling(window=20).mean()
            df["volume_ratio"] = df["volume"] / df["volume_sma"]
            df["volume_increasing"] = (df["volume"] > df["volume"].shift(1)).astype(int)
        
        return df
    
    # ─── 時間特徵 ─────────────────────────────────────────────────────────────
    
    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """添加時間特徵（捕獲週期性）"""
        if "date" not in df.columns:
            # 嘗試使用 index
            if isinstance(df.index, pd.DatetimeIndex):
                dates = df.index
            else:
                return df
        else:
            dates = pd.to_datetime(df["date"])
        
        # 星期（0=週一, 6=週日）
        df["day_of_week"] = dates.dayofweek
        
        # 月份（1-12）
        df["month"] = dates.month
        
        # 一年中的第幾天
        df["day_of_year"] = dates.dayofyear
        
        # 季度
        df["quarter"] = dates.quarter
        
        # 週末標誌
        df["is_weekend"] = (dates.dayofweek >= 5).astype(int)
        
        return df
    
    # ─── 標籤生成 ─────────────────────────────────────────────────────────────
    
    def _generate_labels(self, df: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
        """
        生成交易標籤
        
        策略：持有 N 天後，若價格上漲 > threshold 則為 BUY，
        下跌 > threshold 則為 SELL，否則為 HOLD。
        
        Args:
            df: 價格數據
            horizon: 持有期（天）
            
        Returns:
            添加了 label 列的數據框
        """
        threshold = 0.01  # 1% 門檻
        
        future_return = df["close"].shift(-horizon) / df["close"] - 1
        
        conditions = [
            future_return > threshold,
            future_return < -threshold,
        ]
        choices = [self.LABEL_BUY, self.LABEL_SELL]
        df["label"] = np.select(conditions, choices, default=self.LABEL_HOLD)
        
        return df
    
    # ─── 技術指標計算（私有輔助方法）─────────────────────────────────────────
    
    @staticmethod
    def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """計算 RSI 相對強弱指數"""
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(window=period).mean()
        loss = (-delta.clip(upper=0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def _compute_macd(
        series: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Dict[str, pd.Series]:
        """計算 MACD"""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": macd_line - signal_line,
        }
    
    @staticmethod
    def _compute_bollinger(
        series: pd.Series,
        period: int = 20,
        num_std: float = 2.0
    ) -> Dict[str, pd.Series]:
        """計算布林帶"""
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        return {
            "upper": middle + (std * num_std),
            "middle": middle,
            "lower": middle - (std * num_std),
        }
    
    @staticmethod
    def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """計算 ATR 平均真實波幅"""
        high = df["high"] if "high" in df.columns else df["close"]
        low = df["low"] if "low" in df.columns else df["close"]
        prev_close = df["close"].shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    @staticmethod
    def _compute_roc(series: pd.Series, period: int) -> pd.Series:
        """計算 ROC 變化率"""
        return (series - series.shift(period)) / series.shift(period) * 100
    
    @staticmethod
    def _compute_cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """計算 CCI 商品通道指數"""
        high = df["high"] if "high" in df.columns else df["close"]
        low = df["low"] if "low" in df.columns else df["close"]
        typical_price = (high + low + df["close"]) / 3
        sma = typical_price.rolling(window=period).mean()
        mad = typical_price.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
        return (typical_price - sma) / (0.015 * mad + 1e-10)
    
    @staticmethod
    def _compute_stochastic(
        df: pd.DataFrame,
        k_period: int = 14,
        d_period: int = 3
    ) -> Dict[str, pd.Series]:
        """計算隨機振盪指標"""
        high = df["high"] if "high" in df.columns else df["close"]
        low = df["low"] if "low" in df.columns else df["close"]
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k = 100 * (df["close"] - lowest_low) / (highest_high - lowest_low + 1e-10)
        d = k.rolling(window=d_period).mean()
        return {"k": k, "d": d}
    
    # ─── 驗證工具 ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def _validate_required_columns(df: pd.DataFrame, required: List[str]) -> None:
        """驗證必需列是否存在"""
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"缺少必需列: {missing}，現有列: {list(df.columns)}")
