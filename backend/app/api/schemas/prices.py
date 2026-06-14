"""
Price data request/response schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ── Request Schemas ───────────────────────────────────────────────────────────

class PriceQueryParams(BaseModel):
    """Price query parameters"""
    symbol: str = Field(default="GOLD", description="資產符號")
    interval: str = Field(default="1h", description="時間間隔: 1m, 5m, 15m, 1h, 4h, 1d")
    start_time: Optional[datetime] = Field(None, description="開始時間")
    end_time: Optional[datetime] = Field(None, description="結束時間")
    limit: int = Field(default=100, le=1000, description="返回數量上限")


class HistoricalPricesRequest(BaseModel):
    """Historical prices request"""
    symbol: str = Field(default="GOLD", description="資產符號")
    interval: str = Field(default="1h", description="時間間隔")
    start_time: datetime = Field(..., description="開始時間")
    end_time: datetime = Field(..., description="結束時間")
    limit: int = Field(default=500, le=5000, description="返回數量上限")


# ── Response Schemas ──────────────────────────────────────────────────────────

class OHLCVData(BaseModel):
    """OHLCV (Open, High, Low, Close, Volume) data point"""
    timestamp: datetime = Field(..., description="時間戳")
    open: float = Field(..., description="開盤價")
    high: float = Field(..., description="最高價")
    low: float = Field(..., description="最低價")
    close: float = Field(..., description="收盤價")
    volume: float = Field(..., description="成交量")


class PriceData(BaseModel):
    """Single price data point"""
    symbol: str = Field(..., description="資產符號")
    price: float = Field(..., description="當前價格")
    currency: str = Field(default="USD", description="貨幣")
    timestamp: datetime = Field(..., description="時間戳")
    source: Optional[str] = Field(None, description="數據源")


class CurrentPriceResponse(BaseModel):
    """Current gold price response"""
    symbol: str = Field(..., description="資產符號")
    price: float = Field(..., description="黃金價格（美元/盎司）")
    price_cny: float = Field(..., description="黃金價格（人民幣/克）")
    price_twd: float = Field(..., description="黃金價格（新台幣/克）")
    currency_rates: Dict[str, float] = Field(..., description="匯率")
    timestamp: datetime = Field(..., description="時間戳")
    change_24h: float = Field(..., description="24小時價格變化")
    change_percent_24h: float = Field(..., description="24小時價格變化百分比")
    high_24h: float = Field(..., description="24小時最高價")
    low_24h: float = Field(..., description="24小時最低價")
    volume_24h: float = Field(..., description="24小時成交量")


class HistoricalPricesResponse(BaseModel):
    """Historical prices response"""
    symbol: str = Field(..., description="資產符號")
    interval: str = Field(..., description="時間間隔")
    data: List[OHLCVData] = Field(..., description="OHLCV 數據列表")
    start_time: datetime = Field(..., description="開始時間")
    end_time: datetime = Field(..., description="結束時間")
    count: int = Field(..., description="數據點數量")


class TechnicalIndicatorsResponse(BaseModel):
    """Technical indicators response"""
    symbol: str = Field(..., description="資產符號")
    timestamp: datetime = Field(..., description="時間戳")
    indicators: Dict[str, Any] = Field(..., description="技術指標")
    signals: Dict[str, str] = Field(..., description="交易信號")


class PriceAlertResponse(BaseModel):
    """Price alert with current comparison"""
    symbol: str = Field(..., description="資產符號")
    current_price: float = Field(..., description="當前價格")
    target_price: float = Field(..., description="目標價格")
    direction: str = Field(..., description="方向: above 或 below")
    distance_percent: float = Field(..., description="距離目標百分比")
    triggered: bool = Field(..., description="是否已觸發")
