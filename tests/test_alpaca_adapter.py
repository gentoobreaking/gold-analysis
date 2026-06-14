"""
AlpacaExchange 整合測試

兩種模式：
  1. Mock 模式（默認）：使用 MockExchange，驗證介面合約，不需 API Key
  2. Live 模式（需設定）：真實呼叫 Alpaca API

執行方式：
  # Mock 模式（本地，不需要網路）
  pytest tests/test_alpaca_adapter.py -v

  # Live 模式（需要有效 API Key，測試真實交易流程）
  ALPACA_API_KEY=xxx ALPACA_SECRET_KEY=xxx pytest tests/test_alpaca_adapter.py -v -k live

  # 只跑快速 smoke test
  pytest tests/test_alpaca_adapter.py -v -k "smoke or init"
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# 確保專案根目錄在 Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.trading import (
    AlpacaExchange,
    MockExchange,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderType,
    TimeInForce,
    ExchangeMarketData,
    AccountBalance,
    Position,
    RiskRuleConfig,
)


# ═══════════════════════════════════════════════════════════════
# 測試配置
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def alpaca_valid_keys() -> bool:
    """檢查是否有有效的 Alpaca API Key"""
    key    = os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY")
    return bool(key and secret and key != "你的API_KEY")


@pytest.fixture
def risk_config() -> RiskRuleConfig:
    return RiskRuleConfig(
        max_position_value_pct=0.20,
        max_order_value=50000,
        max_daily_loss=1000,
    )


# ═══════════════════════════════════════════════════════════════
# 1. Mock 模式測試（不需要 API Key）
# ═══════════════════════════════════════════════════════════════

class TestMockExchange:
    """使用 MockExchange 驗證 ExchangeInterface 合約"""

    @pytest.fixture
    def exchange(self, risk_config) -> MockExchange:
        ex = MockExchange(risk_config=risk_config)
        ex.connect()
        yield ex
        ex.disconnect()

    def test_connection(self, exchange):
        assert exchange.is_connected
        assert exchange.is_authenticated()

    def test_get_account(self, exchange):
        account = exchange.get_account()
        assert isinstance(account, AccountBalance)
        assert account.total_equity > 0
        assert account.currency == "USD"

    def test_get_market_data(self, exchange):
        market = exchange.get_market_data("GOLD")
        assert isinstance(market, ExchangeMarketData)
        assert market.bid < market.ask
        assert market.last > 0

    def test_market_data_spread(self, exchange):
        market = exchange.get_market_data("GOLD")
        assert market.spread > 0
        assert market.mid_price == pytest.approx((market.bid + market.ask) / 2)

    def test_submit_market_order_filled(self, exchange):
        """市價單應立即成交"""
        request = OrderRequest(
            symbol="GOLD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.5,
        )
        resp = exchange.submit_order(request)
        assert resp.success, resp.error_message
        assert resp.order is not None
        assert resp.order.status.value == "filled"
        assert resp.order.filled_quantity == 0.5

    def test_submit_limit_order_pending(self, exchange):
        """限價單應進入掛單狀態"""
        market = exchange.get_market_data("GOLD")
        request = OrderRequest(
            symbol="GOLD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1.0,
            price=market.last - 10.0,   # 低於市價，無法成交
        )
        resp = exchange.submit_order(request)
        assert resp.success
        assert resp.order is not None
        assert resp.order.status.value == "submitted"

    def test_cancel_order(self, exchange):
        market = exchange.get_market_data("GOLD")
        request = OrderRequest(
            symbol="GOLD",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=1.0,
            price=market.last + 10.0,
        )
        resp = exchange.submit_order(request)
        assert resp.success
        order_id = resp.order.order_id

        cancelled = exchange.cancel_order(order_id)
        assert cancelled

        order = exchange.get_order(order_id)
        assert order.status.value == "cancelled"

    def test_get_open_orders(self, exchange):
        # 先掛一筆限價單
        market = exchange.get_market_data("GOLD")
        exchange.submit_order(OrderRequest(
            symbol="GOLD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1.0,
            price=market.last - 5.0,
        ))
        opens = exchange.get_open_orders()
        assert len(opens) >= 1

    def test_position_update(self, exchange):
        """成交後持倉應更新"""
        exchange.submit_order(OrderRequest(
            symbol="GOLD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=2.0,
        ))
        pos = exchange.get_position("GOLD")
        assert pos is not None
        assert pos.quantity == 2.0

    def test_historical_prices(self, exchange):
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=30)
        bars  = exchange.get_historical_prices("GOLD", start, end)
        assert len(bars) > 0
        assert all("close" in bar for bar in bars)


# ═══════════════════════════════════════════════════════════════
# 2. AlpacaExchange Mock 測試（Mock HTTP 回應）
# ═══════════════════════════════════════════════════════════════

class TestAlpacaExchangeMocked:
    """用 Mock 模擬 Alpaca API 回應，驗證轉換邏輯"""

    @pytest.fixture
    def exchange(self, risk_config) -> AlpacaExchange:
        ex = AlpacaExchange(
            api_key="PK_TEST_MOCK",
            api_secret="SEC_TEST_MOCK",
            is_demo=True,
            risk_config=risk_config,
        )
        ex.is_connected = True   # 跳過 connect（mock）
        yield ex
        ex.disconnect()

    @pytest.fixture
    def mock_market(self, exchange):
        """Mock 所有 get_market_data 調用，返回測試數據"""
        mock_mkt = ExchangeMarketData(
            symbol="GOLD", bid=1850.0, ask=1851.0, last=1850.5, volume=10000
        )
        with patch.object(exchange, "get_market_data", return_value=mock_mkt):
            yield mock_mkt

    # ── 符號映射 ─────────────────────────────────────────────────────────

    def test_to_alpaca_symbol_gold(self, exchange):
        from backend.app.trading.alpaca_adapter import to_alpaca_symbol, from_alpaca_symbol
        assert to_alpaca_symbol("GOLD") == "GLD"
        assert to_alpaca_symbol("XAUUSD") == "GLD"
        assert to_alpaca_symbol("AAPL") == "AAPL"   # 直接映射

    def test_from_alpaca_symbol(self, exchange):
        from backend.app.trading.alpaca_adapter import from_alpaca_symbol
        assert from_alpaca_symbol("GLD") == "GOLD"
        assert from_alpaca_symbol("SLV") == "SILVER"

    # ── 狀態轉換 ─────────────────────────────────────────────────────────

    def test_map_alpaca_order_status(self, exchange):
        from backend.app.trading.alpaca_adapter import _map_alpaca_order_status
        from backend.app.trading import OrderStatus
        assert _map_alpaca_order_status("new")            == OrderStatus.SUBMITTED
        assert _map_alpaca_order_status("filled")         == OrderStatus.FILLED
        assert _map_alpaca_order_status("cancelled")      == OrderStatus.CANCELLED
        assert _map_alpaca_order_status("partially_filled") == OrderStatus.PARTIAL
        assert _map_alpaca_order_status("rejected")       == OrderStatus.REJECTED

    def test_map_time_in_force(self, exchange):
        from backend.app.trading.alpaca_adapter import _map_time_in_force
        from backend.app.trading import TimeInForce
        assert _map_time_in_force("gtc") == TimeInForce.GTC
        assert _map_time_in_force("day") == TimeInForce.DAY
        assert _map_time_in_force("ioc") == TimeInForce.IOC

    # ── Mock HTTP 回應 ──────────────────────────────────────────────────────

    @pytest.fixture
    def mock_session(self, exchange):
        with patch.object(exchange, "_session") as mock_sess:
            yield mock_sess

    def test_get_account_success(self, exchange, mock_session):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "equity":        "105000.0",
            "cash":          "98000.0",
            "currency":      "USD",
            "margin_used":   "0.0",
            "last_day_turnover": "500.0",
        }
        mock_session.get.return_value = mock_resp

        account = exchange.get_account()
        assert account.total_equity == 105000.0
        assert account.cash == 98000.0

    def test_get_account_error(self, exchange, mock_session):
        from requests.exceptions import HTTPError
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"message": "unauthorized"}
        err = HTTPError(response=mock_resp)
        mock_session.get.side_effect = err

        with pytest.raises(HTTPError):
            exchange.get_account()

    def test_submit_order_success(self, exchange, mock_session, mock_market):
        """模擬成功提交訂單"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id":             "ORDER-123",
            "client_order_id": "CLIENT-001",
            "symbol":         "GLD",
            "side":           "buy",
            "type":           "market",
            "qty":            "1.0",
            "status":         "filled",
            "filled_qty":     "1.0",
            "filled_avg_price": "185.50",
            "time_in_force":  "gtc",
            "created_at":     "2024-01-01T12:00:00Z",
            "updated_at":     "2024-01-01T12:00:01Z",
        }
        mock_session.post.return_value = mock_resp

        request = OrderRequest(
            symbol="GOLD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1.0,
        )
        resp = exchange.submit_order(request)

        assert resp.success, resp.error_message
        assert resp.order is not None
        assert resp.order.order_id == "ORDER-123"
        assert resp.order.symbol == "GOLD"
        assert resp.order.status.value == "filled"

    def test_submit_order_risk_blocked(self, exchange, mock_session, mock_market):
        """風控阻斷時不應發送 HTTP 請求"""
        request = OrderRequest(
            symbol="GOLD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=99999.0,   # 超過風控限制
        )
        resp = exchange.submit_order(request)
        assert not resp.success
        assert resp.error_code == "RISK_BLOCKED"
        mock_session.post.assert_not_called()   # 沒有發送 API 請求

    def test_submit_order_invalid_quantity(self, exchange, mock_session):
        """無效數量應直接拒絕"""
        request = OrderRequest(
            symbol="GOLD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=-1.0,
        )
        resp = exchange.submit_order(request)
        assert not resp.success
        assert resp.error_code == "INVALID_QUANTITY"
        mock_session.post.assert_not_called()

    def test_cancel_order_success(self, exchange, mock_session):
        mock_session.delete.return_value = MagicMock()
        result = exchange.cancel_order("ORDER-123")
        assert result
        mock_session.delete.assert_called_once()

    def test_cancel_order_not_found(self, exchange, mock_session):
        from requests.exceptions import HTTPError
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        err = HTTPError(response=mock_resp)
        mock_session.delete.side_effect = err
        result = exchange.cancel_order("NONEXISTENT")
        assert not result

    def test_get_historical_prices(self, exchange, mock_session):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "bars": [
                {"t": "2024-01-01T00:00:00Z", "o": 100, "h": 105, "l": 99, "c": 103, "v": 1000},
                {"t": "2024-01-02T00:00:00Z", "o": 103, "h": 108, "l": 102, "c": 106, "v": 1200},
            ]
        }
        mock_session.get.return_value = mock_resp

        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        bars  = exchange.get_historical_prices("GOLD", start, end)

        assert len(bars) == 2
        assert bars[0]["close"] == 103
        assert bars[1]["close"] == 106
        # 驗證 API 參數
        call_args = mock_session.get.call_args
        params = call_args.kwargs.get("params", {})
        assert params["timeframe"] == "1Day"

    def test_get_positions(self, exchange, mock_session):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {
                "symbol":         "GLD",
                "qty":            "2.0",
                "avg_entry_price": "180.0",
                "current_price":  "185.0",
                "unrealized_pl":  "10.0",
            }
        ]
        mock_session.get.return_value = mock_resp

        positions = exchange.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "GOLD"
        assert positions[0].quantity == 2.0
        assert positions[0].avg_entry_price == 180.0

    def test_parse_alpaca_time(self, exchange):
        from backend.app.trading.alpaca_adapter import _parse_alpaca_time
        dt = _parse_alpaca_time("2024-06-15T10:30:00Z")
        assert dt.year == 2024
        assert dt.month == 6
        assert dt.day == 15

    def test_parse_alpaca_time_invalid(self, exchange):
        from backend.app.trading.alpaca_adapter import _parse_alpaca_time
        dt = _parse_alpaca_time("not-a-time")
        assert dt is not None   # 應回退到 utcnow


