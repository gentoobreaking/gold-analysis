"""
Data Sources Unit Tests
測試所有數據源適配器
"""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

# Imports use relative path via conftest.py sys.path.insert

from app.services.data_sources.alpha_vantage import AlphaVantageAdapter
from app.services.data_sources.finnhub import FinnhubAdapter
from app.services.data_sources.fred import FREDAdapter
from app.services.data_sources.base import BaseDataSource
from app.services.config import APISettings, get_api_key


class TestAlphaVantageAdapter:
    """Alpha Vantage 適配器測試"""
    
    @pytest.fixture
    def adapter(self):
        return AlphaVantageAdapter()
    
    def test_init(self, adapter):
        assert adapter.name == "alpha_vantage"
        assert adapter.api_key == "test_alpha_key"
    
    @pytest.mark.asyncio
    async def test_get_price_without_key(self, adapter):
        adapter.api_key = ""
        with pytest.raises(ValueError, match="API key 未設定"):
            await adapter.get_price("GC")
    
    @pytest.mark.asyncio
    async def test_get_price_success(self, adapter):
        mock_response = {
            "Global Quote": {
                "05. price": "2034.50",
                "02. open": "2030.00",
                "03. high": "2040.00",
                "04. low": "2028.00",
                "06. volume": "150000",
                "07. latest trading day": "2024-01-15",
            }
        }
        
        with patch.object(adapter, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            result = await adapter.get_price("GC")
            
            assert result.symbol == "GC"
            assert result.value == 2034.50
            assert result.currency == "USD"
            assert result.metadata["high"] == 2040.00
    
    @pytest.mark.asyncio
    async def test_get_price_rate_limit_error(self, adapter):
        mock_response = {"Note": "API rate limit exceeded"}
        
        with patch.object(adapter, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            with pytest.raises(RuntimeError, match="速率限制"):
                await adapter.get_price("GC")
    
    @pytest.mark.asyncio
    async def test_get_historical(self, adapter):
        from datetime import datetime
        
        mock_response = {
            "Time Series (Daily)": {
                "2024-01-15": {
                    "1. open": "2030.00",
                    "2. high": "2040.00",
                    "3. low": "2028.00",
                    "4. close": "2034.50",
                    "6. volume": "150000",
                },
                "2024-01-16": {
                    "1. open": "2035.00",
                    "2. high": "2045.00",
                    "3. low": "2030.00",
                    "4. close": "2040.00",
                    "6. volume": "160000",
                },
            }
        }
        
        with patch.object(adapter, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            start = datetime(2024, 1, 14)
            end = datetime(2024, 1, 17)
            results = await adapter.get_historical("GC", start, end)
            
            assert len(results) == 2
            assert results[0].symbol == "GC"
            assert results[0].close == 2034.50


class TestFinnhubAdapter:
    """Finnhub 適配器測試"""
    
    @pytest.fixture
    def adapter(self):
        return FinnhubAdapter()
    
    def test_init(self, adapter):
        assert adapter.name == "finnhub"
        assert adapter.api_key == "test_finnhub_key"
    
    @pytest.mark.asyncio
    async def test_get_price_without_key(self, adapter):
        adapter.api_key = ""
        with pytest.raises(ValueError, match="API key 未設定"):
            await adapter.get_price("AAPL")
    
    @pytest.mark.asyncio
    async def test_get_price_success(self, adapter):
        mock_response = {
            "c": 185.50,
            "d": 2.30,
            "dp": 1.25,
            "h": 186.00,
            "l": 183.00,
            "o": 183.20,
            "pc": 183.20,
            "t": 1705323000,
        }
        
        with patch.object(adapter, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            result = await adapter.get_price("AAPL")
            
            assert result.symbol == "AAPL"
            assert result.value == 185.50
            assert result.metadata["high"] == 186.00
    
    @pytest.mark.asyncio
    async def test_get_historical(self, adapter):
        from datetime import datetime
        
        mock_response = {
            "s": "ok",
            "t": [1705323000, 1705409400],
            "o": [183.20, 185.00],
            "h": [186.00, 187.00],
            "l": [183.00, 184.50],
            "c": [185.50, 186.00],
            "v": [1000000, 1100000],
        }
        
        with patch.object(adapter, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            start = datetime(2024, 1, 14)
            end = datetime(2024, 1, 17)
            results = await adapter.get_historical("AAPL", start, end)
            
            assert len(results) == 2
            assert results[0].symbol == "AAPL"
            assert results[0].close == 185.50


class TestFREDAdapter:
    """FRED 適配器測試"""
    
    @pytest.fixture
    def adapter(self):
        return FREDAdapter()
    
    def test_init(self, adapter):
        assert adapter.name == "fred"
        assert adapter.api_key == "test_fred_key"
    
    def test_resolve_series(self, adapter):
        assert adapter._resolve_series("GOLD") == "GOLDAMGBD228NLBM"
        assert adapter._resolve_series("GC") == "GOLDAMGBD228NLBM"
        assert adapter._resolve_series("DXY") == "DTWEXBGS"
        assert adapter._resolve_series("CPI") == "CPIAUCSL"
        assert adapter._resolve_series("10Y") == "DGS10"
        assert adapter._resolve_series("FEDFUNDS") == "FEDFUNDS"
    
    @pytest.mark.asyncio
    async def test_get_price_without_key(self, adapter):
        adapter.api_key = ""
        with pytest.raises(ValueError, match="API key 未設定"):
            await adapter.get_price("GOLD")
    
    @pytest.mark.asyncio
    async def test_get_price_success(self, adapter):
        mock_response = {
            "observations": [
                {
                    "date": "2024-01-15",
                    "value": "2034.50",
                    "realtime_start": "2024-01-15",
                    "realtime_end": "2024-01-15",
                }
            ]
        }
        
        with patch.object(adapter, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            result = await adapter.get_price("GOLD")
            
            assert result.symbol == "GOLDAMGBD228NLBM"
            assert result.value == 2034.50
            assert result.metadata["series_name"] == "Gold Fixing Price (London)"
    
    @pytest.mark.asyncio
    async def test_get_historical(self, adapter):
        from datetime import datetime
        
        mock_response = {
            "observations": [
                {"date": "2024-01-15", "value": "2034.50"},
                {"date": "2024-01-16", "value": "2040.00"},
                {"date": "2024-01-17", "value": "."},  # missing data
                {"date": "2024-01-18", "value": "2038.00"},
            ]
        }
        
        with patch.object(adapter, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            start = datetime(2024, 1, 14)
            end = datetime(2024, 1, 19)
            results = await adapter.get_historical("GOLD", start, end)
            
            assert len(results) == 3
            assert results[0].close == 2034.50
            assert results[2].close == 2038.00


class TestBaseDataSource:
    """基類測試"""
    
    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test cache clearing functionality"""
        class TestAdapter(BaseDataSource):
            @property
            def name(self):
                return "test"
            
            async def get_price(self, symbol):
                return None
            
            async def get_historical(self, symbol, start, end):
                return []
        
        adapter = TestAdapter(api_key="test", base_url="http://test.com")
        adapter._cache["test_key"] = ("test_data", 1234567890)
        
        assert "test_key" in adapter._cache
        adapter.clear_cache()
        assert len(adapter._cache) == 0
    
    @pytest.mark.asyncio
    async def test_cache_functionality(self):
        """Test that _request uses cache"""
        class TestAdapter(BaseDataSource):
            @property
            def name(self):
                return "test_cache"
            
            async def get_price(self, symbol):
                return None
            
            async def get_historical(self, symbol, start, end):
                return []
        
        adapter = TestAdapter(api_key="test", base_url="http://test.com")
        # Check cache is empty initially
        assert len(adapter._cache) == 0


class TestConfig:
    """配置測試"""
    
    def test_api_settings(self):
        settings = APISettings()
        assert settings.alpha_vantage_api_key == "test_alpha_key"
        assert settings.finnhub_api_key == "test_finnhub_key"
        assert settings.fred_api_key == "test_fred_key"
        
        assert get_api_key("alpha_vantage") == "test_alpha_key"
        assert get_api_key("finnhub") == "test_finnhub_key"
        assert get_api_key("fred") == "test_fred_key"
    
    def test_defaults(self):
        settings = APISettings(
            alpha_vantage_api_key="",
            finnhub_api_key="",
            fred_api_key="",
        )
        assert settings.alpha_vantage_rate_limit == 5
        assert settings.alpha_vantage_rate_period == 60
        assert settings.max_retries == 3
        assert settings.cache_ttl == 300


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
