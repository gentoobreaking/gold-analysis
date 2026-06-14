"""
Validation & Cleaning Configuration
驗證和清洗的配置參數
"""

from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class ValidationSettings(BaseSettings):
    """驗證閾值配置"""
    
    # Price validation
    min_gold_price: float = Field(default=1000.0, description="最小黃金價格")
    max_gold_price: float = Field(default=10000.0, description="最大黃金價格")
    daily_price_change_threshold: float = Field(default=0.05, description="日波動閾值 (5%)")
    
    # Timestamp validation
    max_data_age_days: int = Field(default=365, description="數據最大保留天數")
    allow_future_timestamp: bool = Field(default=False, description="是否允許未來時間戳")
    
    # Market data validation
    dxy_min: float = Field(default=90.0, description="DXY 最小值")
    dxy_max: float = Field(default=110.0, description="DXY 最大值")
    rate_min: float = Field(default=0.0, description="利率最小值")
    rate_max: float = Field(default=20.0, description="利率最大值")
    
    class Config:
        env_file = ".env"
        env_prefix = "VALIDATION_"


class CleaningSettings(BaseSettings):
    """清洗策略配置"""
    
    # Missing value handling
    missing_value_strategy: str = Field(default="interpolate", description="策略: interpolate/delete/mark")
    interpolation_limit: int = Field(default=5, description="插值最大連續缺失數")
    
    # Duplicate handling
    duplicate_keep: str = Field(default="first", description="保留策略: first/last")
    
    # Outlier detection
    outlier_method: str = Field(default="zscore", description="檢測方法: zscore/iqr")
    zscore_threshold: float = Field(default=3.0, description="Z-score 閾值")
    iqr_multiplier: float = Field(default=1.5, description="IQR 倍數")
    
    # Anomaly correction
    correction_strategy: str = Field(default="clip", description="修正策略: clip/remove/mark")
    
    class Config:
        env_file = ".env"
        env_prefix = "CLEANING_"


@lru_cache()
def get_validation_settings() -> ValidationSettings:
    """取得驗證配置"""
    return ValidationSettings()


@lru_cache()
def get_cleaning_settings() -> CleaningSettings:
    """取得清洗配置"""
    return CleaningSettings()
