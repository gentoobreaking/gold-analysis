"""
投資組合級風險路由 (T064) - 相關性矩陣 / 組合 VaR-CVaR / 因子曝險
"""

from __future__ import annotations

import logging

from app.api.schemas.portfolio_risk import (
    CorrelationMatrix,
    PortfolioRiskRequest,
    PortfolioRiskResponse,
    RiskSampleResponse,
)
from app.risk.portfolio import (
    correlation_matrix,
    factor_exposure,
    portfolio_var_from_returns,
)
from app.services.price_data import fetch_price_series
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.post("/portfolio", response_model=PortfolioRiskResponse)
async def portfolio_risk(request: PortfolioRiskRequest) -> PortfolioRiskResponse:
    """
    計算投資組合級風險：跨資產相關性矩陣、組合 VaR/CVaR（考量相關性）、因子曝險。
    """
    if len(request.weights) != len(request.returns):
        raise HTTPException(status_code=400, detail="weights 與 returns 資產數量必須一致")

    corr = correlation_matrix(request.returns)
    risk = portfolio_var_from_returns(
        weights=request.weights,
        returns_by_asset=request.returns,
        confidence=request.confidence,
        portfolio_value=request.portfolio_value,
        method=request.method,
    )

    exposure: dict[str, float] = {}
    warnings: list[str] = []
    if request.factor_returns:
        # 以第一個資產（通常為 GOLD）做因子曝險分解
        primary = next(iter(request.returns.keys()))
        exposure = factor_exposure(request.returns[primary], request.factor_returns)
    else:
        warnings.append("未提供 factor_returns，略過因子曝險分解")

    return PortfolioRiskResponse(
        correlation=CorrelationMatrix(**corr),
        portfolio_var=risk["var"],
        portfolio_cvar=risk["cvar"],
        portfolio_vol=risk["portfolio_vol"],
        factor_exposure=exposure,
        warnings=warnings,
    )


@router.get("/sample", response_model=RiskSampleResponse)
async def risk_sample() -> RiskSampleResponse:
    """
    風險儀表板預覽：真實黃金價格 + 合成跨資產因子，產出相關性矩陣與因子曝險。
    """
    # 真實黃金收盤價
    _, gold_closes = fetch_price_series("GOLD", limit=250)
    if len(gold_closes) < 30:
        return RiskSampleResponse(
            assets=["GOLD", "DXY", "REAL_YIELD", "BTC", "SPX"],
            correlation=CorrelationMatrix(
                assets=["GOLD", "DXY", "REAL_YIELD", "BTC", "SPX"],
                matrix=[[1.0, 0.0, 0.0, 0.0, 0.0] for _ in range(5)],
                valid=False,
            ),
            factor_exposure={},
            note="price_history 資料不足，請先取數（見 T054）",
        )

    # 由價格推收益率
    gold_ret = [gold_closes[i] / gold_closes[i - 1] - 1 for i in range(1, len(gold_closes))]
    n = len(gold_ret)
    rng = __import__("numpy").random.default_rng(42)

    # 合成因子（與黃金有合理相關性的設計，僅供示範）：
    #   DXY   : 與黃金負相關（美元強 -> 金弱）
    #   REAL_YIELD: 與黃金負相關
    #   BTC   : 與黃金弱正相關（避險情緒共振）
    #   SPX   : 與黃金弱負相關
    dxy = [-0.6 * g + rng.normal(0, 0.006, n) for g in gold_ret]
    ry = [-0.4 * g + rng.normal(0, 0.004, n) for g in gold_ret]
    btc = [0.3 * g + rng.normal(0, 0.03, n) for g in gold_ret]
    spx = [-0.2 * g + rng.normal(0, 0.008, n) for g in gold_ret]

    returns = {
        "GOLD": gold_ret,
        "DXY": dxy,
        "REAL_YIELD": ry,
        "BTC": btc,
        "SPX": spx,
    }
    corr = correlation_matrix(returns)
    exposure = factor_exposure(gold_ret, {"DXY": dxy, "REAL_YIELD": ry, "BTC": btc, "SPX": spx})

    return RiskSampleResponse(
        assets=corr["assets"],
        correlation=CorrelationMatrix(**corr),
        factor_exposure=exposure,
        note="GOLD 為真實歷史價格；DXY/REAL_YIELD/BTC/SPX 為示範用合成因子",
    )
