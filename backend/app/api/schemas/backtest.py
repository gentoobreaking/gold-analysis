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


# ── T063: walk-forward / 比較視圖 schemas ─────────────────────────────────────

class WalkForwardRequest(BaseModel):
    """Walk-forward 回測請求"""
    strategy_type: str = Field("ma_crossover", description="內建策略: ma_crossover, rsi, macd, combined")
    prices: List[float] = Field(..., description="歷史收盤價序列（舊→新）")
    param_grid: List[Dict[str, Any]] = Field(
        default_factory=lambda: [{"fast": 10, "slow": 30}, {"fast": 20, "slow": 50}, {"fast": 30, "slow": 90}],
        description="候選參數組合",
    )
    train_days: int = Field(120, gt=0)
    test_days: int = Field(30, gt=0)
    step: int = Field(30, gt=0)


class WalkForwardFold(BaseModel):
    """單一 walk-forward 折"""
    train_range: List[int]
    test_range: List[int]
    best_params: Dict[str, Any]
    in_sample_sharpe: float
    out_of_sample: Dict[str, float]


class WalkForwardResponse(BaseModel):
    """Walk-forward 回測回應"""
    folds: List[WalkForwardFold]
    n_folds: int = 0
    avg_out_of_sample_sharpe: float = 0.0
    robust: bool = False
    errors: List[str] = Field(default_factory=list)


class StrategyComparisonRequest(BaseModel):
    """策略比較請求"""
    prices: List[float] = Field(..., description="歷史收盤價序列（舊→新）")
    strategies: List[str] = Field(
        default_factory=lambda: ["ma_crossover", "rsi", "macd", "combined"],
        description="要比較的內建策略名稱",
    )


class StrategyComparisonItem(BaseModel):
    """單一策略績效"""
    final_equity: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    n_trades: int
    equity_curve: List[float] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class StrategyComparisonResponse(BaseModel):
    """策略比較回應"""
    results: Dict[str, StrategyComparisonItem]


class PaperReplayRequest(BaseModel):
    """模擬下單(重放)請求"""
    prices: List[float] = Field(..., description="歷史收盤價序列（舊→新）")
    decision_signals: List[float] = Field(..., description="歷史信號序列（0/1，與 prices 同長）")


class PaperReplayResponse(BaseModel):
    """模擬下單回應"""
    strategy: StrategyComparisonItem
    buy_and_hold: StrategyComparisonItem
    outperformed: bool
