"""
Price data routes - current prices, historical data, technical indicators
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.db.config import get_db_session
from app.api.schemas.prices import (
    CurrentPriceResponse,
    HistoricalPricesResponse,
    OHLCVData,
    TechnicalIndicatorsResponse,
)
from app.api.middleware.auth import get_current_active_user
from app.services.price_service import PriceService


router = APIRouter()


# ── Price Endpoints ────────────────────────────────────────────────────────────

@router.get("/current", response_model=CurrentPriceResponse)
async def get_current_price(
    symbol: str = Query(default="GOLD", description="資產符號"),
    current_user: Optional[User] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> CurrentPriceResponse:
    """
    獲取黃金實時價格。
    
    返回黃金現價、匯率、24小時變化等信息。
    
    - **symbol**: 資產符號（目前僅支持 GOLD）
    """
    if symbol.upper() != "GOLD":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目前僅支持 GOLD 符號",
        )
    
    price_service = PriceService(db)
    try:
        price_data = await price_service.get_current_price(symbol.upper())
        return CurrentPriceResponse(**price_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )


@router.get("/historical", response_model=HistoricalPricesResponse)
async def get_historical_prices(
    symbol: str = Query(default="GOLD", description="資產符號"),
    interval: str = Query(default="1h", description="時間間隔: 1m, 5m, 15m, 1h, 4h, 1d"),
    start_time: Optional[datetime] = Query(None, description="開始時間"),
    end_time: Optional[datetime] = Query(None, description="結束時間"),
    limit: int = Query(default=100, ge=1, le=1000, description="返回數量"),
    current_user: Optional[User] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> HistoricalPricesResponse:
    """
    獲取歷史價格數據。
    
    - **symbol**: 資產符號
    - **interval**: 時間間隔（1m, 5m, 15m, 1h, 4h, 1d）
    - **start_time**: 開始時間（可選，默認最近 100 個週期）
    - **end_time**: 結束時間（可選，默認為當前時間）
    - **limit**: 最大返回數據點數
    """
    if symbol.upper() != "GOLD":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目前僅支持 GOLD 符號",
        )
    
    # Default time range
    if end_time is None:
        end_time = datetime.utcnow()
    if start_time is None:
        start_time = end_time - timedelta(days=7)
    
    price_service = PriceService(db)
    try:
        data = await price_service.get_historical_prices(
            symbol=symbol.upper(),
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        return HistoricalPricesResponse(**data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/indicators", response_model=TechnicalIndicatorsResponse)
async def get_technical_indicators(
    symbol: str = Query(default="GOLD", description="資產符號"),
    period: int = Query(default=14, ge=5, le=200, description="計算週期"),
    current_user: Optional[User] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> TechnicalIndicatorsResponse:
    """
    獲取技術指標數據。
    
    包括 RSI、MACD、MA、布林帶等指標及其信號。
    
    - **symbol**: 資產符號
    - **period**: 計算週期（默認 14）
    """
    if symbol.upper() != "GOLD":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目前僅支持 GOLD 符號",
        )
    
    price_service = PriceService(db)
    try:
        indicators = await price_service.get_technical_indicators(
            symbol=symbol.upper(),
            period=period,
        )
        return TechnicalIndicatorsResponse(**indicators)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )


@router.get("/multi", response_model=Dict[str, Any])
async def get_multi_assets_prices(
    symbols: str = Query(..., description="資產符號列表（逗號分隔）"),
    current_user: Optional[User] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    批量獲取多個資產價格。
    
    - **symbols**: 資產符號列表，如 "GOLD,SILVER"
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    
    if not all(s in ["GOLD", "SILVER"] for s in symbol_list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="目前僅支持 GOLD 和 SILVER 符號",
        )
    
    price_service = PriceService(db)
    result = {}
    
    for symbol in symbol_list:
        try:
            price_data = await price_service.get_current_price(symbol)
            result[symbol] = price_data
        except ValueError:
            result[symbol] = {"error": "無法獲取價格數據"}
    
    return result


@router.get("/converter")
async def convert_currency(
    amount: float = Query(..., gt=0, description="金額"),
    from_currency: str = Query(..., description="源貨幣"),
    to_currency: str = Query(..., description="目標貨幣"),
    current_user: Optional[User] = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """
    貨幣轉換。
    
    - **amount**: 金額
    - **from_currency**: 源貨幣（如 USD, CNY, TWD）
    - **to_currency**: 目標貨幣
    """
    valid_currencies = ["USD", "CNY", "TWD", "EUR", "JPY", "GBP"]
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    
    if from_currency not in valid_currencies or to_currency not in valid_currencies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的貨幣。支持的貨幣: {', '.join(valid_currencies)}",
        )
    
    price_service = PriceService(db)
    converted = await price_service.convert_currency(amount, from_currency, to_currency)
    
    return {
        "amount": amount,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "converted_amount": converted,
        "timestamp": datetime.utcnow().isoformat(),
    }
