"""
Alpha Vantage API Adapter
黃金價格、美元指數
文檔: https://www.alphavantage.co/documentation/
"""

from datetime import datetime
from typing import Optional

from .base import BaseDataSource, HistoricalData, MarketData
from ..config import get_api_key, get_api_settings


class AlphaVantageAdapter(BaseDataSource):
    """Alpha Vantage 數據源適配器"""
    
    # 符號映射
    SYMBOL_MAP = {
        "GC": "GOLD",           # 黃金期貨
        "SI": "SILVER",         # 白銀期貨
        "DX": "DXY",            # 美元指數
        "EURUSD": "EUR/USD",    # 歐元美元
        "BTC": "BTC/USD",       # 比特幣
    }
    
    # 特殊函數映射
    FUNCTION_MAP = {
        "GOLD": "function=TOP_25_GAINERS_LOSERS",  # 使用commodity作示例
        "SILVER": "function=TOP_25_GAINERS_LOSERS",
        "DXY": "function=REAL_EFFECTIVE_EXCHANGE_RATE",
        "EUR/USD": "function=CURRENCY_EXCHANGE_RATE",
        "BTC/USD": "function=CURRENCY_EXCHANGE_RATE",
    }
    
    def __init__(self, api_key: Optional[str] = None):
        settings = get_api_settings()
        super().__init__(
            api_key=api_key or get_api_key("alpha_vantage"),
            base_url=settings.alpha_vantage_base_url,
        )
        self.rate_limit_calls = settings.alpha_vantage_rate_limit
        self.rate_limit_period = settings.alpha_vantage_rate_period
    
    @property
    def name(self) -> str:
        return "alpha_vantage"
    
    async def get_price(self, symbol: str) -> MarketData:
        """
        取得即時價格
        
        支持符號:
        - GC: 黃金 (USD/oz)
        - SI: 白銀 (USD/oz)
        - DX: 美元指數
        
        實現說明：
        Alpha Vantage 免費版不支持 Commodity，直接報錯提示用戶
        付費版或替代方案見 README
        """
        # 檢查 API key
        if not self.api_key or self.api_key == "":
            raise ValueError(
                "Alpha Vantage API key 未設定。請在 .env 設定 ALPHA_VANTAGE_API_KEY。"
                "或使用 GOLD_API_KEY 配置替代數據源。"
            )
        
        # 黃金/白銀實時報價
        if symbol.upper() in ("GC", "GOLD"):
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": "GCUSD",  # Gold/USD
                "apikey": self.api_key,
            }
        elif symbol.upper() in ("SI", "SILVER"):
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": "SIUSD",
                "apikey": self.api_key,
            }
        elif symbol.upper() in ("DX", "DXY", "USDX"):
            # 美元指數
            params = {
                "function": "DXY",
                "interval": "5min",
                "apikey": self.api_key,
            }
        else:
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol.upper(),
                "apikey": self.api_key,
            }
        
        data = await self._request(
            method="GET",
            url=self.base_url,
            params=params,
            rate_limit_calls=self.rate_limit_calls,
            rate_limit_period=self.rate_limit_period,
        )
        
        # 解析響應
        if "Note" in data:
            raise RuntimeError(
                f"Alpha Vantage 速率限制已觸發。免費版限制 5 calls/min。"
                "請稍後再試或升級至付費版。"
            )
        if "Error Message" in data:
            raise ValueError(f"Alpha Vantage API 錯誤: {data['Error Message']}")
        
        # 解析 GLOBAL_QUOTE
        if "Global Quote" in data and data["Global Quote"]:
            quote = data["Global Quote"]
            return MarketData(
                symbol=symbol.upper(),
                value=float(quote.get("05. price", 0)),
                timestamp=datetime.fromisoformat(
                    quote.get("07. latest trading day", datetime.now().date().isoformat())
                ),
                currency="USD",
                source=self.name,
                metadata={
                    "open": float(quote.get("02. open", 0)) or None,
                    "high": float(quote.get("03. high", 0)) or None,
                    "low": float(quote.get("04. low", 0)) or None,
                    "volume": float(quote.get("06. volume", 0)) or None,
                },
            )
        
        # 解析 Commodities (黃金白銀實時)
        if "commodity" in data:
            return MarketData(
                symbol=symbol.upper(),
                value=float(data["commodity"].get("price", 0)),
                timestamp=datetime.now(),
                currency="USD",
                source=self.name,
            )
        
        # 美元指數
        if "data" in data and data["data"]:
            item = data["data"][0]
            return MarketData(
                symbol="DXY",
                value=float(item.get("value", 0)),
                timestamp=datetime.fromisoformat(item.get("date", datetime.now().isoformat())),
                currency="USD",
                source=self.name,
            )
        
        raise ValueError(f"Alpha Vantage 未返回有效數據: {data}")
    
    async def get_historical(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[HistoricalData]:
        """
        取得歷史數據
        
        支持: GC (黃金), SI (白銀), DXY (美元指數)
        """
        if not self.api_key or self.api_key == "":
            raise ValueError(
                "Alpha Vantage API key 未設定。請在 .env 設定 ALPHA_VANTAGE_API_KEY。"
            )
        
        # 確定時間序列函數
        if symbol.upper() in ("GC", "GOLD"):
            function = "TIME_SERIES_DAILY_ADJUSTED"
            market = "physical"
        elif symbol.upper() in ("SI", "SILVER"):
            function = "TIME_SERIES_DAILY_ADJUSTED"
            market = "physical"
        elif symbol.upper() in ("DX", "DXY"):
            function = "DXY_SERIES"  # 假設的美元指數時間序列
            market = "index"
        else:
            function = "TIME_SERIES_DAILY_ADJUSTED"
            market = "stock"
        
        params = {
            "function": function,
            "symbol": symbol.upper(),
            "outputsize": "full",
            "apikey": self.api_key,
        }
        
        data = await self._request(
            method="GET",
            url=self.base_url,
            params=params,
            rate_limit_calls=self.rate_limit_calls,
            rate_limit_period=self.rate_limit_period,
        )
        
        if "Note" in data:
            raise RuntimeError(
                "Alpha Vantage 速率限制已觸發。免費版限制 5 calls/min。"
            )
        
        # 解析時間序列
        results = []
        time_series_key = None
        for key in data:
            if "Time Series" in key or "Daily" in key:
                time_series_key = key
                break
        
        if time_series_key:
            for date_str, values in data[time_series_key].items():
                date = datetime.fromisoformat(date_str)
                if start <= date <= end:
                    results.append(
                        HistoricalData(
                            symbol=symbol.upper(),
                            date=date,
                            open=float(values.get("1. open", 0)) or None,
                            high=float(values.get("2. high", 0)) or None,
                            low=float(values.get("3. low", 0)) or None,
                            close=float(values.get("4. close", 0)) or None,
                            volume=float(values.get("6. volume", 0)) or None,
                            source=self.name,
                        )
                    )
        
        return sorted(results, key=lambda x: x.date)
