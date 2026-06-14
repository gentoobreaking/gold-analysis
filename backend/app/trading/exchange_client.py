"""
Exchange Client - 高層封裝交易所互動
提供簡潔的 API 供決策系統調用，以便在未來替換實際交易所實現。
目前使用 MockExchange 作為後端實現，保持安全且可測試。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .exchange_interface import (
    ExchangeInterface,
    OrderRequest,
    OrderResponse,
    MarketData,
    MockExchange,
)

logger = logging.getLogger(__name__)


class ExchangeClient:
    """高層交易所客戶端，封裝底層 ExchangeInterface"""

    def __init__(self, use_mock: bool = True, **kwargs):
        """初始化交易所客戶端
        
        Args:
            use_mock: 是否使用 MockExchange（開發測試）
            **kwargs: 交給底層 ExchangeInterface 的參數（如 api_key）
        """
        self.use_mock = use_mock
        if use_mock:
            self.exchange: ExchangeInterface = MockExchange(**kwargs)
        else:
            # TODO: 根據配置動態加載實際交易所適配器（OANDA、IG 等）
            raise NotImplementedError("實際交易所適配器尚未實現，請配置 use_mock=True")
        
        self.exchange.connect()
        logger.info(f"ExchangeClient 初始化完成 (use_mock={use_mock})")

    # ─── 基礎 API ────────────────────────────────────────────────
    def get_market_data(self, symbol: str) -> MarketData:
        return self.exchange.get_market_data(symbol)

    def get_account_balance(self) -> Any:
        return self.exchange.get_account()

    def get_positions(self) -> List[Any]:
        return self.exchange.get_positions()

    def submit_order(self, request: OrderRequest) -> OrderResponse:
        return self.exchange.submit_order(request)

    def cancel_order(self, order_id: str) -> bool:
        return self.exchange.cancel_order(order_id)

    def get_open_orders(self) -> List[Any]:
        return self.exchange.get_open_orders()

    # ─── 清理資源 ────────────────────────────────────────────────
    def close(self) -> None:
        self.exchange.disconnect()
        logger.info("ExchangeClient 已關閉連接")
