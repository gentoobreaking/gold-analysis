"""
分析計算工具 - 用於技術指標計算和圖表模式識別

提供移動平均線、RSI、MACD、布林帶等常用技術指標計算。
"""

from typing import List, Dict, Any, Optional, Tuple
import math
from collections import deque
import logging

logger = logging.getLogger(__name__)


class AnalysisTools:
    """
    分析計算工具集
    
    提供黃金和金融市場技術分析的計算工具。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化分析工具
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        logger.info("AnalysisTools initialized")
    
    # ==================== 簡單移動平均線 (SMA) ====================
    
    async def calculate_ma(self, data: List[float], period: int) -> List[float]:
        """
        計算簡單移動平均線 (Simple Moving Average)
        
        Args:
            data: 價格數據列表
            period: 週期
            
        Returns:
            MA 值列表（長度與輸入相同，前面部分為 None）
        """
        if len(data) < period:
            logger.warning(f"Data length {len(data)} < period {period}")
            return []
        
        result = [None] * (period - 1)
        
        for i in range(period - 1, len(data)):
            avg = sum(data[i - period + 1:i + 1]) / period
            result.append(round(avg, 2))
        
        return result
    
    # ==================== 指數移動平均線 (EMA) ====================
    
    async def calculate_ema(self, data: List[float], period: int) -> List[float]:
        """
        計算指數移動平均線 (Exponential Moving Average)
        
        Args:
            data: 價格數據列表
            period: 週期
            
        Returns:
            EMA 值列表
        """
        if len(data) < period:
            return []
        
        multiplier = 2 / (period + 1)
        result = [None] * (period - 1)
        
        # SMA for first value
        sma = sum(data[:period]) / period
        result.append(sma)
        
        for i in range(period, len(data)):
            ema = (data[i] - result[-1]) * multiplier + result[-1]
            result.append(round(ema, 2))
        
        return result
    
    # ==================== RSI (相對強弱指數) ====================
    
    async def calculate_rsi(
        self, 
        data: List[float], 
        period: int = 14,
        method: str = "wilders"
    ) -> List[float]:
        """
        計算 RSI (Relative Strength Index)
        
        Args:
            data: 價格數據列表（收盤價）
            period: RSI 週期（默認 14）
            method: 計算方法 (wilders/wilder 或 simple)
            
        Returns:
            RSI 值列表 (0-100)
        """
        if len(data) < period + 1:
            logger.warning(f"Data length {len(data)} < period+1 {period+1}")
            return []
        
        result = [None] * period
        
        # Calculate price changes
        changes = [data[i] - data[i-1] for i in range(1, len(data))]
        
        if method == "wilders":
            # Wilder's smoothing method
            gains = [c if c > 0 else 0 for c in changes]
            losses = [-c if c < 0 else 0 for c in changes]
            
            # First average
            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period
            
            for i in range(period, len(changes)):
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
                
                if avg_loss == 0:
                    rsi = 100
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                
                result.append(round(rsi, 2))
        else:
            # Simple RSI
            for i in range(period, len(changes)):
                period_gains = [g for g in changes[i-period:i] if g > 0]
                period_losses = [-l for l in changes[i-period:i] if l < 0]
                
                avg_gain = sum(period_gains) / period if period_gains else 0
                avg_loss = sum(period_losses) / period if period_losses else 0
                
                if avg_loss == 0:
                    rsi = 100
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                
                result.append(round(rsi, 2))
        
        return result
    
    # ==================== MACD ====================
    
    async def calculate_macd(
        self,
        data: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Dict[str, List[float]]:
        """
        計算 MACD (Moving Average Convergence Divergence)
        
        Args:
            data: 價格數據列表
            fast_period: 快線週期
            slow_period: 慢線週期
            signal_period: 信號線週期
            
        Returns:
            包含 macd, signal, histogram 的字典
        """
        if len(data) < slow_period + signal_period:
            logger.warning("Data too short for MACD calculation")
            return {"macd": [], "signal": [], "histogram": []}
        
        # Calculate EMAs
        fast_ema = await self.calculate_ema(data, fast_period)
        slow_ema = await self.calculate_ema(data, slow_period)
        
        # MACD line
        macd = []
        for i in range(len(data)):
            if fast_ema[i] is not None and slow_ema[i] is not None:
                macd.append(round(fast_ema[i] - slow_ema[i], 4))
            else:
                macd.append(None)
        
        # Signal line (EMA of MACD)
        valid_macd = [m for m in macd if m is not None]
        if len(valid_macd) < signal_period:
            return {"macd": macd, "signal": [], "histogram": []}
        
        signal = [None] * len(macd)
        signal_multiplier = 2 / (signal_period + 1)
        
        # First signal value
        signal_start_idx = None
        for i, m in enumerate(macd):
            if m is not None:
                if signal_start_idx is None:
                    signal_start_idx = i
                    signal.append(m)
                break
        
        # Calculate signal line
        if signal_start_idx is not None and len(valid_macd) >= signal_period:
            first_signal = sum(valid_macd[:signal_period]) / signal_period
            valid_idx = signal_start_idx
            for j in range(signal_period):
                if valid_idx + j < len(macd):
                    signal[valid_idx + j] = round(first_signal, 4)
            
            for i in range(signal_start_idx + signal_period, len(macd)):
                if macd[i] is not None and signal[i-1] is not None:
                    sig = (macd[i] - signal[i-1]) * signal_multiplier + signal[i-1]
                    signal.append(round(sig, 4))
        
        # Histogram
        histogram = []
        for i in range(len(macd)):
            if macd[i] is not None and signal[i] is not None:
                histogram.append(round(macd[i] - signal[i], 4))
            else:
                histogram.append(None)
        
        return {
            "macd": macd,
            "signal": signal,
            "histogram": histogram
        }
    
    # ==================== 布林帶 (Bollinger Bands) ====================
    
    async def calculate_bollinger_bands(
        self,
        data: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Dict[str, List[float]]:
        """
        計算布林帶 (Bollinger Bands)
        
        Args:
            data: 價格數據列表
            period: 移動平均週期
            std_dev: 標準差倍數
            
        Returns:
            包含 upper, middle, lower 的字典
        """
        if len(data) < period:
            return {"upper": [], "middle": [], "lower": []}
        
        middle = await self.calculate_ma(data, period)
        
        upper = [None] * len(data)
        lower = [None] * len(data)
        
        for i in range(period - 1, len(data)):
            subset = data[i - period + 1:i + 1]
            mean = middle[i]
            
            # Calculate standard deviation
            variance = sum((x - mean) ** 2 for x in subset) / period
            std = math.sqrt(variance)
            
            upper[i] = round(mean + std_dev * std, 2)
            lower[i] = round(mean - std_dev * std, 2)
        
        return {
            "upper": upper,
            "middle": middle,
            "lower": lower
        }
    
    # ==================== ATR (平均真實波幅) ====================
    
    async def calculate_atr(
        self,
        high: List[float],
        low: List[float],
        close: List[float],
        period: int = 14
    ) -> List[float]:
        """
        計算 ATR (Average True Range)
        
        Args:
            high: 最高價列表
            low: 最低價列表
            close: 收盤價列表
            period: ATR 週期
            
        Returns:
            ATR 值列表
        """
        if len(high) != len(low) != len(close) or len(high) < period + 1:
            return []
        
        # Calculate True Range
        tr = []
        for i in range(1, len(close)):
            h_l = high[i] - low[i]
            h_c = abs(high[i] - close[i-1])
            l_c = abs(low[i] - close[i-1])
            tr.append(max(h_l, h_c, l_c))
        
        # Calculate ATR
        if len(tr) < period:
            return []
        
        atr = [None] * (period + 1)
        avg_tr = sum(tr[:period]) / period
        atr.append(round(avg_tr, 4))
        
        for i in range(period, len(tr)):
            avg_tr = (avg_tr * (period - 1) + tr[i]) / period
            atr.append(round(avg_tr, 4))
        
        return atr
    
    # ==================== 支撐位和阻力位 ====================
    
    async def find_support_resistance(
        self,
        data: List[float],
        window: int = 5
    ) -> Dict[str, List[float]]:
        """
        識別支撐位和阻力位
        
        Args:
            data: 價格數據列表
            window: 局部極值窗口大小
            
        Returns:
            支撐位和阻力位列表
        """
        if len(data) < window * 2 + 1:
            return {"support": [], "resistance": []}
        
        support_levels = []
        resistance_levels = []
        
        for i in range(window, len(data) - window):
            # Check if local minimum (support): point <= all neighbors in window
            left_ok = all(data[i] <= data[j] for j in range(i - window, i))
            right_ok = all(data[i] <= data[j] for j in range(i + 1, i + window + 1))
            if left_ok and right_ok:
                support_levels.append(data[i])

            # Check if local maximum (resistance): point >= all neighbors in window
            left_ok_r = all(data[i] >= data[j] for j in range(i - window, i))
            right_ok_r = all(data[i] >= data[j] for j in range(i + 1, i + window + 1))
            if left_ok_r and right_ok_r:
                resistance_levels.append(data[i])
        
        # Cluster similar levels
        support_levels = self._cluster_levels(support_levels, tolerance=5.0)
        resistance_levels = self._cluster_levels(resistance_levels, tolerance=5.0)
        
        return {
            "support": sorted(support_levels),
            "resistance": sorted(resistance_levels, reverse=True)
        }
    
    def _cluster_levels(
        self, 
        levels: List[float], 
        tolerance: float = 5.0
    ) -> List[float]:
        """將接近的價格位聚類"""
        if not levels:
            return []
        
        sorted_levels = sorted(levels)
        clusters = []
        current_cluster = [sorted_levels[0]]
        
        for level in sorted_levels[1:]:
            if abs(level - current_cluster[-1]) <= tolerance:
                current_cluster.append(level)
            else:
                clusters.append(current_cluster)
                current_cluster = [level]
        
        clusters.append(current_cluster)
        
        # Return average of each cluster
        return [sum(c) / len(c) for c in clusters]
    
    # ==================== 趨勢判斷 ====================
    
    async def analyze_trend(
        self,
        data: List[float],
        short_period: int = 10,
        long_period: int = 30
    ) -> Dict[str, Any]:
        """
        分析價格趨勢
        
        Args:
            data: 價格數據列表
            short_period: 短期 MA 週期
            long_period: 長期 MA 週期
            
        Returns:
            趨勢分析結果
        """
        if len(data) < long_period:
            return {"trend": "insufficient_data", "strength": 0}
        
        short_ma = await self.calculate_ma(data, short_period)
        long_ma = await self.calculate_ma(data, long_period)
        
        # Get latest valid values
        valid_short = [v for v in short_ma if v is not None]
        valid_long = [v for v in long_ma if v is not None]
        
        if not valid_short or not valid_long:
            return {"trend": "insufficient_data", "strength": 0}
        
        current_short = valid_short[-1]
        current_long = valid_long[-1]
        
        # Calculate trend
        if current_short > current_long:
            trend = "uptrend"
            strength = min(100, (current_short - current_long) / current_long * 1000)
        elif current_short < current_long:
            trend = "downtrend"
            strength = min(100, (current_long - current_short) / current_long * 1000)
        else:
            trend = "sideways"
            strength = 0
        
        # Check trend direction (last 5 days)
        direction = "stable"
        if len(valid_short) >= 5:
            recent_change = valid_short[-1] - valid_short[-5]
            if recent_change > 0.5:
                direction = "accelerating"
            elif recent_change < -0.5:
                direction = "weakening"
        
        return {
            "trend": trend,
            "direction": direction,
            "strength": round(strength, 2),
            "short_ma": current_short,
            "long_ma": current_long,
            "gap": round(current_short - current_long, 2)
        }
    
    def __repr__(self) -> str:
        return "<AnalysisTools>"
