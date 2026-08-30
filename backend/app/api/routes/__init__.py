"""
Routes package
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def get_status():
    """Get system status"""
    return {"status": "ok", "message": "API is running"}


from . import alerts, auth, backtest, decisions, freshness, macro_digest, portfolio_risk, prices

__all__ = [
    "alerts",
    "auth",
    "backtest",
    "decisions",
    "freshness",
    "get_status",
    "macro_digest",
    "portfolio_risk",
    "prices",
    "router",
]