# ═══════════════════════════════════════════════════════════════
# 3. Live 模式測試（需要有效 API Key）
# ═══════════════════════════════════════════════════════════════

@pytest.mark.skipif(
    not os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_API_KEY") == "你的API_KEY",
    reason="需要有效的 ALPACA_API_KEY"
)
class TestAlpacaExchangeLive:
    """真實 Alpaca API 整合測試（使用 Paper Trading）"""

    @pytest.fixture
    def exchange(self, risk_config) -> AlpacaExchange:
        ex = AlpacaExchange.from_env(risk_config=risk_config)
        assert ex.connect(), "Alpaca 連接失敗，請確認 API Key 有效且為 Paper 帳號"
        yield ex
        ex.disconnect()

    def test_live_account(self, exchange):
        account = exchange.get_account()
        assert account.total_equity > 0
        assert account.currency == "USD"

    def test_live_market_data(self, exchange):
        """獲取 SPY 報價（Alpaca 最容易取得的標的）"""
        market = exchange.get_market_data("SPY")
        assert market.last > 0
        assert market.bid < market.ask

    def test_live_submit_and_cancel(self, exchange):
        """提交限價單後立即取消（測試完整流程）"""
        market = exchange.get_market_data("SPY")
        request = OrderRequest(
            symbol="SPY",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1.0,
            price=market.last - 5.0,   # 故意設低價，確保不會成交
            time_in_force=TimeInForce.DAY,
        )
        resp = exchange.submit_order(request)
        assert resp.success, f"下單失敗: {resp.error_message}"
        assert resp.order is not None

        order_id = resp.order.order_id
        # 等待一下再取消
        import time; time.sleep(0.5)
        cancelled = exchange.cancel_order(order_id)
        assert cancelled, f"取消失敗: {order_id}"

        # 驗證狀態
        order = exchange.get_order(order_id)
        assert order.status.value == "cancelled"

    def test_live_historical_prices(self, exchange):
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=10)
        bars  = exchange.get_historical_prices("SPY", start, end)
        assert len(bars) > 0
        assert all("close" in bar for bar in bars)


