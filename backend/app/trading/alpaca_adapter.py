"""
Alpaca Exchange Adapter - Alpaca 現貨/期貨交易所適配器

Alpaca 官網: https://alpaca.markets/
API 文檔: https://docs.alpaca.markets/
Python SDK: pip install alpaca-trade-api

支持:
  - 現貨股票 (US equities)
  - 期貨 (commodities)
  - 加密貨幣 (crypto)

⚠️ 實盤前請確認:
  1. ALPACA_PAPER=true（先在 Paper 環境測試）
  2. API Key 有正確的交易權限 ( TRADING role )
  3. 標的(symbol)在 Alpaca 系統中有報價
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.exceptions import RequestException

from .exchange_interface import (
    ExchangeInterface,
    MarketData as ExchangeMarketData,
    OrderRequest,
    OrderResponse,
)
from .order_types import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
    AccountBalance,
    Trade,
    TimeInForce,
)
from .risk_rules import RiskRuleConfig

logger = logging.getLogger(__name__)


# ─── Alpaca ↔ Internal 標的映射 ──────────────────────────────────────────────

# Alpaca 使用的標的代碼（需與 Alpaca 帳號支援的資產一致）
# Alpaca 現貨: AAPL, TSLA, SPY, GLD 等
# Alpaca 期貨: GC (Gold), SI (Silver), PL (Platinum) 等（需開通期貨權限）
# 黃金相關 ETF: GLD, GDX, IAU
ALPACA_SYMBOLS = {
    "GOLD":   "GLD",    # SPDR Gold Shares (現貨黃金 ETF)
    "XAUUSD": "GLD",    # 黃金現貨 → 映射到 GLD ETF
    "SILVER": "SLV",    # iShares Silver Trust
    "SPY":    "SPY",    # S&P 500 ETF
    "AAPL":   "AAPL",   # Apple
    "TSLA":   "TSLA",   # Tesla
    # 更多可擴展...
}

# Internal Symbol → Alpaca Symbol
def to_alpaca_symbol(symbol: str) -> str:
    """將內部標的代碼轉換為 Alpaca 標的代碼"""
    return ALPACA_SYMBOLS.get(symbol, symbol)

# Alpaca Symbol → Internal Symbol
def from_alpaca_symbol(alpaca_symbol: str) -> str:
    """將 Alpaca 標的代碼轉換為內部代碼"""
    for internal, alpaca in ALPACA_SYMBOLS.items():
        if alpaca == alpaca_symbol:
            return internal
    return alpaca_symbol


# ─── Alpaca API 回應狀態映射 ────────────────────────────────────────────────

def _map_alpaca_order_status(raw: str) -> OrderStatus:
    """將 Alpaca API 回應的訂單狀態轉換為內部枚舉"""
    mapping = {
        "pending_new":      OrderStatus.PENDING,
        "new":              OrderStatus.SUBMITTED,
        "partially_filled": OrderStatus.PARTIAL,
        "filled":           OrderStatus.FILLED,
        "done_for_day":     OrderStatus.EXPIRED,
        "cancelled":        OrderStatus.CANCELLED,
        "expired":          OrderStatus.EXPIRED,
        "rejected":         OrderStatus.REJECTED,
        "stopped":          OrderStatus.REJECTED,
        "accepted":         OrderStatus.SUBMITTED,
        "pending_cancel":   OrderStatus.SUBMITTED,
        "pending_replace":  OrderStatus.SUBMITTED,
        "replaced":         OrderStatus.SUBMITTED,
    }
    return mapping.get(raw, OrderStatus.PENDING)


def _map_alpaca_side(raw: str) -> OrderSide:
    return OrderSide.BUY if raw == "buy" else OrderSide.SELL


def _map_time_in_force(raw: str) -> TimeInForce:
    """將 Alpaca time_in_force 轉換為內部枚舉"""
    mapping = {
        "day":  TimeInForce.DAY,
        "gtc":  TimeInForce.GTC,
        "ioc":  TimeInForce.IOC,
        "fok":  TimeInForce.FOK,
        "opg":  TimeInForce.DAY,
        "cls":  TimeInForce.DAY,
    }
    return mapping.get(raw, TimeInForce.GTC)


# ─── AlpacaExchange 實現 ─────────────────────────────────────────────────────

class AlpacaExchange(ExchangeInterface):
    """
    Alpaca 交易所適配器

    支持兩種模式:
    - Paper Trading (模擬交易，無實際資金風險)
    - Live Trading (實盤，真實資金)

    使用方式:
        # 從環境變數初始化（推薦）
        adapter = AlpacaExchange.from_env()

        # 直接傳入
        adapter = AlpacaExchange(
            api_key="PK...",
            api_secret="Sec...",
            is_demo=True,          # Paper Trading
        )

        adapter.connect()
        account = adapter.get_account()
        market  = adapter.get_market_data("GOLD")
    """

    exchange_name = "ALPACA"
    supported_order_types = [
        OrderType.MARKET,
        OrderType.LIMIT,
        OrderType.STOP,
        OrderType.STOP_LIMIT,
    ]
    # Alpaca 支援的標的（需帳號有權限）
    supported_symbols = list(ALPACA_SYMBOLS.keys())

    # API 端點
    BASE_URL_PAPER  = "https://paper-api.alpaca.markets"
    BASE_URL_LIVE   = "https://api.alpaca.markets"
    CRYPTO_BASE_URL = "https://data.alpaca.markets"

    # HTTP Header 版本
    HEADER_APCA_API_VERSION = "v2"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        is_demo: bool = True,
        base_url: Optional[str] = None,
        risk_config: Optional[RiskRuleConfig] = None,
        timeout: int = 15,
    ):
        """
        初始化 Alpaca 適配器

        Args:
            api_key:     Alpaca API Key
            api_secret:  Alpaca API Secret
            is_demo:     True=Paper Trading, False=Live Trading
            base_url:    可自訂端點（預設自動根據 is_demo 選擇）
            risk_config: 風控配置
            timeout:     HTTP 請求超時（秒）
        """
        super().__init__(
            api_key=api_key,
            api_secret=api_secret,
            is_demo=is_demo,
            risk_config=risk_config,
        )

        self.base_url = (
            base_url
            or (self.BASE_URL_PAPER if is_demo else self.BASE_URL_LIVE)
        )
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "APCA-API-KEY-ID":     self.api_key or "",
            "APCA-API-SECRET-KEY": self.api_secret or "",
            "Content-Type":        "application/json",
        })
        self.logger = logging.getLogger(f"{__name__}.AlpacaExchange")

        # 本地訂單簿（快取 Alpaca 的訂單狀態，減少 API 調用）
        self._orders:     Dict[str, Order]  = {}
        self._positions:  Dict[str, Position] = {}
        self._account:    Optional[AccountBalance] = None

    # ─── 工廠方法 ───────────────────────────────────────────────────────────

    @classmethod
    def from_env(cls, risk_config: Optional[RiskRuleConfig] = None) -> "AlpacaExchange":
        """
        從環境變數建立實例

        讀取變數:
          ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER, ALPACA_BASE_URL
        """
        from dotenv import load_dotenv
        load_dotenv()

        api_key    = os.getenv("ALPACA_API_KEY")    or os.getenv("APCA_API_KEY_ID")
        api_secret = os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY")
        is_demo    = os.getenv("ALPACA_PAPER", "true").lower() != "false"
        base_url   = os.getenv("ALPACA_BASE_URL")

        if not api_key or not api_secret:
            raise ValueError(
                "缺少 Alpaca API 憑證。請設定 ALPACA_API_KEY 和 ALPACA_SECRET_KEY 環境變數，"
                "或使用 AlpacaExchange(api_key=..., api_secret=...) 直接傳入。"
            )

        return cls(
            api_key=api_key,
            api_secret=api_secret,
            is_demo=is_demo,
            base_url=base_url,
            risk_config=risk_config,
        )

    # ─── 連接管理 ───────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """驗證 API 憑證是否有效"""
        try:
            resp = self._get("/account")
            resp.raise_for_status()
            self.is_connected = True
            mode = "Paper Trading" if self.is_demo else "Live Trading"
            self.logger.info(f"[Alpaca] 連接成功（{mode}）")
            return True
        except RequestException as e:
            self.logger.error(f"[Alpaca] 連接失敗: {e}")
            self.is_connected = False
            return False

    def disconnect(self) -> None:
        self._session.close()
        self.is_connected = False
        self.logger.info("[Alpaca] 連接已斷開")

    def is_authenticated(self) -> bool:
        return self.is_connected and bool(self.api_key and self.api_secret)

    # ─── 私有 HTTP 工具 ─────────────────────────────────────────────────────

    def _get(self, path: str, params: Optional[Dict] = None) -> requests.Response:
        url = f"{self.base_url}/{self.HEADER_APCA_API_VERSION}{path}"
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp

    def _post(self, path: str, json: Optional[Dict] = None) -> requests.Response:
        url = f"{self.base_url}/{self.HEADER_APCA_API_VERSION}{path}"
        resp = self._session.post(url, json=json, timeout=self.timeout)
        resp.raise_for_status()
        return resp

    def _delete(self, path: str) -> requests.Response:
        url = f"{self.base_url}/{self.HEADER_APCA_API_VERSION}{path}"
        resp = self._session.delete(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp

    def _request(self, method: str, path: str,
                 json: Optional[Dict] = None) -> requests.Response:
        """通用 HTTP 請求（自動處理 429 Retry-After）"""
        url = f"{self.base_url}/{self.HEADER_APCA_API_VERSION}{path}"
        for attempt in range(3):
            resp = self._session.request(
                method, url, json=json, timeout=self.timeout
            )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                self.logger.warning(f"[Alpaca] Rate limit，{retry_after}s 後重試...")
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp
        raise RequestException("重試次數耗盡")

    # ─── 帳戶查詢 ───────────────────────────────────────────────────────────

    def get_account(self) -> AccountBalance:
        """
        獲取帳戶資訊

        API: GET /account
        Doc: https://docs.alpaca.markets/reference/getaccount
        """
        resp = self._get("/account").json()

        self._account = AccountBalance(
            total_equity=        float(resp.get("equity", 0)),
            cash=                float(resp.get("cash", 0)),
            currency=            resp.get("currency", "USD"),
            margin_used=         float(resp.get("margin_used", 0)),
            unrealized_pnl=      float(resp.get("equity", 0)) - float(resp.get("cash", 0)),
            realized_pnl_today= float(resp.get("last_day_turnover", 0)),
            exchange=self.exchange_name,
            timestamp=datetime.now(timezone.utc),
        )
        return self._account

    def get_positions(self) -> List[Position]:
        """
        獲取所有持倉

        API: GET /positions
        Doc: https://docs.alpaca.markets/reference/getpositions
        """
        resp = self._get("/positions")
        raw_positions: List[Dict] = resp.json()

        self._positions.clear()
        positions: List[Position] = []

        for p in raw_positions:
            symbol = from_alpaca_symbol(p["symbol"])
            pos = Position(
                symbol=symbol,
                side=PositionSide.LONG if float(p["qty"]) > 0 else PositionSide.SHORT,
                quantity=abs(float(p["qty"])),
                avg_entry_price=float(p["avg_entry_price"]),
                current_price=float(p.get("current_price", 0)),
                realized_pnl=float(p.get("unrealized_pl", 0)) * (
                    -1 if float(p["qty"]) < 0 else 1
                ),
                exchange=self.exchange_name,
            )
            self._positions[symbol] = pos
            positions.append(pos)

        return positions

    def get_position(self, symbol: str) -> Optional[Position]:
        """
        獲取指定標的持倉

        API: GET /positions/{symbol}
        """
        alpaca_sym = to_alpaca_symbol(symbol)
        try:
            resp = self._get(f"/positions/{alpaca_sym}").json()
            pos = Position(
                symbol=symbol,
                side=PositionSide.LONG if float(resp["qty"]) > 0 else PositionSide.SHORT,
                quantity=abs(float(resp["qty"])),
                avg_entry_price=float(resp["avg_entry_price"]),
                current_price=float(resp.get("current_price", 0)),
                realized_pnl=float(resp.get("unrealized_pl", 0)),
                exchange=self.exchange_name,
            )
            self._positions[symbol] = pos
            return pos
        except RequestException:
            return self._positions.get(symbol)

    # ─── 市場數據 ───────────────────────────────────────────────────────────

    def get_market_data(self, symbol: str) -> ExchangeMarketData:
        """
        獲取實時報價（Last / Bid / Ask）

        API: GET /account/portfolio/net-liquid_value (非即時報價)
        實時報價使用: GET /market_data/stocks/{symbol}/quotes/latest
                      GET /market_data/stocks/{symbol}/trades/latest

        ⚠️ 即時市場數據需要 Alpaca Data 訂閱（付費）
           若無訂閱，此方法會拋出異常或返回估算值。

        回退邏輯:
          1. 嘗試即時報價（需 Data 訂閱）
          2. 嘗試前一交易日收盤價
          3. 若皆失敗，使用本地快取（最後一次成功報價）
        """
        alpaca_sym = to_alpaca_symbol(symbol)

        # ── 嘗試即時 Quote（需 Data 訂閱）──────────────────────────────────
        try:
            resp = self._get(
                f"/market_data/stocks/{alpaca_sym}/quotes/latest",
                params={"limit": 1},
            )
            data = resp.json().get("quote", {})
            if data:
                return ExchangeMarketData(
                    symbol=symbol,
                    bid=float(data.get("bp", 0)),
                    ask=float(data.get("ap", 0)),
                    last=float(data.get("ap", 0)),   # ask 作為 last 近似
                    volume=float(data.get("v", 0)),
                    timestamp=datetime.fromisoformat(
                        str(data.get("t") or datetime.now(timezone.utc).isoformat())
                    ).replace(tzinfo=timezone.utc),
                    source=self.exchange_name,
                )
        except RequestException as e:
            self.logger.debug(f"[Alpaca] 即時報價不可用: {e}，嘗試備用方案...")

        # ── 備用：前一交易日收盤價 ───────────────────────────────────────────
        try:
            bars = self._get(
                f"/market_data/stocks/{alpaca_sym}/bars",
                params={"timeframe": "1Day", "limit": 1},
            ).json().get("bars", [])

            if bars:
                bar = bars[0]
                price = float(bar["c"])
                return ExchangeMarketData(
                    symbol=symbol,
                    bid=price * 0.9995,
                    ask=price * 1.0005,
                    last=price,
                    volume=float(bar.get("v", 0)),
                    timestamp=datetime.fromisoformat(
                        bar["t"].replace("Z", "+00:00")
                    ),
                    source=self.exchange_name,
                )
        except RequestException as e:
            self.logger.warning(f"[Alpaca] 收盤價查詢失敗: {e}")

        # ── 完全失敗：拋出異常 ───────────────────────────────────────────────
        raise RequestException(
            f"[Alpaca] 無法獲取 {symbol} 市場數據。"
            "請確認：(1) Alpaca Data 訂閱已啟用，(2) 標的在帳號權限範圍內。"
        )

    def get_historical_prices(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1Day",
    ) -> List[Dict[str, Any]]:
        """
        獲取歷史 K 線

        API: GET /market_data/stocks/{symbol}/bars
        Doc:  https://docs.alpaca.markets/reference/getstockbars

        timeframe 可選: 1Min, 5Min, 15Min, 1Hour, 1Day
        """
        alpaca_sym = to_alpaca_symbol(symbol)

        # 格式化時間（ISO 8601 with timezone）
        start_str = start.astimezone(timezone.utc).isoformat()
        end_str   = end.astimezone(timezone.utc).isoformat()

        resp = self._get(
            f"/market_data/stocks/{alpaca_sym}/bars",
            params={
                "timeframe": timeframe,
                "start":     start_str,
                "end":       end_str,
                "limit":     1000,
                "adjustment": "split",      # 自動調整split/dividend
            },
        )

        bars = resp.json().get("bars", [])
        return [
            {
                "date":   bar["t"],
                "open":   bar["o"],
                "high":   bar["h"],
                "low":    bar["l"],
                "close":  bar["c"],
                "volume": bar["v"],
            }
            for bar in bars
        ]

    # ─── 訂單操作 ───────────────────────────────────────────────────────────

    def submit_order(self, request: OrderRequest) -> OrderResponse:
        """
        提交訂單

        API: POST /orders
        Doc: https://docs.alpaca.markets/reference/postorder

        ⚠️ Alpaca 現貨帳號交易規則:
          - 買入必須有足夠現金
          - 賣出必須有足夠持倉
          - 當日沖銷（T+0）需帳號開通 day trade 權限
        """
        alpaca_sym = to_alpaca_symbol(request.symbol)

        # ── 1. 參數驗證 ───────────────────────────────────────────────────────
        if request.quantity <= 0:
            return OrderResponse(
                success=False,
                error_code="INVALID_QUANTITY",
                error_message=f"數量必須 > 0，收到: {request.quantity}",
            )

        # ── 2. 風控檢查 ─────────────────────────────────────────────────────
        market = self.get_market_data(request.symbol)
        passed, results = self._apply_risk_check(request)
        if not passed:
            blocked = [r for r in results if r.is_blocked]
            return OrderResponse(
                success=False,
                error_code="RISK_BLOCKED",
                error_message=blocked[0].message if blocked else "風控阻斷",
                raw_response={"risk_results": [r.to_dict() for r in results]},
            )

        # ── 3. 構造 Alpaca API 請求 body ────────────────────────────────────
        body: Dict[str, Any] = {
            "symbol":        alpaca_sym,
            "side":          request.side.value,
            "type":          request.order_type.value,
            "qty":           str(request.quantity),
            "time_in_force": request.time_in_force.value.lower(),
        }

        # 限價單
        if request.price is not None:
            body["limit_price"] = str(request.price)

        # 止損單 / 止損限價單
        if request.stop_price is not None:
            body["stop_price"] = str(request.stop_price)

        # 用戶端訂單 ID（可選，方便對帳）
        client_id = request.client_order_id or str(uuid.uuid4())[:8]
        body["client_order_id"] = client_id

        # ── 4. 發送至 Alpaca ─────────────────────────────────────────────────
        try:
            resp = self._post("/orders", json=body)
            raw_order: Dict = resp.json()

            # ── 5. 包裝為內部 Order 物件 ──────────────────────────────────────
            order = Order(
                order_id=raw_order["id"],
                client_order_id=raw_order.get("client_order_id", client_id),
                symbol=request.symbol,
                side=_map_alpaca_side(raw_order["side"]),
                order_type=OrderType(raw_order["type"]),
                quantity=float(raw_order["qty"]),
                price=float(raw_order["limit_price"]) if raw_order.get("limit_price") else None,
                stop_price=float(raw_order["stop_price"]) if raw_order.get("stop_price") else None,
                status=_map_alpaca_order_status(raw_order["status"]),
                filled_quantity=float(raw_order.get("filled_qty", 0)),
                avg_fill_price=float(raw_order["filled_avg_price"])
                              if raw_order.get("filled_avg_price") else 0.0,
                time_in_force=_map_time_in_force(raw_order["time_in_force"]),
                created_at=_parse_alpaca_time(raw_order.get("created_at")),
                updated_at=_parse_alpaca_time(raw_order.get("updated_at")),
                exchange=self.exchange_name,
            )

            self._orders[order.order_id] = order
            self.logger.info(
                f"[Alpaca] 訂單已提交: {order.order_id} | "
                f"{order.side.value.upper()} {order.quantity} {order.symbol} "
                f"@ {order.order_type.value} {order.price or 'MARKET'}"
            )
            return OrderResponse(success=True, order=order, raw_response=raw_order)

        except RequestException as e:
            error_detail = _parse_alpaca_error(e)
            self.logger.error(f"[Alpaca] 訂單提交失敗: {error_detail}")
            return OrderResponse(
                success=False,
                error_code=error_detail.get("code", "UNKNOWN"),
                error_message=error_detail.get("message", str(e)),
            )

    def cancel_order(self, order_id: str) -> bool:
        """
        取消訂單

        API: DELETE /orders/{order_id}
        Doc: https://docs.alpaca.markets/reference/deleteorderbyorderid
        """
        try:
            self._delete(f"/orders/{order_id}")
            # 更新本地狀態
            if order_id in self._orders:
                self._orders[order_id].status = OrderStatus.CANCELLED
            self.logger.info(f"[Alpaca] 訂單已取消: {order_id}")
            return True
        except RequestException as e:
            self.logger.warning(f"[Alpaca] 取消訂單失敗 {order_id}: {e}")
            return False

    def get_order(self, order_id: str) -> Optional[Order]:
        """
        查詢訂單狀態

        API: GET /orders/{order_id}
        """
        # 優先返回本地快取（避免過度 API 調用）
        if order_id in self._orders:
            local = self._orders[order_id]
            # 已結束的訂單不需要刷新
            if local.is_closed:
                return local

        try:
            resp = self._get(f"/orders/{order_id}").json()
            order = self._raw_to_order(resp)
            self._orders[order_id] = order
            return order
        except RequestException:
            return self._orders.get(order_id)

    def get_open_orders(self) -> List[Order]:
        """
        獲取所有未完成訂單

        API: GET /orders?status=open
        """
        try:
            resp = self._get("/orders", params={"status": "open", "limit": 100})
            raw_orders: List[Dict] = resp.json()
            orders: List[Order] = []
            for raw in raw_orders:
                order = self._raw_to_order(raw)
                self._orders[order.order_id] = order
                orders.append(order)
            return orders
        except RequestException as e:
            self.logger.warning(f"[Alpaca] 查詢開倉訂單失敗: {e}")
            return [o for o in self._orders.values() if not o.is_closed]

    # ─── 私有工具 ───────────────────────────────────────────────────────────

    def _raw_to_order(self, raw: Dict) -> Order:
        """將 Alpaca API 回應轉換為內部 Order 物件"""
        return Order(
            order_id=raw["id"],
            client_order_id=raw.get("client_order_id", ""),
            symbol=from_alpaca_symbol(raw["symbol"]),
            side=_map_alpaca_side(raw["side"]),
            order_type=OrderType(raw["type"]),
            quantity=float(raw["qty"]),
            price=float(raw["limit_price"]) if raw.get("limit_price") else None,
            stop_price=float(raw["stop_price"]) if raw.get("stop_price") else None,
            status=_map_alpaca_order_status(raw["status"]),
            filled_quantity=float(raw.get("filled_qty", 0)),
            avg_fill_price=float(raw["filled_avg_price"])
                          if raw.get("filled_avg_price") else 0.0,
            time_in_force=_map_time_in_force(raw["time_in_force"]),
            created_at=_parse_alpaca_time(raw.get("created_at")),
            updated_at=_parse_alpaca_time(raw.get("updated_at")),
            exchange=self.exchange_name,
        )

    def get_trades(self) -> List[Trade]:
        """
        獲取帳戶所有成交記錄（最近 100 筆）

        API: GET /account/activities
        """
        try:
            resp = self._get(
                "/account/activities",
                params={"activity_type": "FILL", "limit": 100},
            )
            activities: List[Dict] = resp.json()
            trades: List[Trade] = []
            for act in activities:
                trades.append(Trade(
                    trade_id=act.get("id", ""),
                    order_id=act.get("order_id", ""),
                    symbol=from_alpaca_symbol(act.get("symbol", "")),
                    side=OrderSide.BUY if act.get("side") == "buy" else OrderSide.SELL,
                    quantity=float(act.get("qty", 0)),
                    price=float(act.get("price", 0)),
                    commission=float(act.get("commission", 0)),
                    timestamp=_parse_alpaca_time(act.get("transaction_time")),
                ))
            return trades
        except RequestException as e:
            self.logger.warning(f"[Alpaca] 獲取成交記錄失敗: {e}")
            return []

    def __repr__(self) -> str:
        mode = "PAPER" if self.is_demo else "LIVE"
        return f"<AlpacaExchange mode={mode} connected={self.is_connected}>"


# ─── 工具函式 ─────────────────────────────────────────────────────────────────

def _parse_alpaca_time(raw: Optional[str]) -> datetime:
    """解析 Alpaca API 回應的 ISO 8601 時間字串"""
    if not raw:
        return datetime.utcnow()
    # Alpaca 有兩種格式: "2024-01-02T15:00:00Z" 或 "2024-01-02T15:00:00.123456789Z"
    raw = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.utcnow()


def _parse_alpaca_error(exc: RequestException) -> Dict[str, str]:
    """從 HTTP 例外中解析 Alpaca API 錯誤訊息"""
    try:
        body = exc.response.json()
        return {
            "code":    body.get("code", ""),
            "message": body.get("message", str(exc)),
        }
    except Exception:
        return {"code": "NETWORK_ERROR", "message": str(exc)}


# ─── 快速測試入口 ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        # 從環境變數建立（推薦）
        adapter = AlpacaExchange.from_env()
        adapter.connect()

        print("=== 帳戶資訊 ===")
        print(json.dumps(adapter.get_account().to_dict(), indent=2, default=str))

        print("\n=== 市場報價 ===")
        for sym in ["GOLD", "SPY"]:
            try:
                mkt = adapter.get_market_data(sym)
                print(f"{sym}: bid={mkt.bid:.2f} ask={mkt.ask:.2f} last={mkt.last:.2f}")
            except Exception as e:
                print(f"{sym}: 無法獲取 ({e})")

        print("\n=== 提交測試單（限價單）===")
        req = OrderRequest(
            symbol="SPY",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1.0,
            price=450.0,
            time_in_force=TimeInForce.DAY,
        )
        resp = adapter.submit_order(req)
        print(f"結果: success={resp.success}")
        if resp.order:
            print(f"訂單ID: {resp.order.order_id}")
            # 測試取消
            adapter.cancel_order(resp.order.order_id)
            print("已取消測試單")

        adapter.disconnect()

    except ValueError as e:
        print(f"⚠️  環境變數未設定: {e}")
        print("  請複製 .env.example 為 .env 並填入有效 API Key")
    except Exception as e:
        print(f"錯誤: {e}")
