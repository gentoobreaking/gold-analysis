"""
Exchange Client - 高層封裝交易所互動
提供簡潔的 API 供決策系統調用，以便在未來替換實際交易所實現。
目前使用 MockExchange 作為後端實現，保持安全且可測試。
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .exchange_interface import (
    ExchangeInterface,
    OrderRequest,
    OrderResponse,
    MarketData,
    MockExchange,
)
from .order_types import Order, OrderSide, OrderType, OrderStatus, Position

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
class RestExchangeClient:
    """Generic v20-style REST client (OANDA / IG compatible).

    Speaks a thin slice of the v20 REST API via the standard library so the same
    code path drives a real broker once credentials are supplied. ``opener`` is
    injectable (an ``urllib`` OpenerDirector, or any object with ``.open``) so
    tests can mock HTTP without sockets.
    """

    def __init__(self, base_url: str, api_key: str, account_id: Optional[str] = None, opener: Any = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.account_id = account_id
        self.opener = opener or urllib.request.build_opener()

    # ── HTTP helpers ─────────────────────────────────────────
    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _request(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        with self.opener.open(req) as resp:  # type: ignore[union-attr]
            raw = resp.read()
        return json.loads(raw or b"{}")

    # ── ExchangeClient-compatible surface ────────────────────
    def get_market_data(self, symbol: str) -> MarketData:
        params = f"?instruments={urllib.parse.quote(symbol)}"
        resp = self._request("GET", f"/v3/accounts/{self.account_id}/pricing{params}")
        quotes = (resp.get("prices") or [{}])[0]
        bids = quotes.get("bids") or [{}]
        asks = quotes.get("asks") or [{}]
        return MarketData(
            symbol=symbol,
            bid=float((bids[0].get("price") if bids else 0) or 0),
            ask=float((asks[0].get("price") if asks else 0) or 0),
            last=float(quotes.get("closeoutBid") or quotes.get("closeoutAsk") or 0),
            volume=0.0,
            timestamp=quotes.get("time"),
            source="rest",
        )

    def get_account_balance(self) -> Dict[str, Any]:
        resp = self._request("GET", f"/v3/accounts/{self.account_id}/summary")
        return resp.get("account") or resp

    def get_positions(self) -> List[Position]:
        resp = self._request("GET", f"/v3/accounts/{self.account_id}/positions")
        out: List[Position] = []
        for p in resp.get("positions") or []:
            out.append(
                Position(
                    symbol=p.get("instrument", ""),
                    side=OrderSide.BUY,
                    quantity=float(p.get("long", {}).get("units") or 0),
                    avg_entry_price=0.0,
                    current_price=0.0,
                    realized_pnl=0.0,
                    opened_at=None,
                    exchange="rest",
                )
            )
        return out

    def submit_order(self, request: OrderRequest) -> OrderResponse:
        units = request.quantity if request.side == OrderSide.BUY else -request.quantity
        payload = {
            "order": {
                "instrument": request.symbol,
                "units": str(units),
                "type": "MARKET" if request.order_type == OrderType.MARKET else "LIMIT",
                "timeInForce": "FOK",
            }
        }
        try:
            resp = self._request("POST", f"/v3/accounts/{self.account_id}/orders", payload)
            txn = resp.get("orderFillTransaction") or resp.get("orderCreateTransaction") or {}
            ok = bool(txn)
            order = Order(
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                order_id=txn.get("id"),
                status=OrderStatus.FILLED if ok else OrderStatus.REJECTED,
                time_in_force=request.time_in_force,
            )
            return OrderResponse(success=ok, order=order, raw_response=resp)
        except Exception as exc:  # noqa: BLE001
            return OrderResponse(success=False, order=None, error_message=str(exc))

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._request("PUT", f"/v3/accounts/{self.account_id}/orders/{order_id}/cancel")
            return True
        except Exception:  # noqa: BLE001
            return False

    def get_open_orders(self) -> List[Any]:
        try:
            resp = self._request("GET", f"/v3/accounts/{self.account_id}/pendingOrders")
            return resp.get("orders") or []
        except Exception:  # noqa: BLE001
            return []

    def close(self) -> None:
        return None
