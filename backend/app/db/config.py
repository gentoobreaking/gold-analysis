"""
Database configuration module
Handles PostgreSQL, InfluxDB, and Redis connections
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from pydantic_settings import BaseSettings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from influxdb_client import InfluxDBClient
from redis import asyncio as aioredis


class Settings(BaseSettings):
    """Database configuration settings"""
    
    # Debug mode
    debug: bool = False
    
    # PostgreSQL
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/gold_analysis"
    
    # InfluxDB
    influxdb_url: str = "http://localhost:8086"
    influxdb_token: str = "my-token"
    influxdb_org: str = "gold-analysis"
    influxdb_bucket: str = "market-data"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    class Config:
        env_file = ".env"


# Global settings instance
settings = Settings()

# SQLAlchemy Base for models
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models"""
    pass


# PostgreSQL async engine and session maker
_postgres_engine = None
_postgres_session_maker = None


def get_postgres_engine():
    """Get or create PostgreSQL async engine"""
    global _postgres_engine
    if _postgres_engine is None:
        _postgres_engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    return _postgres_engine


def get_postgres_session_maker():
    """Get or create PostgreSQL session maker"""
    global _postgres_session_maker
    if _postgres_session_maker is None:
        _postgres_session_maker = async_sessionmaker(
            get_postgres_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _postgres_session_maker


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get database session
    Usage: async def endpoint(db: AsyncSession = Depends(get_db_session))
    """
    session_maker = get_postgres_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_postgres() -> None:
    """Initialize PostgreSQL connection and create tables"""
    engine = get_postgres_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ PostgreSQL initialized")


# InfluxDB client
_influx_client: Optional[InfluxDBClient] = None


def get_influx_client() -> InfluxDBClient:
    """Get or create InfluxDB client"""
    global _influx_client
    if _influx_client is None:
        _influx_client = InfluxDBClient(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )
    return _influx_client


async def init_influxdb() -> None:
    """Initialize InfluxDB client and verify connection"""
    client = get_influx_client()
    health = await client.health()
    print(f"✅ InfluxDB initialized: {health.status}")


# Redis client
_redis_client: Optional[aioredis.Redis] = None


def get_redis_client() -> aioredis.Redis:
    """Get or create Redis async client"""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def init_redis() -> None:
    """Initialize Redis connection"""
    client = get_redis_client()
    await client.ping()
    print("✅ Redis initialized")


async def init_all_databases() -> None:
    """Initialize all database connections"""
    await init_postgres()
    await init_influxdb()
    await init_redis()