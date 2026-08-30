"""Price Service - 價格數據業務邏輯

Mock 實作供測試/開發環境使用。正式環境可替換為真實數據源（yfinance/Alpha Vantage 等）。
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class PriceService:
    """價格服務"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_current_price(self, symbol: str = "GOLD") -> dict[str, Any]:
        """獲取當前價格（mock）。"""
        if symbol.upper() != "GOLD":
            raise ValueError(f"不支持的資產符號: {symbol}")

        base_price = 2000.0 + random.uniform(-50, 50)
        now = datetime.now(timezone.utc)

        return {
            "symbol": "GOLD",
            "price": round(base_price, 2),
            "price_cny": round(base_price * 7.2 / 31.1035, 2),  # USD/oz -> CNY/g
            "price_twd": round(base_price * 32.0 / 31.1035, 2),  # USD/oz -> TWD/g
            "currency_rates": {
                "USD_CNY": 7.2,
                "USD_TWD": 32.0,
            },
            "timestamp": now,
            "change_24h": round(random.uniform(-30, 30), 2),
            "change_percent_24h": round(random.uniform(-1.5, 1.5), 2),
            "high_24h": round(base_price + random.uniform(5, 20), 2),
            "low_24h": round(base_price - random.uniform(5, 20), 2),
            "volume_24h": random.randint(100000, 500000),
        }

    async def get_historical_prices(
        self,
        symbol: str = "GOLD",
        interval: str = "1h",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """獲取歷史價格（mock）。"""
        if symbol.upper() != "GOLD":
            raise ValueError(f"不支持的資產符號: {symbol}")

        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(days=7)

        # 根據 interval 計算間隔
        interval_map = {
            "1m": timedelta(minutes=1),
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "1h": timedelta(hours=1),
            "4h": timedelta(hours=4),
            "1d": timedelta(days=1),
        }
        delta = interval_map.get(interval, timedelta(hours=1))

        data: list[dict[str, Any]] = []
        current = start_time
        base_price = 2000.0

        for i in range(min(limit, 500)):
            if current > end_time:
                break
            # 模擬價格隨機游走
            change = random.uniform(-10, 10)
            base_price = max(1500, min(2500, base_price + change))
            high = base_price + random.uniform(0, 5)
            low = base_price - random.uniform(0, 5)
            open_price = base_price + random.uniform(-2, 2)
            close_price = base_price + random.uniform(-2, 2)
            volume = random.randint(1000, 10000)

            data.append({
                "timestamp": current,
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close_price, 2),
                "volume": float(volume),
            })
            current += delta

        return {
            "symbol": "GOLD",
            "interval": interval,
            "data": data,
            "start_time": start_time,
            "end_time": end_time,
            "count": len(data),
        }

    async def get_technical_indicators(
        self,
        symbol: str = "GOLD",
        period: int = 14,
    ) -> dict[str, Any]:
        """獲取技術指標（mock）。"""
        if symbol.upper() != "GOLD":
            raise ValueError(f"不支持的資產符號: {symbol}")

        rsi = round(random.uniform(30, 70), 2)
        macd = round(random.uniform(-5, 5), 4)
        bb_upper = 2050.0
        bb_lower = 1950.0

        return {
            "symbol": "GOLD",
            "timestamp": datetime.now(timezone.utc),
            "indicators": {
                "rsi": rsi,
                "macd": macd,
                "bb_upper": bb_upper,
                "bb_middle": (bb_upper + bb_lower) / 2,
                "bb_lower": bb_lower,
                "sma_20": 2000.0,
                "ema_20": 2001.0,
            },
            "signals": {
                "rsi": "neutral" if 40 <= rsi <= 60 else ("overbought" if rsi > 60 else "oversold"),
                "macd": "bullish" if macd > 0 else "bearish",
                "bb": "neutral",
            },
        }