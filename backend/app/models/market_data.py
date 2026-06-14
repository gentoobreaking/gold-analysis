"""
Market Data Models
統一的市場數據模型定義
"""

from datetime import datetime
from enum import Enum
from typing import Optional

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
    change: Optional[float] = Field(None, description="價格變動")
    change_percent: Optional[float] = Field(None, description="變動百分比")
    open: Optional[float] = Field(None, description="開盤價")
    high: Optional[float] = Field(None, description="最高價")
    low: Optional[float] = Field(None, description="最低價")
    volume: Optional[float] = Field(None, description="成交量")
    
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
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    adjusted_close: Optional[float] = None
    source: Optional[str] = None


class EconomicIndicator(BaseModel):
    """經濟指標模型"""
    series_id: str = Field(..., description="FRED Series ID")
    name: str = Field(..., description="指標名稱")
    value: float = Field(..., description="當前值")
    date: datetime = Field(..., description="數據日期")
    unit: Optional[str] = Field(None, description="單位")
    frequency: Optional[str] = Field(None, description="頻率 (D/W/M)")
    source: str = Field(default="fred")


class MarketDataResponse(BaseModel):
    """市場數據響應模型"""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    source: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