# ═══════════════════════════════════════════════════════════════
# 4. Smoke Tests（快速驗證，不需要網路）
# ═══════════════════════════════════════════════════════════════

class TestSmoke:
    """快速冒煙測試，驗證基本初始化和導入"""

    def test_import_alpaca_exchange(self):
        from backend.app.trading import AlpacaExchange
        assert AlpacaExchange is not None

    def test_alpaca_exchange_init(self):
        ex = AlpacaExchange(
            api_key="test_key",
            api_secret="test_secret",
            is_demo=True,
        )
        assert ex.exchange_name == "ALPACA"
        assert ex.is_demo is True
        assert ex.base_url == AlpacaExchange.BASE_URL_PAPER

    def test_alpaca_exchange_live_mode(self):
        ex = AlpacaExchange(
            api_key="test_key",
            api_secret="test_secret",
            is_demo=False,
        )
        assert ex.base_url == AlpacaExchange.BASE_URL_LIVE

    def test_mock_exchange_init(self):
        ex = MockExchange()
        assert ex.exchange_name == "MOCK"
        assert not ex.is_connected

    def test_order_request_creation(self):
        req = OrderRequest(
            symbol="GOLD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=1.5,
            price=1850.0,
            stop_price=1800.0,
            time_in_force=TimeInForce.GTC,
        )
        assert req.symbol == "GOLD"
        assert req.price == 1850.0
        assert req.stop_price == 1800.0

    def test_market_data_properties(self):
        mkt = ExchangeMarketData(
            symbol="GOLD", bid=1850.0, ask=1851.0, last=1850.5, volume=10000
        )
        assert mkt.spread == 1.0
        assert mkt.mid_price == pytest.approx(1850.5)

    def test_account_balance_properties(self):
        acc = AccountBalance(total_equity=100000, cash=90000, currency="USD")
        assert acc.buying_power == 90000
        assert acc.margin_available == 100000

    def test_position_pnl(self):
        from backend.app.trading import PositionSide
        pos = Position(
            symbol="GOLD",
            side=PositionSide.LONG,
            quantity=2.0,
            avg_entry_price=1800.0,
            current_price=1850.0,
        )
        assert pos.unrealized_pnl == pytest.approx(100.0)   # (1850-1800)*2
        assert pos.unrealized_pnl_pct == pytest.approx(100.0 / 3600 * 100)

    def test_from_env_raises_on_missing_keys(self):
        with pytest.raises(ValueError, match="缺少 Alpaca API 憑證"):
            # 清除環境變數，確保觸發錯誤
            with patch.dict(os.environ, {
                "ALPACA_API_KEY":    "",
                "ALPACA_SECRET_KEY": "",
            }, clear=False):
                # 重新載入會讀到空值
                AlpacaExchange.from_env()


