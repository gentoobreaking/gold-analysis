"""
Order Types and Data Models - 訂單類型與數據模型
定義交易系統中使用的所有訂單、持倉、帳戶等核心數據結構。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional


# ─── 枚舉類 ─────────────────────────────────────────────────────────────────

class OrderSide(str, Enum):
    """訂單方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """訂單類型"""
    MARKET = "market"          # 市價單
    LIMIT = "limit"            # 限價單
    STOP = "stop"              # 止損單
    STOP_LIMIT = "stop_limit"  # 止損限價單
    TAKE_PROFIT = "take_profit"  # 止盈單


class OrderStatus(str, Enum):
    """訂單狀態"""
    PENDING = "pending"        # 待成交
    SUBMITTED = "submitted"    # 已提交
    PARTIAL = "partial"        # 部分成交
    FILLED = "filled"          # 完全成交
    CANCELLED = "cancelled"    # 已取消
    REJECTED = "rejected"      # 被拒絕
    EXPIRED = "expired"        # 已過期


class PositionSide(str, Enum):
    """持倉方向（期貨/杠桿）"""
    LONG = "long"
    SHORT = "short"
    NET = "net"  # 現貨/合一帳戶


class TimeInForce(str, Enum):
    """訂單有效期"""
    GTC = "GTC"   # Good Till Canceled（永久有效直至取消）
    IOC = "IOC"  # Immediate Or Cancel（即時或取消）
    FOK = "FOK"  # Fill Or Kill（全數成交或取消）
    DAY = "DAY"  # 當日有效


# ─── 數據類別 ───────────────────────────────────────────────────────────────

@dataclass
class Order:
    """
    訂單數據模型
    
    Attributes:
        order_id: 交易所返回的訂單 ID
        client_order_id: 客戶端生成的訂單 ID（用於追蹤）
        symbol: 標的代碼（如 GOLD, GC.CMDTY）
        side: 買入或賣出
        order_type: 訂單類型
        quantity: 數量
        price: 掛牌價格（限價單/止損限價單）
        stop_price: 觸發價格（止損單/止損限價單）
        status: 當前狀態
        filled_quantity: 已成交數量
        avg_fill_price: 平均成交價
        commission: 交易手續費
        time_in_force: 有效期
        created_at: 創建時間
        updated_at: 更新時間
        notes: 備註
    """
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    order_id: Optional[str] = None
    client_order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    time_in_force: TimeInForce = TimeInForce.GTC
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
    exchange: str = "mock"  # 交易所名稱
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def remaining_quantity(self) -> float:
        """剩餘未成交數量"""
        return max(0.0, self.quantity - self.filled_quantity)
    
    @property
    def is_closed(self) -> bool:
        """訂單是否已結束（成交/取消/拒絕/過期）"""
        return self.status in {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
        }
    
    @property
    def total_value(self) -> float:
        """訂單總價值"""
        return self.avg_fill_price * self.filled_quantity
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "avg_fill_price": self.avg_fill_price,
            "remaining_quantity": self.remaining_quantity,
            "commission": self.commission,
            "total_value": self.total_value,
            "time_in_force": self.time_in_force.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "exchange": self.exchange,
            "notes": self.notes,
            "metadata": self.metadata,
        }


@dataclass
class Position:
    """
    持倉數據模型
    
    Attributes:
        symbol: 標的代碼
        side: 持倉方向
        quantity: 持倉數量
        avg_entry_price: 平均進場價
        current_price: 當前市場價格
        unrealized_pnl: 未實現盈虧
        realized_pnl: 已實現盈虧
        opened_at: 開倉時間
        exchange: 交易所
    """
    symbol: str
    side: PositionSide
    quantity: float
    avg_entry_price: float
    current_price: float = 0.0
    realized_pnl: float = 0.0
    opened_at: datetime = field(default_factory=datetime.utcnow)
    exchange: str = "mock"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def market_value(self) -> float:
        """市值"""
        return self.quantity * self.current_price
    
    @property
    def unrealized_pnl(self) -> float:
        """未實現盈虧"""
        if self.side == PositionSide.LONG:
            return (self.current_price - self.avg_entry_price) * self.quantity
        elif self.side == PositionSide.SHORT:
            return (self.avg_entry_price - self.current_price) * self.quantity
        else:
            return (self.current_price - self.avg_entry_price) * self.quantity
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """未實現盈虧百分比"""
        if self.avg_entry_price == 0:
            return 0.0
        return self.unrealized_pnl / (self.avg_entry_price * self.quantity) * 100
    
    @property
    def cost_basis(self) -> float:
        """持倉成本"""
        return self.avg_entry_price * self.quantity
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "avg_entry_price": self.avg_entry_price,
            "current_price": self.current_price,
            "cost_basis": self.cost_basis,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "realized_pnl": self.realized_pnl,
            "opened_at": self.opened_at.isoformat(),
            "exchange": self.exchange,
        }


@dataclass
class AccountBalance:
    """
    帳戶餘額數據模型
    
    Attributes:
        total_equity: 總資產（帳戶淨值）
        cash: 可用現金
        buying_power: 購買力
        currency: 結算貨幣
        margin_used: 已使用保證金
        margin_available: 可用保證金
        unrealized_pnl: 總未實現盈虧
        realized_pnl_today: 今日已實現盈虧
    """
    total_equity: float
    cash: float
    currency: str = "USD"
    margin_used: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl_today: float = 0.0
    exchange: str = "mock"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def buying_power(self) -> float:
        """購買力（可用現金）"""
        return self.cash
    
    @property
    def margin_available(self) -> float:
        """可用保證金"""
        return max(0.0, self.total_equity - self.margin_used)
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            "total_equity": self.total_equity,
            "cash": self.cash,
            "currency": self.currency,
            "margin_used": self.margin_used,
            "margin_available": self.margin_available,
            "buying_power": self.buying_power,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl_today": self.realized_pnl_today,
            "exchange": self.exchange,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Trade:
    """
    成交記錄
    
    Attributes:
        trade_id: 成交 ID
        order_id: 關聯訂單 ID
        symbol: 標的
        side: 方向
        quantity: 成交數量
        price: 成交價格
        commission: 手續費
        timestamp: 成交時間
    """
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    order_id: Optional[str] = None
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    price: float = 0.0
    commission: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def value(self) -> float:
        return self.quantity * self.price
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": self.price,
            "value": self.value,
            "commission": self.commission,
            "timestamp": self.timestamp.isoformat(),
        }
