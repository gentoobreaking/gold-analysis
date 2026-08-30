"""
Alert request/response schemas
"""
from datetime import datetime

from app.models.alert import AlertType
from pydantic import BaseModel, Field

# ── Request Schemas ────────────────────────────────────────────────────────────

class CreateAlertRequest(BaseModel):
    """Create new alert request"""
    alert_type: AlertType = Field(..., description="告警類型")
    asset: str = Field(default="GOLD", description="資產符號")
    target_price: float = Field(..., gt=0, description="目標價格")
    extra_data: str | None = Field(None, description="額外數據（JSON）")


class UpdateAlertRequest(BaseModel):
    """Update alert request"""
    target_price: float | None = Field(None, gt=0)
    is_active: bool | None = None


# ── Response Schemas ────────────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    """Alert response"""
    id: int
    user_id: int
    alert_type: AlertType
    asset: str
    target_price: float
    is_active: bool
    created_at: datetime
    triggered_at: datetime | None
    extra_data: str | None

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    """Alert list response with pagination"""
    items: list[AlertResponse]
    total: int
    page: int
    page_size: int


class AlertTriggeredEvent(BaseModel):
    """Alert triggered event"""
    alert_id: int
    asset: str
    alert_type: AlertType
    target_price: float
    current_price: float
    triggered_at: datetime
    message: str = Field(..., description="觸發消息")
