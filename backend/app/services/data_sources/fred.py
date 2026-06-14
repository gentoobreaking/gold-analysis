"""
FRED (Federal Reserve Economic Data) API Adapter
利率、通脹數據
文檔: https://fred.stlouisfed.org/docs/api/fred/
"""

from datetime import datetime
from typing import Optional

import httpx

from .base import BaseDataSource, HistoricalData, MarketData
from ..config import get_api_key, get_api_settings


class FREDAdapter(BaseDataSource):
    """FRED 數據源適配器"""
    
    # 常用 FRED series ID
    SERIES_MAP = {
        # 利率
        "FEDFUNDS": "Federal Funds Rate (Effective)",
        "DFF": "Federal Funds Rate (Daily)",
        "DTB3": "3-Month Treasury Bill",
        "DTB6": "6-Month Treasury Bill",
        "DGS10": "10-Year Treasury Rate",
        "DGS30": "30-Year Treasury Rate",
        "TEDRATE": "TED Spread",
        
        # 通脹
        "CPIAUCSL": "CPI (All Urban Consumers)",
        "CPILFESL": "Core CPI (Less Food & Energy)",
        "PCEPI": "PCE Price Index",
        "PCECTPI": "Core PCE Price Index",
        
        # 黃金相關
        "GOLDAMGBD228NLBM": "Gold Fixing Price (London)",
        "GOLDPMGBD228NLBM": "Gold Fixing Price (PM, London)",
        
        # 美元指數
        "DTWEXBGS": "Trade Weighted USD Index (Broad)",
        "DTWEXM": "Trade Weighted USD Index (Major)",
        
        # 實際利率
        "REAINTRATREARAT10Y": "Real 10-Year Treasury Rate",
    }
    
    def __init__(self, api_key: Optional[str] = None):
        settings = get_api_settings()
        super().__init__(
            api_key=api_key or get_api_key("fred"),
            base_url=settings.fred_base_url,
        )
    
    @property
    def name(self) -> str:
        return "fred"
    
    async def get_price(self, symbol: str) -> MarketData:
        """
        取得最新觀測值
        
        FRED 的 series 並非實時價格，而是經濟數據
        對於黃金，自動映射到 GOLDAMGBD228NLBM
        對於美元指數，映射到 DTWEXBGS
        """
        series_id = self._resolve_series(symbol)
        
        if not self.api_key or self.api_key == "":
            raise ValueError(
                "FRED API key 未設定。請在 .env 設定 FRED_API_KEY。"
                "免費註冊: https://fred.stlouisfed.org/docs/api/api_key.html"
            )
        
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "limit": 1,
            "sort_order": "desc",
        }
        
        data = await self._request(
            method="GET",
            url=f"{self.base_url}/observations/get",
            params=params,
        )
        
        observations = data.get("observations", [])
        if not observations:
            raise ValueError(f"FRED 未找到 series {series_id} 的數據")
        
        latest = observations[0]
        date_str = latest["date"]
        value_str = latest["value"]
        
        # FRED 使用 "." 表示缺失值
        if value_str == ".":
            raise ValueError(f"FRED series {series_id} 最新值為缺失數據")
        
        return MarketData(
            symbol=series_id,
            value=float(value_str),
            timestamp=datetime.strptime(date_str, "%Y-%m-%d"),
            currency="USD",
            source=self.name,
            metadata={
                "series_name": self.SERIES_MAP.get(series_id, series_id),
                "realtime_start": latest.get("realtime_start"),
                "realtime_end": latest.get("realtime_end"),
            },
        )
    
    async def get_historical(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[HistoricalData]:
        """
        取得歷史觀測值
        
        對於利率和通脹數據，返回日/周/月頻率
        """
        series_id = self._resolve_series(symbol)
        
        if not self.api_key or self.api_key == "":
            raise ValueError(
                "FRED API key 未設定。請在 .env 設定 FRED_API_KEY。"
            )
        
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start.strftime("%Y-%m-%d"),
            "observation_end": end.strftime("%Y-%m-%d"),
        }
        
        data = await self._request(
            method="GET",
            url=f"{self.base_url}/observations/get",
            params=params,
        )
        
        observations = data.get("observations", [])
        results = []
        
        for obs in observations:
            value_str = obs["value"]
            if value_str != ".":  # 跳過缺失值
                results.append(
                    HistoricalData(
                        symbol=series_id,
                        date=datetime.strptime(obs["date"], "%Y-%m-%d"),
                        close=float(value_str),
                        source=self.name,
                    )
                )
        
        return sorted(results, key=lambda x: x.date)
    
    async def search_series(self, text: str, limit: int = 20) -> list[dict]:
        """
        搜索 FRED series
        
        用於查找感興趣的經濟指標
        """
        if not self.api_key or self.api_key == "":
            raise ValueError(
                "FRED API key 未設定。請在 .env 設定 FRED_API_KEY。"
            )
        
        params = {
            "search_text": text,
            "api_key": self.api_key,
            "file_type": "json",
            "limit": limit,
        }
        
        data = await self._request(
            method="GET",
            url=f"{self.base_url}/series/search",
            params=params,
        )
        
        return data.get("seriess", [])
    
    async def get_series_info(self, symbol: str) -> dict:
        """
        取得 series 詳細信息
        """
        if not self.api_key or self.api_key == "":
            raise ValueError(
                "FRED API key 未設定。請在 .env 設定 FRED_API_KEY。"
            )
        
        params = {
            "series_id": symbol,
            "api_key": self.api_key,
            "file_type": "json",
        }
        
        data = await self._request(
            method="GET",
            url=f"{self.base_url}/series",
            params=params,
        )
        
        return data.get("seriess", [{}])[0]
    
    def _resolve_series(self, symbol: str) -> str:
        """
        解析 symbol 到 FRED series ID
        
        支持別名:
        - GOLD/GC -> GOLDAMGBD228NLBM (倫敦金下午定盤價)
        - DXY/DX -> DTWEXBGS (美元指數 broad)
        - CPI -> CPIAUCSL
        - 10Y/10YR -> DGS10
        """
        symbol_upper = symbol.upper()
        
        if symbol_upper in self.SERIES_MAP:
            return symbol_upper
        
        aliases = {
            "GOLD": "GOLDAMGBD228NLBM",
            "GC": "GOLDAMGBD228NLBM",
            "XAU": "GOLDAMGBD228NLBM",
            "DXY": "DTWEXBGS",
            "DX": "DTWEXBGS",
            "USDX": "DTWEXBGS",
            "CPI": "CPIAUCSL",
            "CORE_CPI": "CPILFESL",
            "PCE": "PCEPI",
            "10Y": "DGS10",
            "10YR": "DGS10",
            "30Y": "DGS30",
            "30YR": "DGS30",
            "FED_RATE": "FEDFUNDS",
            "FFR": "FEDFUNDS",
        }
        
        return aliases.get(symbol_upper, symbol_upper)
