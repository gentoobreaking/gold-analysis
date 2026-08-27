"""Core configuration settings.

This module provides the application settings for JWT authentication,
Redis connection, and other core infrastructure.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    """Core application settings."""

    # JWT
    jwt_secret_key: str = Field(
        default="dev-secret-change-in-production",
        description="Secret key for JWT signing",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    jwt_access_token_expire_minutes: int = Field(
        default=30, description="Access token expiry in minutes"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7, description="Refresh token expiry in days"
    )

    # Redis (used by rate limiter)
    redis_url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CORE_",
        extra="ignore",
    )


@lru_cache()
def get_core_settings() -> CoreSettings:
    """Get cached core settings instance."""
    return CoreSettings()


settings = get_core_settings()