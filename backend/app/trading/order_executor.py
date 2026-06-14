"""
Order Executor - 訂單執行與結果處理
封裝從決策系統收到的交易指令，完成風控檢查、下單、結果回報。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .order_types import OrderRequest, OrderResponse, OrderSide, OrderType, TimeInForce
from .exchange_client import ExchangeClient

logger = logging.getLogger(__name__)


class OrderExecutionError(RuntimeError):
    """下單失敗的自訂例外"""
    pass


class OrderExecutor:
    """高層訂單執行器，提供簡潔 API 給決策系統使用"""

    def __init__(self, client: Optional[ExchangeClient] = None, use_mock: bool = True, **client_kwargs):
        if client:
            self.client = client
        else:
            self.client = ExchangeClient(use_mock=use_mock, **client_kwargs)
        self.logger = logging.getLogger(__name__)

    # ─── 主要執行入口 ────────────────────────────────────────
    def execute(self, symbol: str, side: str, quantity: float, order_type: str = "market", price: Optional[float] = None,
                stop_price: Optional[float] = None, time_in_force: str = "GTC", client_order_id: Optional[str] = None) -> OrderResponse:
        """下單並返回統一的 OrderResponse
        
        Args:
            symbol: 標的代碼
            side: "buy" 或 "sell"
            quantity: 數量（正值）
            order_type: "market"、"limit"、"stop"、"stop_limit"
            price: 限價或止損價格（視 order_type 而定）
            stop_price: 止損價格（止損單）
            time_in_force: GTC/IOC/FOK/DAY
            client_order_id: 客戶自訂 ID（可選）
        """
        # 1. 構建 OrderRequest
        request = OrderRequest(
            symbol=symbol,
            side=OrderSide(side),
            order_type=OrderType(order_type),
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=TimeInForce(time_in_force),
            client_order_id=client_order_id,
        )
        
        # 2. 調用 ExchangeClient
        response: OrderResponse = self.client.submit_order(request)
        
        if not response.success:
            self.logger.error(f"下單失敗: {response.error_message}")
            raise OrderExecutionError(response.error_message or "下單失敗")
        
        self.logger.info(f"下單成功: {response.order.order_id} ({symbol} {side} {quantity})")
        return response

    # ─── 補充工具 ────────────────────────────────────────
    def cancel(self, order_id: str) -> bool:
        """取消指定訂單"""
        result = self.client.cancel_order(order_id)
        if result:
            self.logger.info(f"訂單已取消: {order_id}")
        else:
            self.logger.warning(f"取消訂單失敗或不存在: {order_id}")
        return result

    def get_open_orders(self) -> List[Any]:
        return self.client.get_open_orders()

    def close(self) -> None:
        self.client.close()
