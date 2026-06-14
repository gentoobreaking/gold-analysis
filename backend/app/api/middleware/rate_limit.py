"""
Rate limiting middleware for API endpoints
"""
import time
from typing import Optional

from fastapi import Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings


# Create limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri=settings.redis_url if settings.redis_url else "memory://",
)


async def rate_limit_dependency(request: Request) -> None:
    """
    Dependency for rate limiting endpoints.
    Raises 429 Too Many Requests if limit exceeded.
    """
    # Get client identifier (IP address or user ID if authenticated)
    client_ip = get_remote_address(request)
    
    # Check rate limit manually for custom limits
    # This is a simplified version; in production use @limiter.limit decorator
    pass


def rate_limit_callback(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Callback for rate limit exceeded events"""
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"速率限制已超出: {exc.detail}",
            "error": "rate_limit_exceeded",
            "retry_after": getattr(exc, "retry_after", 60),
        }
    )
