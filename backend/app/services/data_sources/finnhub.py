"""
Finnhub API Adapter
實時報價、公司新聞
文檔: https://finnhub.io/docs/api
"""

from datetime import datetime, timedelta
from typing import Optional

import httpx

from .base import BaseDataSource, HistoricalData, MarketData
from ..config import get_api_key, get_api_settings


class FinnhubAdapter(BaseDataSource):
    """Finnhub 數據源適配器"""
    
    def __init__(self, api_key: Optional[str] = None):
        settings = get_api_settings()
        super().__init__(
            api_key=api_key or get_api_key("finnhub"),
            base_url=settings.finnhub_base_url,
        )
    
    @property
    def name(self) -> str:
        return "finnhub"
    
    async def get_price(self, symbol: str) -> MarketData:
        """
        取得即時報價
        
        Finnhub 支持:
        - 股票: AAPL, GOOG, MSFT...
        - 加密: BINANCE:BTCUSDT, BINANCE:ETHUSDT...
        - 外匯: OANDA:EURUSD
        
        注意: Finnhub 免費版實時報價有延遲
        """
        if not self.api_key or self.api_key == "":
            raise ValueError(
                "Finnhub API key 未設定。請在 .env 設定 FINNHUB_API_KEY。"
            )
        
        params = {
            "symbol": symbol.upper(),
        }
        headers = {
            "X-Finnhub-Token": self.api_key,
        }
        
        data = await self._request(
            method="GET",
            url=f"{self.base_url}/quote",
            params=params,
            headers=headers,
        )
        
        if "c" not in data or not data["c"]:
            raise ValueError(f"Finnhub 未找到符號 {symbol} 或 API 限流")
        
        return MarketData(
            symbol=symbol.upper(),
            value=data["c"],  # current price
            timestamp=datetime.fromtimestamp(data["t"]),
            currency="USD",
            source=self.name,
            metadata={
                "open": data["o"] or None,
                "high": data["h"] or None,
                "low": data["l"] or None,
                "previous_close": data["pc"] or None,
                "change_percent": ((data["c"] - data["pc"]) / data["pc"] * 100) if data["pc"] else None,
            },
        )
    
    async def get_historical(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[HistoricalData]:
        """
        取得 Candlestick 歷史數據
        
        Finnhub 提供:
        - 股票/加密/外匯的日線/周線/月線K線
        """
        if not self.api_key or self.api_key == "":
            raise ValueError(
                "Finnhub API key 未設定。請在 .env 設定 FINNHUB_API_KEY。"
            )
        
        params = {
            "symbol": symbol.upper(),
            "resolution": "D",  # 日線
            "from": int(start.timestamp()),
            "to": int(end.timestamp()),
        }
        headers = {
            "X-Finnhub-Token": self.api_key,
        }
        
        data = await self._request(
            method="GET",
            url=f"{self.base_url}/stock/candle",
            params=params,
            headers=headers,
        )
        
        if data.get("s") != "ok":
            raise ValueError(f"Finnhub 未返回有效的K線數據: {data}")
        
        results = []
        timestamps = data.get("t", [])
        opens = data.get("o", [])
        highs = data.get("h", [])
        lows = data.get("l", [])
        closes = data.get("c", [])
        volumes = data.get("v", [])
        
        for i, ts in enumerate(timestamps):
            date = datetime.fromtimestamp(ts)
            if start <= date <= end:
                results.append(
                    HistoricalData(
                        symbol=symbol.upper(),
                        date=date,
                        open=opens[i] if i < len(opens) else None,
                        high=highs[i] if i < len(highs) else None,
                        low=lows[i] if i < len(lows) else None,
                        close=closes[i] if i < len(closes) else None,
                        volume=volumes[i] if i < len(volumes) else None,
                        source=self.name,
                    )
                )
        
        return sorted(results, key=lambda x: x.date)
    
    async def get_company_news(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        取得公司新聞
        
        黃金相關: GLD, GOLD, NEM, AU
        """
        if not self.api_key or self.api_key == "":
            raise ValueError(
                "Finnhub API key 未設定。請在 .env 設定 FINNHUB_API_KEY。"
            )
        
        start_date = start or (datetime.now() - timedelta(days=7))
        end_date = end or datetime.now()
        
        params = {
            "symbol": symbol.upper(),
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d"),
        }
        headers = {
            "X-Finnhub-Token": self.api_key,
        }
        
        data = await self._request(
            method="GET",
            url=f"{self.base_url}/news",
            params=params,
            headers=headers,
        )
        
        if not isinstance(data, list):
            raise ValueError(f"Finnhub 新聞 API 返回異常: {data}")
        
        return data[:limit]
    
    async def get_market_news(self, category: str = "general") -> list[dict]:
        """
        取得市場新聞
        
        categories: general, forex, crypto, merger
        """
        if not self.api_key or self.api_key == "":
            raise ValueError(
                "Finnhub API key 未設定。請在 .env 設定 FINNHUB_API_KEY。"
            )
        
        params = {
            "category": category,
        }
        headers = {
            "X-Finnhub-Token": self.api_key,
        }
        
        data = await self._request(
            method="GET",
            url=f"{self.base_url}/news",
            params=params,
            headers=headers,
        )
        
        if not isinstance(data, list):
            raise ValueError(f"Finnhub 新聞 API 返回異常: {data}")
        
        return data
