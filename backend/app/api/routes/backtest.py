"""
Backtest routes - strategy backtesting and optimization
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.db.config import get_db_session
from app.api.schemas.backtest import (
    BacktestRequest,
    BacktestResponse,
    BacktestMetrics,
    BacktestTrade,
    BacktestEquity,
    SaveStrategyRequest,
    StrategyResponse,
    StrategyListResponse,
)
from app.api.middleware.auth import get_current_active_user
from app.services.backtest_service import BacktestService


router = APIRouter()


# ── Backtest Endpoints ─────────────────────────────────────────────────────────

@router.post("/run", response_model=BacktestResponse)
async def run_backtest(
    request: BacktestRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> BacktestResponse:
    """
    運行策略回測。
    
    - **strategy_type**: 策略類型（ma_crossover, rsi, macd, combined）
    - **start_date**: 開始日期
    - **end_date**: 結束日期
    - **config**: 回測配置（初始資金、手續費、滑點等）
    """
    # Validate date range
    if request.start_date >= request.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="結束日期必須晚於開始日期",
        )
    
    # Validate strategy type
    valid_strategies = ["ma_crossover", "rsi", "macd", "combined"]
    if request.strategy_type not in valid_strategies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的策略類型。可選: {', '.join(valid_strategies)}",
        )
    
    backtest_service = BacktestService(db)
    try:
        result = await backtest_service.run_backtest(
            user_id=current_user.id,
            strategy_type=request.strategy_type,
            start_date=request.start_date,
            end_date=request.end_date,
            config=request.config.model_dump(),
            decision_ids=request.decision_ids,
        )
        return BacktestResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/strategies", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
async def save_strategy(
    request: SaveStrategyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> StrategyResponse:
    """
    保存策略配置。
    
    - **name**: 策略名稱
    - **strategy_type**: 策略類型
    - **config**: 策略配置
    - **is_public**: 是否公開（可被其他用戶查看）
    """
    backtest_service = BacktestService(db)
    
    strategy = await backtest_service.save_strategy(
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        strategy_type=request.strategy_type,
        config=request.config,
        is_public=request.is_public,
    )
    
    return StrategyResponse.model_validate(strategy)


@router.get("/strategies", response_model=StrategyListResponse)
async def list_strategies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    strategy_type: Optional[str] = Query(None, description="策略類型過濾"),
    include_public: bool = Query(default=True, description="包含公開策略"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> StrategyListResponse:
    """
    列出策略。
    
    - **page**: 頁碼
    - **page_size**: 每頁數量
    - **strategy_type**: 按策略類型過濾
    - **include_public**: 是否包含公開策略
    """
    backtest_service = BacktestService(db)
    
    result = await backtest_service.list_strategies(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        strategy_type=strategy_type,
        include_public=include_public,
    )
    
    return StrategyListResponse(**result)


@router.get("/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> StrategyResponse:
    """獲取策略詳情。"""
    backtest_service = BacktestService(db)
    
    try:
        strategy = await backtest_service.get_strategy(
            strategy_id=strategy_id,
            user_id=current_user.id,
        )
        return StrategyResponse.model_validate(strategy)
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您無權查看此策略",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="策略不存在",
        )


@router.delete("/strategies/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """刪除策略。"""
    backtest_service = BacktestService(db)
    
    try:
        await backtest_service.delete_strategy(
            strategy_id=strategy_id,
            user_id=current_user.id,
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您無權刪除此策略",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="策略不存在",
        )


@router.get("/history", response_model=List[BacktestResponse])
async def list_backtest_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[BacktestResponse]:
    """列出歷史回測記錄。"""
    backtest_service = BacktestService(db)
    
    results = await backtest_service.list_backtest_history(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    
    return [BacktestResponse(**r) for r in results]


@router.get("/compare")
async def compare_strategies(
    strategy_ids: str = Query(..., description="策略 ID 列表（逗號分隔）"),
    start_date: Optional[datetime] = Query(None, description="比較開始日期"),
    end_date: Optional[datetime] = Query(None, description="比較結束日期"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    比較多個策略的表現。
    
    - **strategy_ids**: 策略 ID 列表
    - **start_date**: 比較開始日期（可選）
    - **end_date**: 比較結束日期（可選）
    """
    strategy_id_list = [int(s.strip()) for s in strategy_ids.split(",")]
    
    if len(strategy_id_list) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少需要兩個策略進行比較",
        )
    
    backtest_service = BacktestService(db)
    
    try:
        comparison = await backtest_service.compare_strategies(
            strategy_ids=strategy_id_list,
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
        )
        return comparison
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
