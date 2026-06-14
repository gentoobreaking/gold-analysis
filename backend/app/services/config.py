"""
API Configuration & Secrets Management
API 密鑰管理：從環境變數讀取，不硬編碼
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """API 密鑰配置"""
    
    # Alpha Vantage
    alpha_vantage_api_key: str = ""
    alpha_vantage_base_url: str = "https://www.alphavantage.co/query"
    
    # Finnhub
    finnhub_api_key: str = ""
    finnhub_base_url: str = "https://finnhub.io/api/v1"
    
    # FRED
    fred_api_key: str = ""
    fred_base_url: str = "https://api.stlouisfed.org/fred"
    
    # Rate limiting
    alpha_vantage_rate_limit: int = 5  # 5 calls/min
    alpha_vantage_rate_period: int = 60  # 60 seconds
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0  # seconds
    
    # Cache settings
    cache_ttl: int = 300  # 5 minutes default

    class Config:
        env_file = ".env"
        env_prefix = ""


@lru_cache()
def get_api_settings() -> APISettings:
    """取得 API 配置（單例，緩存）"""
    return APISettings()


def get_api_key(provider: str) -> str:
    """取得指定 provider 的 API key"""
    settings = get_api_settings()
    key_map = {
        "alpha_vantage": settings.alpha_vantage_api_key,
        "finnhub": settings.finnhub_api_key,
        "fred": settings.fred_api_key,
    }
    return key_map.get(provider, "")
