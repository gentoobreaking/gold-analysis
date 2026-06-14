"""
Decision routes - AI recommendations, trading decisions
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.user import User
from app.models.decision import Decision
from app.db.config import get_db_session
from app.api.schemas.decisions import (
    CreateDecisionRequest,
    UpdateDecisionRequest,
    ExecuteDecisionRequest,
    DecisionResponse,
    DecisionListResponse,
    RecommendationResponse,
    DecisionStatsResponse,
)
from app.api.middleware.auth import get_current_active_user
from app.services.decision_service import DecisionService


router = APIRouter()


# ── Decision Endpoints ─────────────────────────────────────────────────────────

@router.get("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    symbol: str = Query(default="GOLD", description="資產符號"),
    confidence_threshold: float = Query(default=0.6, ge=0.0, le=1.0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> RecommendationResponse:
    """
    獲取 AI 決策推薦。
    
    根據市場數據和技術指標生成買入/賣出/持有建議。
    
    - **symbol**: 資產符號
    - **confidence_threshold**: 最低置信度閾值
    """
    if symbol.upper() != "GOLD":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目前僅支持 GOLD 符號",
        )
    
    decision_service = DecisionService(db)
    try:
        recommendation = await decision_service.generate_recommendation(
            user_id=current_user.id,
            symbol=symbol.upper(),
            confidence_threshold=confidence_threshold,
        )
        return RecommendationResponse(**recommendation)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )


@router.post("/", response_model=DecisionResponse, status_code=status.HTTP_201_CREATED)
async def create_decision(
    request: CreateDecisionRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> DecisionResponse:
    """
    創建新決策記錄。
    
    - **decision_type**: 決策類型（buy, sell, hold, watch）
    - **source**: 決策來源（ai_analysis, technical, fundamental, sentiment, manual）
    - **signal_strength**: 信號強度（0.0-1.0）
    - **confidence**: 置信度（0.0-1.0）
    """
    decision_service = DecisionService(db)
    
    decision = await decision_service.create_decision(
        user_id=current_user.id,
        decision_type=request.decision_type,
        source=request.source,
        asset=request.asset,
        signal_strength=request.signal_strength,
        confidence=request.confidence,
        price_target=request.price_target,
        stop_loss=request.stop_loss,
        reason_zh=request.reason_zh,
        reason_en=request.reason_en,
        portfolio_id=request.portfolio_id,
    )
    
    return DecisionResponse.model_validate(decision)


@router.get("/", response_model=DecisionListResponse)
async def list_decisions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    symbol: Optional[str] = Query(None, description="資產符號過濾"),
    decision_type: Optional[str] = Query(None, description="決策類型過濾"),
    is_executed: Optional[bool] = Query(None, description="是否已執行"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> DecisionListResponse:
    """
    列出用戶的決策記錄。
    
    - **page**: 頁碼
    - **page_size**: 每頁數量
    - **symbol**: 按資產符號過濾
    - **decision_type**: 按決策類型過濾
    - **is_executed**: 按執行狀態過濾
    """
    query = select(Decision).where(Decision.user_id == current_user.id)
    
    # Apply filters
    if symbol:
        query = query.where(Decision.asset == symbol.upper())
    if decision_type:
        query = query.where(Decision.decision_type == decision_type)
    if is_executed is not None:
        query = query.where(Decision.is_executed == is_executed)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Paginate
    query = query.order_by(Decision.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    decisions = result.scalars().all()
    
    return DecisionListResponse(
        items=[DecisionResponse.model_validate(d) for d in decisions],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.get("/{decision_id}", response_model=DecisionResponse)
async def get_decision(
    decision_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> DecisionResponse:
    """獲取指定決策詳情。"""
    result = await db.execute(
        select(Decision).where(
            Decision.id == decision_id,
            Decision.user_id == current_user.id,
        )
    )
    decision = result.scalar_one_or_none()
    
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="決策不存在",
        )
    
    return DecisionResponse.model_validate(decision)


@router.patch("/{decision_id}", response_model=DecisionResponse)
async def update_decision(
    decision_id: int,
    request: UpdateDecisionRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> DecisionResponse:
    """更新決策記錄。"""
    result = await db.execute(
        select(Decision).where(
            Decision.id == decision_id,
            Decision.user_id == current_user.id,
        )
    )
    decision = result.scalar_one_or_none()
    
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="決策不存在",
        )
    
    if decision.is_executed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已執行的決策無法修改",
        )
    
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(decision, field, value)
    
    await db.commit()
    await db.refresh(decision)
    
    return DecisionResponse.model_validate(decision)


@router.post("/{decision_id}/execute", response_model=DecisionResponse)
async def execute_decision(
    decision_id: int,
    request: ExecuteDecisionRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> DecisionResponse:
    """
    標記決策為已執行。
    
    - **execution_price**: 執行價格（可選，默認使用市價）
    - **notes**: 執行備註
    """
    result = await db.execute(
        select(Decision).where(
            Decision.id == decision_id,
            Decision.user_id == current_user.id,
        )
    )
    decision = result.scalar_one_or_none()
    
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="決策不存在",
        )
    
    if decision.is_executed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="決策已執行",
        )
    
    decision_service = DecisionService(db)
    decision = await decision_service.execute_decision(
        decision=decision,
        execution_price=request.execution_price,
    )
    
    return DecisionResponse.model_validate(decision)


@router.delete("/{decision_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_decision(
    decision_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """刪除決策記錄。"""
    result = await db.execute(
        select(Decision).where(
            Decision.id == decision_id,
            Decision.user_id == current_user.id,
        )
    )
    decision = result.scalar_one_or_none()
    
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="決策不存在",
        )
    
    if decision.is_executed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已執行的決策無法刪除",
        )
    
    await db.delete(decision)
    await db.commit()


@router.get("/stats/summary", response_model=DecisionStatsResponse)
async def get_decision_stats(
    symbol: Optional[str] = Query(None, description="資產符號過濾"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> DecisionStatsResponse:
    """獲取決策統計摘要。"""
    query = select(Decision).where(Decision.user_id == current_user.id)
    
    if symbol:
        query = query.where(Decision.asset == symbol.upper())
    
    result = await db.execute(query)
    decisions = result.scalars().all()
    
    total = len(decisions)
    buy = sum(1 for d in decisions if d.decision_type.value == "buy")
    sell = sum(1 for d in decisions if d.decision_type.value == "sell")
    hold = sum(1 for d in decisions if d.decision_type.value == "hold")
    watch = sum(1 for d in decisions if d.decision_type.value == "watch")
    executed = sum(1 for d in decisions if d.is_executed)
    pending = total - executed
    avg_confidence = sum(d.confidence for d in decisions) / total if total > 0 else 0
    avg_strength = sum(d.signal_strength for d in decisions) / total if total > 0 else 0
    
    return DecisionStatsResponse(
        total_decisions=total,
        buy_count=buy,
        sell_count=sell,
        hold_count=hold,
        watch_count=watch,
        executed_count=executed,
        pending_count=pending,
        avg_confidence=avg_confidence,
        avg_signal_strength=avg_strength,
        win_rate=None,  # 計算勝率需要更複雜的邏輯
    )
