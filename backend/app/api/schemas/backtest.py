"""
Backtest request/response schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ── Request Schemas ────────────────────────────────────────────────────────────

class BacktestConfig(BaseModel):
    """Backtest configuration"""
    initial_capital: float = Field(default=10000.0, gt=0, description="初始資金")
    commission_rate: float = Field(default=0.001, ge=0, le=0.1, description="手續費率")
    slippage: float = Field(default=0.001, ge=0, le=0.1, description="滑點")
    position_size: float = Field(default=0.1, gt=0, le=1.0, description="倉位大小比例")


class BacktestRequest(BaseModel):
    """Backtest request"""
    strategy_type: str = Field(..., description="策略類型: ma_crossover, rsi, macd, combined")
    start_date: datetime = Field(..., description="開始日期")
    end_date: datetime = Field(..., description="結束日期")
    config: BacktestConfig = Field(default_factory=BacktestConfig, description="回測配置")
    decision_ids: Optional[List[int]] = Field(None, description="使用的決策 ID 列表")


class SaveStrategyRequest(BaseModel):
    """Save backtest strategy request"""
    name: str = Field(..., min_length=1, max_length=100, description="策略名稱")
    description: Optional[str] = Field(None, max_length=500, description="策略描述")
    strategy_type: str = Field(..., description="策略類型")
    config: Dict[str, Any] = Field(..., description="策略配置")
    is_public: bool = Field(default=False, description="是否公開")


# ── Response Schemas ────────────────────────────────────────────────────────────

class BacktestTrade(BaseModel):
    """Single backtest trade"""
    timestamp: datetime
    action: str  # buy, sell
    price: float
    quantity: float
    commission: float
    total: float


class BacktestEquity(BaseModel):
    """Equity curve data point"""
    timestamp: datetime
    equity: float
    cash: float
    position_value: float
    drawdown: float


class BacktestMetrics(BaseModel):
    """Backtest performance metrics"""
    total_return: float = Field(..., description="總收益（百分比）")
    annualized_return: float = Field(..., description="年化收益率")
    sharpe_ratio: float = Field(..., description="夏普比率")
    max_drawdown: float = Field(..., description="最大回撤（百分比）")
    win_rate: float = Field(..., description="勝率")
    profit_factor: float = Field(..., description="利潤因子")
    total_trades: int = Field(..., description="總交易次數")
    avg_trade_duration: float = Field(..., description="平均持倉時間（小時）")


class BacktestResponse(BaseModel):
    """Full backtest response"""
    strategy_name: str
    backtest_id: str = Field(..., description="回測 ID")
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_equity: float
    metrics: BacktestMetrics
    trades: List[BacktestTrade]
    equity_curve: List[BacktestEquity]
    created_at: datetime


class StrategyResponse(BaseModel):
    """Saved strategy response"""
    id: int
    user_id: int
    name: str
    description: Optional[str]
    strategy_type: str
    config: Dict[str, Any]
    is_public: bool
    backtest_results: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StrategyListResponse(BaseModel):
    """Strategy list response"""
    items: List[StrategyResponse]
    total: int
