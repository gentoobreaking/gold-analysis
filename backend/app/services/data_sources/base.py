"""
Base Data Source Adapter
統一的基類，定義所有適配器的標準接口
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import httpx

from ..config import get_api_settings


@dataclass
class MarketData:
    """市場數據統一模型"""
    symbol: str
    value: float
    timestamp: datetime
    currency: Optional[str] = None
    source: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class HistoricalData:
    """歷史數據統一模型"""
    symbol: str
    date: datetime
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    source: Optional[str] = None


class BaseDataSource(ABC):
    """數據源適配器基類"""
    
    # 類級別速率限制追蹤（各子類實例共享）
    _rate_limit_tracker: dict[str, list[float]] = {}
    _rate_limit_lock = asyncio.Lock()
    
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.settings = get_api_settings()
        self._cache: dict[str, tuple[Any, float]] = {}  # key -> (data, timestamp)
        
    @property
    @abstractmethod
    def name(self) -> str:
        """數據源名稱"""
        pass
    
    @abstractmethod
    async def get_price(self, symbol: str) -> MarketData:
        """取得即時價格"""
        pass
    
    @abstractmethod
    async def get_historical(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[HistoricalData]:
        """取得歷史數據"""
        pass
    
    async def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] = None,
        rate_limit_calls: int = 5,
        rate_limit_period: int = 60,
    ) -> dict[str, Any]:
        """
        統一 HTTP 請求方法，帶重試、限流、緩存
        """
        # 檢查緩存
        cache_key = f"{method}:{url}:{str(params)}"
        if cache_key in self._cache:
            cached_data, cached_time = self._cache[cache_key]
            if time.time() - cached_time < self.settings.cache_ttl:
                return cached_data
        
        # 速率限制檢查
        await self._check_rate_limit(rate_limit_calls, rate_limit_period)
        
        # 重試機制
        last_error = None
        for attempt in range(self.settings.max_retries):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    # 寫入緩存
                    self._cache[cache_key] = (data, time.time())
                    return data
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # 觸發速率限制，等待後重試
                    wait_time = int(e.response.headers.get("Retry-After", 60))
                    await asyncio.sleep(wait_time)
                    continue
                last_error = e
                if attempt < self.settings.max_retries - 1:
                    await asyncio.sleep(self.settings.retry_delay * (attempt + 1))
                    continue
                raise
                
            except httpx.RequestError as e:
                last_error = e
                if attempt < self.settings.max_retries - 1:
                    await asyncio.sleep(self.settings.retry_delay * (attempt + 1))
                    continue
                raise
                
            except Exception as e:
                last_error = e
                if attempt < self.settings.max_retries - 1:
                    await asyncio.sleep(self.settings.retry_delay * (attempt + 1))
                    continue
                raise
        
        raise last_error or Exception("Request failed after retries")
    
    async def _check_rate_limit(self, calls: int, period: int):
        """速率限制：滑動窗口算法"""
        async with self._rate_limit_lock:
            now = time.time()
            key = f"{self.name}:{id(self)}"
            
            if key not in self._rate_limit_tracker:
                self._rate_limit_tracker[key] = []
            
            # 清理過期的時間戳
            self._rate_limit_tracker[key] = [
                ts for ts in self._rate_limit_tracker[key]
                if now - ts < period
            ]
            
            if len(self._rate_limit_tracker[key]) >= calls:
                oldest = self._rate_limit_tracker[key][0]
                wait_time = period - (now - oldest)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            
            self._rate_limit_tracker[key].append(now)
    
    def clear_cache(self):
        """清除緩存"""
        self._cache.clear()
