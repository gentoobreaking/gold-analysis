"""
Exchange Interface - 交易所接口抽象層
定義統一的交易所接口規範，支持多交易所適配。
目前為設計和模擬實現，不實際連接交易所。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Type

from .order_types import (
    Order,
    OrderSide,
    OrderType,
    OrderStatus,
    Position,
    PositionSide,
    AccountBalance,
    Trade,
    TimeInForce,
)
from .risk_rules import RiskRuleEngine, RiskRuleConfig

logger = logging.getLogger(__name__)


# ─── 接口數據模型 ───────────────────────────────────────────────────────────

@dataclass
class OrderRequest:
    """下單請求"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    client_order_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderResponse:
    """下單響應"""
    success: bool
    order: Optional[Order] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class MarketData:
    """實時市場數據"""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = "mock"
    
    @property
    def spread(self) -> float:
        return self.ask - self.bid
    
    @property
    def mid_price(self) -> float:
        return (self.bid + self.ask) / 2


# ─── 交易所接口抽象 ─────────────────────────────────────────────────────────

class ExchangeInterface(ABC):
    """
    交易所接口抽象基類
    
    定義所有交易所適配器必須實現的方法。
    子類需實現具體交易所的 API 調用邏輯。
    
    支持的交易所（待實現）:
    - OANDA (forex, commodities)
    - IG Markets (CFD)
    - Interactive Brokers
    - Alpaca (stocks, crypto)
    """
    
    # 交易所元信息
    exchange_name: str = "abstract"
    supported_order_types: List[OrderType] = []
    supported_symbols: List[str] = []
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        is_demo: bool = True,
        risk_config: Optional[RiskRuleConfig] = None,
    ):
        """
        初始化交易所接口
        
        Args:
            api_key: API Key
            api_secret: API Secret
            is_demo: 是否使用模擬/演示模式
            risk_config: 風控配置
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_demo = is_demo
        self.is_connected = False
        
        # 風控引擎
        self.risk_engine = RiskRuleEngine(risk_config)
        
        # 本地訂單簿（用於模擬模式）
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}
        self._account: Optional[AccountBalance] = None
        
        self.logger = logging.getLogger(f"{__name__}.{self.exchange_name}")
    
    # ─── 連接管理 ────────────────────────────────────────────────────────────
    
    @abstractmethod
    def connect(self) -> bool:
        """
        建立連接
        
        Returns:
            是否連接成功
        """
        raise NotImplementedError
    
    @abstractmethod
    def disconnect(self) -> None:
        """關閉連接"""
        raise NotImplementedError
    
    @abstractmethod
    def is_authenticated(self) -> bool:
        """檢查是否已認證"""
        raise NotImplementedError
    
    # ─── 帳戶查詢 ────────────────────────────────────────────────────────────
    
    @abstractmethod
    def get_account(self) -> AccountBalance:
        """獲取帳戶餘額"""
        raise NotImplementedError
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """獲取所有持倉"""
        raise NotImplementedError
    
    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """獲取指定標的持倉"""
        raise NotImplementedError
    
    # ─── 市場數據 ────────────────────────────────────────────────────────────
    
    @abstractmethod
    def get_market_data(self, symbol: str) -> MarketData:
        """獲取實時市場數據"""
        raise NotImplementedError
    
    @abstractmethod
    def get_historical_prices(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1D",
    ) -> List[Dict[str, Any]]:
        """獲取歷史價格"""
        raise NotImplementedError
    
    # ─── 訂單操作 ────────────────────────────────────────────────────────────
    
    @abstractmethod
    def submit_order(self, request: OrderRequest) -> OrderResponse:
        """
        提交訂單
        
        完整的下單流程:
        1. 參數驗證
        2. 風控檢查
        3. 發送到交易所
        4. 返回結果
        """
        raise NotImplementedError
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """取消訂單"""
        raise NotImplementedError
    
    @abstractmethod
    def get_order(self, order_id: str) -> Optional[Order]:
        """查詢訂單狀態"""
        raise NotImplementedError
    
    @abstractmethod
    def get_open_orders(self) -> List[Order]:
        """獲取所有未完成訂單"""
        raise NotImplementedError
    
    # ─── 通用工具 ────────────────────────────────────────────────────────────
    
    def _validate_symbol(self, symbol: str) -> None:
        """驗證標的是否受支持"""
        if self.supported_symbols and symbol not in self.supported_symbols:
            raise ValueError(f"標的 {symbol} 不受 {self.exchange_name} 支持")
    
    def _apply_risk_check(self, request: OrderRequest) -> Tuple[bool, List]:
        """應用風控檢查"""
        account = self.get_account()
        position = self.get_position(request.symbol)
        open_orders = self.get_open_orders()
        
        price = request.price or self.get_market_data(request.symbol).last
        
        return self.risk_engine.check(
            order_side=request.side.value,
            symbol=request.symbol,
            quantity=request.quantity,
            price=price,
            position=position,
            account=account,
            existing_orders=[o.to_dict() for o in open_orders],
        )


# ─── 模擬交易所實現 ─────────────────────────────────────────────────────────

class MockExchange(ExchangeInterface):
    """
    模擬交易所 - 測試/開發用
    
    在內存中模擬真實交易所行為，
    不需要真實 API 密鑰即可測試整個交易流程。
    
    特性:
    - 訂單簿管理
    - 持倉追蹤
    - 帳戶餘額更新
    - 模擬成交（根據市場價格）
    """
    
    exchange_name = "MOCK"
    supported_order_types = list(OrderType)
    supported_symbols = ["GOLD", "XAUUSD", "GC.CMDTY", "EURUSD"]
    
    def __init__(self, **kwargs):
        super().__init__(is_demo=True, **kwargs)
        self._mock_market: Dict[str, MarketData] = {}
        self._trades: List[Trade] = []
        self._base_price = 2000.0  # 黃金基礎價格
        
        # 初始化模擬帳戶
        self._account = AccountBalance(
            total_equity=100000.0,
            cash=100000.0,
            currency="USD",
            unrealized_pnl=0.0,
            realized_pnl_today=0.0,
            exchange=self.exchange_name,
        )
        
        # 初始化市場數據
        for symbol in self.supported_symbols:
            self._mock_market[symbol] = MarketData(
                symbol=symbol,
                bid=self._base_price - 0.5,
                ask=self._base_price + 0.5,
                last=self._base_price,
                volume=10000.0,
                source=self.exchange_name,
            )
        
        self.logger.info("MockExchange 初始化完成")
    
    def connect(self) -> bool:
        self.is_connected = True
        self.logger.info(f"[{self.exchange_name}] 連接成功 (模擬模式)")
        return True
    
    def disconnect(self) -> None:
        self.is_connected = False
        self.logger.info(f"[{self.exchange_name}] 連接已斷開")
    
    def is_authenticated(self) -> bool:
        return self.is_connected
    
    # ─── 帳戶 ────────────────────────────────────────────────────────────────
    
    def get_account(self) -> AccountBalance:
        """計算實時帳戶餘額（包含未實現盈虧）"""
        total_unrealized = sum(p.unrealized_pnl for p in self._positions.values())
        self._account.unrealized_pnl = total_unrealized
        self._account.total_equity = self._account.cash + total_unrealized
        return self._account
    
    def get_positions(self) -> List[Position]:
        return list(self._positions.values())
    
    def get_position(self, symbol: str) -> Optional[Position]:
        return self._positions.get(symbol)
    
    # ─── 市場數據 ────────────────────────────────────────────────────────────
    
    def get_market_data(self, symbol: str) -> MarketData:
        """返回模擬市場數據（帶隨機微小波動）"""
        import random
        base = self._mock_market.get(symbol)
        if not base:
            raise ValueError(f"未知標的: {symbol}")
        
        # 模擬微小價格波動（±0.1%）
        delta = random.uniform(-0.001, 0.001)
        last = base.last * (1 + delta)
        spread = base.spread
        
        return MarketData(
            symbol=symbol,
            bid=last - spread / 2,
            ask=last + spread / 2,
            last=last,
            volume=base.volume + random.uniform(-100, 100),
            timestamp=datetime.utcnow(),
            source=self.exchange_name,
        )
    
    def get_historical_prices(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1D",
    ) -> List[Dict[str, Any]]:
        """生成模擬歷史數據"""
        import random
        prices = []
        current = self._base_price
        delta_days = (end - start).days or 1
        
        for i in range(min(delta_days, 365)):
            date = start + timedelta(days=i)
            change = random.uniform(-0.02, 0.025)  # 日波動 ±2.5%
            current = current * (1 + change)
            prices.append({
                "date": date.isoformat(),
                "open": current * (1 + random.uniform(-0.005, 0.005)),
                "high": current * (1 + random.uniform(0, 0.01)),
                "low": current * (1 + random.uniform(-0.01, 0)),
                "close": current,
                "volume": random.uniform(5000, 20000),
            })
        
        return prices
    
    # ─── 訂單 ────────────────────────────────────────────────────────────────
    
    def submit_order(self, request: OrderRequest) -> OrderResponse:
        """提交模擬訂單"""
        self.logger.info(
            f"收到下單請求: {request.side.value.upper()} "
            f"{request.quantity} {request.symbol} @ "
            f"{request.order_type.value} "
            f"{request.price or 'MARKET'}"
        )
        
        # 風控檢查
        passed, results = self._apply_risk_check(request)
        if not passed:
            blocked = [r for r in results if r.is_blocked]
            return OrderResponse(
                success=False,
                error_code="RISK_BLOCKED",
                error_message=blocked[0].message if blocked else "風控阻斷",
                raw_response={"risk_results": results},
            )
        
        # 創建訂單
        market = self.get_market_data(request.symbol)
        fill_price = request.price or market.last
        
        order = Order(
            order_id=self._generate_order_id(),
            client_order_id=request.client_order_id,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            price=request.price,
            stop_price=request.stop_price,
            status=OrderStatus.SUBMITTED,
            time_in_force=request.time_in_force,
            exchange=self.exchange_name,
        )
        
        # 模擬立即成交（市價單）或掛單（限價單）
        if request.order_type == OrderType.MARKET:
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.avg_fill_price = fill_price
            order.commission = fill_price * order.quantity * 0.0002  # 0.02% 手續費
            
            # 更新持倉
            self._update_position(order)
            # 更新帳戶
            self._update_account(order)
            # 記錄成交
            trade = Trade(
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.filled_quantity,
                price=order.avg_fill_price,
                commission=order.commission,
            )
            self._trades.append(trade)
            
            self.logger.info(
                f"訂單成交: {order.order_id} | "
                f"{order.side.value.upper()} {order.filled_quantity} "
                f"@{order.avg_fill_price:.2f}"
            )
        else:
            order.status = OrderStatus.SUBMITTED
            self.logger.info(f"掛單成功: {order.order_id}")
        
        self._orders[order.order_id] = order
        return OrderResponse(success=True, order=order)
    
    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if not order:
            return False
        
        if order.is_closed:
            return False
        
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.utcnow()
        self.logger.info(f"訂單已取消: {order_id}")
        return True
    
    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)
    
    def get_open_orders(self) -> List[Order]:
        return [o for o in self._orders.values() if not o.is_closed]
    
    # ─── 私有工具 ────────────────────────────────────────────────────────────
    
    def _generate_order_id(self) -> str:
        import uuid
        return f"MOCK-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    def _update_position(self, order: Order) -> None:
        """更新持倉"""
        pos = self._positions.get(order.symbol)
        
        if order.side == OrderSide.BUY:
            if pos is None:
                self._positions[order.symbol] = Position(
                    symbol=order.symbol,
                    side=PositionSide.LONG,
                    quantity=order.filled_quantity,
                    avg_entry_price=order.avg_fill_price,
                    exchange=self.exchange_name,
                )
            else:
                # 計算新平均價
                total_cost = pos.cost_basis + order.filled_quantity * order.avg_fill_price
                total_qty = pos.quantity + order.filled_quantity
                pos.quantity = total_qty
                pos.avg_entry_price = total_cost / total_qty
        
        elif order.side == OrderSide.SELL:
            if pos and pos.quantity >= order.filled_quantity:
                pos.quantity -= order.filled_quantity
                if pos.quantity < 1e-8:
                    del self._positions[order.symbol]
            elif pos:
                # 不足，先平倉再反向開倉（簡化處理）
                self._positions[order.symbol] = Position(
                    symbol=order.symbol,
                    side=PositionSide.SHORT,
                    quantity=order.filled_quantity - pos.quantity,
                    avg_entry_price=order.avg_fill_price,
                    exchange=self.exchange_name,
                )
                del self._positions[order.symbol]
    
    def _update_account(self, order: Order) -> None:
        """更新帳戶餘額"""
        if order.side == OrderSide.BUY:
            self._account.cash -= order.total_value + order.commission
        else:
            self._account.cash += order.total_value - order.commission
    
    def get_trades(self) -> List[Trade]:
        """獲取所有成交記錄"""
        return self._trades


# ─── OANDA 交易所適配器（骨架，設計階段）────────────────────────────────────

class OANDAAdapter(ExchangeInterface):
    """
    OANDA 交易所適配器
    
    OANDA 官網: https://www.oanda.com/
    API 文檔: https://developer.oanda.com/
    
    支持:
    - 外匯 (FX)
    - 貴金屬 (GOLD, SILVER)
    - 大宗商品
    
    ⚠️ 注意：此為設計實現，實際使用需要有效的 OANDA 帳戶和 API Token
    """
    
    exchange_name = "OANDA"
    supported_order_types = [
        OrderType.MARKET,
        OrderType.LIMIT,
        OrderType.STOP,
        OrderType.STOP_LIMIT,
    ]
    supported_symbols = [
        # FX majors
        "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF",
        # Commodities
        "XAU_USD",  # Gold
        "XAG_USD",  # Silver
        # More symbols...
    ]
    
    # API 端點
    BASE_URL_LIVE = "https://api-oanda.com/v3"
    BASE_URL_DEMO = "https://streaming.oanda.com/v3"
    
    def __init__(
        self,
        account_id: Optional[str] = None,
        api_key: Optional[str] = None,
        is_demo: bool = True,
        **kwargs,
    ):
        super().__init__(api_key=api_key, is_demo=is_demo, **kwargs)
        self.account_id = account_id
        self._session = None  # requests.Session
    
    def connect(self) -> bool:
        if self.is_demo:
            self.logger.warning("OANDA 演示模式：實際不連接真實 API")
            self.is_connected = True
            return True
        
        # TODO: 實現真實的 API 連接
        raise NotImplementedError("請先填入有效的 OANDA API 密鑰")
    
    def disconnect(self) -> None:
        if self._session:
            self._session.close()
        self.is_connected = False
    
    def is_authenticated(self) -> bool:
        return self.is_connected and bool(self.api_key)
    
    def get_account(self) -> AccountBalance:
        # TODO: 調用 GET /v3/accounts/{accountID}
        raise NotImplementedError()
    
    def get_positions(self) -> List[Position]:
        raise NotImplementedError()
    
    def get_position(self, symbol: str) -> Optional[Position]:
        raise NotImplementedError()
    
    def get_market_data(self, symbol: str) -> MarketData:
        # TODO: 調用 GET /v3/accounts/{accountID}/pricing
        raise NotImplementedError()
    
    def get_historical_prices(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1D",
    ) -> List[Dict[str, Any]]:
        # TODO: 調用 GET /v3/instruments/{instrument}/candles
        raise NotImplementedError()
    
    def submit_order(self, request: OrderRequest) -> OrderResponse:
        # TODO: 調用 POST /v3/accounts/{accountID}/orders
        raise NotImplementedError()
    
    def cancel_order(self, order_id: str) -> bool:
        # TODO: 調用 PUT /v3/accounts/{accountID}/orders/{orderID}/cancel
        raise NotImplementedError()
    
    def get_order(self, order_id: str) -> Optional[Order]:
        raise NotImplementedError()
    
    def get_open_orders(self) -> List[Order]:
        raise NotImplementedError()
