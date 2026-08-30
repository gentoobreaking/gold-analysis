"""Price Service - 價格數據業務邏輯

從共享 PostgreSQL (core.daily_prices) 讀取真實價格數據。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.daily_price import DailyPrice
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# USD/oz -> CNY/g and TWD/g conversion factors (1 troy ounce = 31.1035 grams)
GRAMS_PER_OUNCE = 31.1035
USD_CNY_RATE = 7.2
USD_TWD_RATE = 32.0


class PriceService:
    """價格服務 - 從 PostgreSQL 讀取價格數據"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_current_price(self, symbol: str = "GOLD") -> dict[str, Any]:
        """從 core.daily_prices 獲取當前價格。"""
        symbol = symbol.upper()
        if symbol != "GOLD":
            raise ValueError(f"不支持的資產符號: {symbol}")

        # Get latest price from core.daily_prices
        result = await self.session.execute(
            select(DailyPrice)
            .where(DailyPrice.symbol == "GOLD")
            .order_by(DailyPrice.trade_date.desc())
            .limit(1)
        )
        latest = result.scalars().first()

        if latest is None:
            raise ValueError(f"無 {symbol} 價格數據")

        current_price = float(latest.close)

        # Get previous day for 24h change
        prev_result = await self.session.execute(
            select(DailyPrice)
            .where(DailyPrice.symbol == "GOLD")
            .order_by(DailyPrice.trade_date.desc())
            .offset(1)
            .limit(1)
        )
        prev = prev_result.scalars().first()
        prev_close = float(prev.close) if prev else current_price

        change_24h = current_price - prev_close
        change_percent_24h = (change_24h / prev_close * 100) if prev_close else 0.0

        return {
            "symbol": "GOLD",
            "price": round(current_price, 2),
            "price_cny": round(current_price * USD_CNY_RATE / GRAMS_PER_OUNCE, 2),
            "price_twd": round(current_price * USD_TWD_RATE / GRAMS_PER_OUNCE, 2),
            "currency_rates": {
                "USD_CNY": USD_CNY_RATE,
                "USD_TWD": USD_TWD_RATE,
            },
            "timestamp": datetime.combine(latest.trade_date, datetime.min.time()).replace(
                tzinfo=timezone.utc
            ),
            "change_24h": round(change_24h, 2),
            "change_percent_24h": round(change_percent_24h, 2),
            "high_24h": round(float(latest.high), 2),
            "low_24h": round(float(latest.low), 2),
            "volume_24h": float(latest.volume or 0),
        }

    async def get_historical_prices(
        self,
        symbol: str = "GOLD",
        interval: str = "1d",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """從 core.daily_prices 獲取歷史價格數據。"""
        symbol = symbol.upper()
        if symbol != "GOLD":
            raise ValueError(f"不支持的資產符號: {symbol}")

        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(days=30)

        # Convert datetime to date for comparison
        end_date = end_time.date()
        start_date = start_time.date()

        query = (
            select(DailyPrice)
            .where(DailyPrice.symbol == "GOLD")
            .where(DailyPrice.trade_date >= start_date)
            .where(DailyPrice.trade_date <= end_date)
            .order_by(DailyPrice.trade_date.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        rows: list[DailyPrice] = result.scalars().all()
        rows.reverse()  # oldest first

        data: list[dict[str, Any]] = []
        for r in rows:
            ts = datetime.combine(r.trade_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            data.append(
                {
                    "timestamp": ts,
                    "open": float(r.open) if r.open else 0.0,
                    "high": float(r.high) if r.high else 0.0,
                    "low": float(r.low) if r.low else 0.0,
                    "close": float(r.close) if r.close else 0.0,
                    "volume": float(r.volume or 0),
                }
            )

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
        """從 core.daily_prices 計算技術指標。"""
        symbol = symbol.upper()
        if symbol != "GOLD":
            raise ValueError(f"不支持的資產符號: {symbol}")

        # Fetch recent prices for indicator calculation
        result = await self.session.execute(
            select(DailyPrice)
            .where(DailyPrice.symbol == "GOLD")
            .order_by(DailyPrice.trade_date.desc())
            .limit(period + 50)
        )
        rows = result.scalars().all()
        rows.reverse()  # oldest first

        if not rows:
            raise ValueError(f"無 {symbol} 價格數據")

        closes = [float(r.close) for r in rows if r.close]
        latest = rows[-1]
        current_price = float(latest.close)

        # Compute RSI
        gains, losses = [], []
        for i in range(1, len(closes)):
            delta = closes[i] - closes[i - 1]
            if delta > 0:
                gains.append(delta)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(-delta)

        avg_gain = (
            sum(gains[-period:]) / period
            if len(gains) >= period
            else sum(gains) / len(gains)
            if gains
            else 0
        )
        avg_loss = (
            sum(losses[-period:]) / period
            if len(losses) >= period
            else sum(losses) / len(losses)
            if losses
            else 0
        )
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi = round(100 - (100 / (1 + rs)), 2)

        # Compute MACD (12, 26, 9)
        ema_fast = closes[-1] if closes else 0.0
        ema_slow = closes[-1] if closes else 0.0
        k_fast = 2 / (12 + 1)
        k_slow = 2 / (26 + 1)
        for c in closes:
            ema_fast = ema_fast + k_fast * (c - ema_fast)
            ema_slow = ema_slow + k_slow * (c - ema_slow)
        macd_line = ema_fast - ema_slow
        signal_line = macd_line  # simplified single-value signal line
        macd_hist = round(macd_line - signal_line, 4)

        # Bollinger Bands (20-period)
        recent_closes = closes[-20:] if len(closes) >= 20 else closes
        sma_20 = sum(recent_closes) / len(recent_closes) if recent_closes else 0.0
        variance = (
            sum((c - sma_20) ** 2 for c in recent_closes) / len(recent_closes)
            if recent_closes
            else 0
        )
        std = variance**0.5
        bb_upper = round(sma_20 + 2 * std, 2)
        bb_lower = round(sma_20 - 2 * std, 2)

        # EMA 20
        ema_20 = closes[-1] if closes else 0.0
        k_ema = 2 / (20 + 1)
        for c in closes:
            ema_20 = ema_20 + k_ema * (c - ema_20)
        ema_20 = round(ema_20, 2)
        sma_20 = round(sma_20, 2)

        return {
            "symbol": "GOLD",
            "timestamp": datetime.now(timezone.utc),
            "indicators": {
                "rsi": rsi,
                "macd": macd_hist,
                "bb_upper": bb_upper,
                "bb_middle": round((bb_upper + bb_lower) / 2, 2),
                "bb_lower": bb_lower,
                "sma_20": sma_20,
                "ema_20": ema_20,
            },
            "signals": {
                "rsi": "neutral" if 40 <= rsi <= 60 else ("overbought" if rsi > 60 else "oversold"),
                "macd": "bullish" if macd_hist > 0 else "bearish",
                "bb": "overbought"
                if current_price > bb_upper
                else ("oversold" if current_price < bb_lower else "neutral"),
            },
        }

    async def convert_currency(
        self,
        amount: float,
        from_currency: str,
        to_currency: str,
    ) -> float:
        """貨幣轉換（使用固定匯率）。"""
        rates = {
            "USD": 1.0,
            "CNY": 1 / USD_CNY_RATE,
            "TWD": 1 / USD_TWD_RATE,
            "EUR": 0.85,
            "JPY": 150.0,
            "GBP": 0.75,
        }
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if from_currency not in rates or to_currency not in rates:
            raise ValueError(f"不支持的貨幣: {from_currency} 或 {to_currency}")

        usd_amount = amount * rates[from_currency]
        return round(usd_amount / rates[to_currency], 4)
