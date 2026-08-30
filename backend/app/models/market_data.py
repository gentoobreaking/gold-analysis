"""
Market Data Models
統一的市場數據模型定義
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class DataSource(str, Enum):
    """支持的數據源"""

    ALPHA_VANTAGE = "alpha_vantage"
    FINNHUB = "finnhub"
    FRED = "fred"
    YFINANCE = "yfinance"
    METALEXCHANGERATE = "metalexchangerate"


class SymbolType(str, Enum):
    """標的類型"""

    COMMODITY = "commodity"
    INDEX = "index"
    CURRENCY = "currency"
    CRYPTO = "crypto"
    STOCK = "stock"
    BOND = "bond"


class PriceData(BaseModel):
    """價格數據模型"""

    symbol: str = Field(..., description="標的代碼")
    price: float = Field(..., description="當前價格")
    currency: str = Field(default="USD", description="計價貨幣")
    timestamp: datetime = Field(..., description="數據時間戳")
    source: str = Field(..., description="數據來源")

    # 可選字段
    change: float | None = Field(None, description="價格變動")
    change_percent: float | None = Field(None, description="變動百分比")
    open: float | None = Field(None, description="開盤價")
    high: float | None = Field(None, description="最高價")
    low: float | None = Field(None, description="最低價")
    volume: float | None = Field(None, description="成交量")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "GC",
                "price": 2034.50,
                "currency": "USD",
                "timestamp": "2024-01-15T14:30:00Z",
                "source": "alpha_vantage",
                "change": 12.30,
                "change_percent": 0.61,
            }
        }


class HistoricalPriceData(BaseModel):
    """歷史價格數據模型"""

    symbol: str
    date: datetime
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    adjusted_close: float | None = None
    source: str | None = None


class EconomicIndicator(BaseModel):
    """經濟指標模型"""

    series_id: str = Field(..., description="FRED Series ID")
    name: str = Field(..., description="指標名稱")
    value: float = Field(..., description="當前值")
    date: datetime = Field(..., description="數據日期")
    unit: str | None = Field(None, description="單位")
    frequency: str | None = Field(None, description="頻率 (D/W/M)")
    source: str = Field(default="fred")


class MarketDataResponse(BaseModel):
    """市場數據響應模型"""

    success: bool
    data: dict | None = None
    error: str | None = None
    source: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now(timezone.utc))
