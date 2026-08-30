"""
資料新鮮度 SLA 監控路由 (T066)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.api.schemas.freshness import FreshnessResponse, SourceStatus
from app.services.data_freshness import check_freshness, run_freshness_check
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/freshness", tags=["freshness"])


class _CheckRequest(BaseModel):
    notify: bool = True


@router.get("", response_model=FreshnessResponse)
async def get_freshness() -> FreshnessResponse:
    """檢查各資料來源新鮮度（不發送通知）。"""
    statuses = await check_freshness()
    return FreshnessResponse(
        checked_at=datetime.now(timezone.utc).isoformat(),
        sources=[SourceStatus(**s.__dict__) for s in statuses],
    )


@router.post("/check", response_model=FreshnessResponse)
async def run_check(request: _CheckRequest) -> FreshnessResponse:
    """檢查並對 stale 來源發送 T056 通知（若 notify=True 且 notify_enabled）。"""
    statuses = await run_freshness_check() if request.notify else await check_freshness()
    return FreshnessResponse(
        checked_at=datetime.now(timezone.utc).isoformat(),
        sources=[SourceStatus(**s.__dict__) for s in statuses],
    )
