"""
Alert routes - price alerts and notifications
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.user import User
from app.models.alert import Alert
from app.db.config import get_db_session
from app.api.schemas.alerts import (
    CreateAlertRequest,
    UpdateAlertRequest,
    AlertResponse,
    AlertListResponse,
    AlertTriggeredEvent,
)
from app.api.middleware.auth import get_current_active_user
from app.services.alert_service import AlertService


router = APIRouter()


# ── Alert Endpoints ─────────────────────────────────────────────────────────────

@router.post("/", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    request: CreateAlertRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> AlertResponse:
    """
    創建價格告警。
    
    - **alert_type**: 告警類型（price_above, price_below, indicator_cross, volume_spike）
    - **asset**: 資產符號
    - **target_price**: 目標價格
    """
    alert_service = AlertService(db)
    
    alert = await alert_service.create_alert(
        user_id=current_user.id,
        alert_type=request.alert_type,
        asset=request.asset.upper(),
        target_price=request.target_price,
        extra_data=request.extra_data,
    )
    
    return AlertResponse.model_validate(alert)


@router.get("/", response_model=AlertListResponse)
async def list_alerts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    is_active: Optional[bool] = Query(None, description="是否啟用"),
    asset: Optional[str] = Query(None, description="資產符號"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> AlertListResponse:
    """
    列出用戶的告警。
    
    - **page**: 頁碼
    - **page_size**: 每頁數量
    - **is_active**: 按啟用狀態過濾
    - **asset**: 按資產符號過濾
    """
    query = select(Alert).where(Alert.user_id == current_user.id)
    
    if is_active is not None:
        query = query.where(Alert.is_active == is_active)
    if asset:
        query = query.where(Alert.asset == asset.upper())
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Paginate
    query = query.order_by(Alert.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    alerts = result.scalars().all()
    
    return AlertListResponse(
        items=[AlertResponse.model_validate(a) for a in alerts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> AlertResponse:
    """獲取告警詳情。"""
    result = await db.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.user_id == current_user.id,
        )
    )
    alert = result.scalar_one_or_none()
    
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="告警不存在",
        )
    
    return AlertResponse.model_validate(alert)


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int,
    request: UpdateAlertRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> AlertResponse:
    """更新告警。"""
    result = await db.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.user_id == current_user.id,
        )
    )
    alert = result.scalar_one_or_none()
    
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="告警不存在",
        )
    
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(alert, field, value)
    
    await db.commit()
    await db.refresh(alert)
    
    return AlertResponse.model_validate(alert)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """刪除告警。"""
    result = await db.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.user_id == current_user.id,
        )
    )
    alert = result.scalar_one_or_none()
    
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="告警不存在",
        )
    
    await db.delete(alert)
    await db.commit()


@router.post("/{alert_id}/toggle", response_model=AlertResponse)
async def toggle_alert(
    alert_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> AlertResponse:
    """切換告警啟用/停用狀態。"""
    result = await db.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.user_id == current_user.id,
        )
    )
    alert = result.scalar_one_or_none()
    
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="告警不存在",
        )
    
    alert.is_active = not alert.is_active
    await db.commit()
    await db.refresh(alert)
    
    return AlertResponse.model_validate(alert)


@router.get("/check/triggered")
async def check_triggered_alerts(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[AlertTriggeredEvent]:
    """檢查並返回所有觸發的告警。"""
    alert_service = AlertService(db)
    
    triggered = await alert_service.check_triggered_alerts(user_id=current_user.id)
    
    return [AlertTriggeredEvent(**t) for t in triggered]


@router.delete("/clear-triggered", status_code=status.HTTP_204_NO_CONTENT)
async def clear_triggered_alerts(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """清除所有已觸發的告警（停用它們）。"""
    alert_service = AlertService(db)
    
    await alert_service.clear_triggered_alerts(user_id=current_user.id)
