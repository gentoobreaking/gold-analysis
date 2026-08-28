"""
Routes package
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def get_status():
    """Get system status"""
    return {"status": "ok", "message": "API is running"}

from . import auth, prices, decisions, backtest, alerts, portfolio_risk, macro_digest

__all__ = ["router", "get_status", "auth", "prices", "decisions", "backtest", "alerts", "portfolio_risk", "macro_digest"]
