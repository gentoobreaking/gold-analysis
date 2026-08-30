"""
Data freshness SLA schemas (T066)
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SourceStatus(BaseModel):
    """單一資料來源的 SLA 狀態"""

    name: str
    sla_seconds: int
    last_update: str | None = None
    age_seconds: float | None = None
    status: str = "unavailable"  # fresh | stale | unavailable
    is_mock: bool = False
    detail: str = ""


class FreshnessResponse(BaseModel):
    """所有來源的新鮮度檢查結果"""

    checked_at: str
    sources: list[SourceStatus] = Field(default_factory=list)