# ═══════════════════════════════════════════════════════════════
# 5. 介面合約測試（確保 Mock 和 Alpaca 行為一致）
# ═══════════════════════════════════════════════════════════════

class TestInterfaceContract:
    """驗證 MockExchange 和 AlpacaExchange 滿足相同的介面合約"""

    @pytest.fixture(params=["mock", "alpaca_mocked"])
    def exchange(self, request, risk_config):
        if request.param == "mock":
            ex = MockExchange(risk_config=risk_config)
            ex.connect()
            yield ex
            ex.disconnect()
        else:
            ex = AlpacaExchange(
                api_key="PK_TEST",
                api_secret="SEC_TEST",
                is_demo=True,
                risk_config=risk_config,
            )
            ex.is_connected = True
            # Mock 所有 HTTP 依賴
            mock_mkt = ExchangeMarketData(
                symbol="GOLD", bid=1850.0, ask=1851.0, last=1850.5, volume=10000
            )
            mock_acc = AccountBalance(total_equity=100000, cash=90000, currency="USD")
            with patch.object(ex, "get_market_data", return_value=mock_mkt), \
                 patch.object(ex, "get_account", return_value=mock_acc):
                ex.connect()
                yield ex
                ex.disconnect()

    def test_exchange_has_required_methods(self, exchange):
        """驗證所有必需方法都存在"""
        required = [
            "connect", "disconnect", "is_authenticated",
            "get_account", "get_positions", "get_position",
            "get_market_data", "get_historical_prices",
            "submit_order", "cancel_order", "get_order", "get_open_orders",
        ]
        for method in required:
            assert hasattr(exchange, method), f"缺少方法: {method}"
            assert callable(getattr(exchange, method)), f"不是可調用: {method}"

    def test_submit_order_returns_order_response(self, exchange):
        req = OrderRequest(
            symbol="GOLD",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=0.5,
        )
        resp = exchange.submit_order(req)
        assert isinstance(resp, OrderResponse)
        assert resp.success
        assert resp.order is not None
        assert resp.order.symbol == "GOLD"

    def test_market_data_has_required_fields(self, exchange):
        mkt = exchange.get_market_data("GOLD")
        assert hasattr(mkt, "symbol")
        assert hasattr(mkt, "bid")
        assert hasattr(mkt, "ask")
        assert hasattr(mkt, "last")
        assert hasattr(mkt, "spread")
        assert hasattr(mkt, "mid_price")
        assert mkt.bid < mkt.ask

    def test_account_has_required_fields(self, exchange):
        acc = exchange.get_account()
        assert hasattr(acc, "total_equity")
        assert hasattr(acc, "cash")
        assert hasattr(acc, "currency")
        assert hasattr(acc, "buying_power")
        assert hasattr(acc, "to_dict")
        assert callable(acc.to_dict)

    def test_invalid_symbol_raises(self, exchange):
        with pytest.raises(Exception):   # 具體類型視實作而定
            exchange.get_market_data("INVALID_SYMBOL_XYZ_123")
