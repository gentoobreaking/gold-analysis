"""
Portfolio risk schemas (T064) - 相關性矩陣 / 組合 VaR-CVaR / 因子曝險
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PortfolioRiskRequest(BaseModel):
    """投資組合風險計算請求"""

    weights: list[float] = Field(..., description="各資產權重（總和建議≈1）")
    returns: dict[str, list[float]] = Field(..., description="各資產收益率序列 {資產名: 收益列}")
    factor_returns: dict[str, list[float]] | None = Field(
        None, description="因子收益率序列 {因子名: 收益列}，用於因子曝險分解"
    )
    confidence: float = Field(0.95, gt=0.0, lt=1.0)
    portfolio_value: float = Field(1.0, gt=0.0)
    method: str = Field("parametric", description="parametric | cornish_fisher")


class CorrelationMatrix(BaseModel):
    assets: list[str]
    matrix: list[list[float]]
    valid: bool


class PortfolioRiskResponse(BaseModel):
    """投資組合風險回應"""

    correlation: CorrelationMatrix
    portfolio_var: float
    portfolio_cvar: float
    portfolio_vol: float
    factor_exposure: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class RiskSampleResponse(BaseModel):
    """範例資料（真實黃金價格 + 合成因子），供前端儀表板預覽"""

    assets: list[str]
    correlation: CorrelationMatrix
    factor_exposure: dict[str, float]
    note: str = ""
