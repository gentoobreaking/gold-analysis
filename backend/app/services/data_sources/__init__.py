"""
Data Sources Package
統一數據源適配器
"""

from .base import BaseDataSource, HistoricalData, MarketData
from .alpha_vantage import AlphaVantageAdapter
from .finnhub import FinnhubAdapter
from .fred import FREDAdapter

__all__ = [
    "BaseDataSource",
    "HistoricalData",
    "MarketData",
    "AlphaVantageAdapter",
    "FinnhubAdapter",
    "FREDAdapter",
]
