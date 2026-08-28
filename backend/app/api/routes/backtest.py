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
    WalkForwardRequest,
    WalkForwardResponse,
    WalkForwardFold,
    StrategyComparisonRequest,
    StrategyComparisonResponse,
    StrategyComparisonItem,
    PaperReplayRequest,
    PaperReplayResponse,
)
from app.services.backtest_engine import BacktestEngine, BUILTIN_STRATEGIES
from app.services.price_data import fetch_price_series
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


# ── T063: 向量化引擎端點（無 DB / 自帶價格序列）────────────────────────────

@router.post("/walk-forward", response_model=WalkForwardResponse)
async def walk_forward(request: WalkForwardRequest) -> WalkForwardResponse:
    """
    Walk-forward 回測（樣本外驗證）。

    在 in-sample 訓練窗選最佳參數，於 out-of-sample 測試窗驗證，
    回傳各折最佳參數與樣本外績效，以及平均樣本外 Sharpe 與是否穩健(robust)。
    """
    strategy_fn = BUILTIN_STRATEGIES.get(request.strategy_type)
    if strategy_fn is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未知策略類型。可選: {', '.join(BUILTIN_STRATEGIES.keys())}",
        )
    engine = BacktestEngine()
    result = engine.walk_forward(
        prices=request.prices,
        strategy_fn=strategy_fn,
        param_grid=request.param_grid,
        train_days=request.train_days,
        test_days=request.test_days,
        step=request.step,
    )
    return WalkForwardResponse(
        folds=[WalkForwardFold(**f) for f in result.get("folds", [])],
        n_folds=result.get("n_folds", 0),
        avg_out_of_sample_sharpe=result.get("avg_out_of_sample_sharpe", 0.0),
        robust=result.get("robust", False),
        errors=result.get("errors", []),
    )


@router.post("/compare", response_model=StrategyComparisonResponse)
async def compare_strategies_engine(request: StrategyComparisonRequest) -> StrategyComparisonResponse:
    """
    策略比較：對同一段歷史價格，並排比較多個內建策略的績效。
    """
    unknown = [s for s in request.strategies if s not in BUILTIN_STRATEGIES]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未知策略: {', '.join(unknown)}。可選: {', '.join(BUILTIN_STRATEGIES.keys())}",
        )
    engine = BacktestEngine()
    strategies = {name: BUILTIN_STRATEGIES[name] for name in request.strategies}
    raw = engine.compare_strategies(request.prices, strategies)
    results = {
        name: StrategyComparisonItem(**item) for name, item in raw.items() if "error" not in item
    }
    # 若某策略回傳 error，塞回 errors 欄
    for name, item in raw.items():
        if "error" in item:
            results[name] = StrategyComparisonItem(
                final_equity=0.0, total_return=0.0, annualized_return=0.0,
                sharpe_ratio=0.0, sortino_ratio=0.0, max_drawdown=0.0,
                win_rate=0.0, n_trades=0, errors=[item["error"]],
            )
    return StrategyComparisonResponse(results=results)


@router.post("/paper-replay", response_model=PaperReplayResponse)
async def paper_replay(request: PaperReplayRequest) -> PaperReplayResponse:
    """
    模擬下單：重放歷史信號序列，對比策略與 buy & hold 基準的實際走勢。
    """
    if len(request.prices) != len(request.decision_signals):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="prices 與 decision_signals 長度必須一致",
        )
    engine = BacktestEngine()
    result = engine.paper_replay(request.prices, request.decision_signals)
    return PaperReplayResponse(
        strategy=StrategyComparisonItem(**result["strategy"]),
        buy_and_hold=StrategyComparisonItem(**result["buy_and_hold"]),
        outperformed=result["outperformed"],
    )


@router.get("/prices")
async def get_prices(
    asset: str = Query("GOLD", description="資產代號"),
    limit: int = Query(400, gt=0, le=2000, description="最多回傳筆數"),
) -> dict:
    """
    取得真實歷史收盤價序列（來自 price_history），供前端回測/比較視圖使用。
    """
    dates, closes = fetch_price_series(asset=asset, limit=limit)
    return {"asset": asset, "dates": dates, "prices": closes, "count": len(closes)}
