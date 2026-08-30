"""
Data Sources Package
統一數據源適配器
"""

from .alpha_vantage import AlphaVantageAdapter
from .base import BaseDataSource, HistoricalData, MarketData
from .finnhub import FinnhubAdapter
from .fred import FREDAdapter

__all__ = [
    "AlphaVantageAdapter",
    "BaseDataSource",
    "FREDAdapter",
    "FinnhubAdapter",
    "HistoricalData",
    "MarketData",
]
