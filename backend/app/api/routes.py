"""
Gold Analysis Core - API Routes
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def get_status():
    """Get system status"""
    return {"status": "ok", "message": "API is running"}
