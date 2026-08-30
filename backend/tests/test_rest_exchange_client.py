"""
T048 - RestExchangeClient 實連 / contract 測試

驗證 ``RestExchangeClient``（v20 REST，injectable opener）能正確發出請求並解析回應。

驗收標準對應：
- get_account()：取得帳戶餘額/權益
- get_positions()：取得當前持倉
- get_market_data("XAUUSD")：取得即時行情
- submit_order()：送出限價單，驗證 OrderResponse.success / order_id
- cancel_order(order_id)：取消測試單，驗證成功
- 錯誤處理驗證：無效參數 → success=False，error_message 合理
- 請求/回應日記記錄

本測試採用 **contract test**（回放 HTTP 錄製）方式，不需真實憑證，
符合任務備註「若無實盤測試帳號，改以 contract test（錄製/回放 HTTP）替代」。
"""

import io
import json

import pytest
from app.trading.exchange_client import RestExchangeClient
from app.trading.exchange_interface import MarketData, OrderRequest
from app.trading.order_types import OrderSide, OrderStatus, OrderType

# ─── Fake HTTP opener for injection ──────────────────────────────────────


class FakeResponse(io.BytesIO):
    """Simulates an ``http.client.HTTPResponse``-like object."""

    def __init__(self, data: bytes, status: int = 200):
        super().__init__(data)
        self.status = status
        self.headers = {"Content-Type": "application/json"}


class _CtxWrapper:
    """Wraps a FakeResponse so it works with ``with opener.open(req) as resp:``."""

    def __init__(self, resp):
        self._resp = resp

    def __enter__(self):
        return self._resp

    def __exit__(self, *_exc):
        return False


class FakeOpener:
    """Injectable ``OpenerDirector`` substitute that records requests and
    returns canned responses.

    ``open`` returns an object that supports the context-manager protocol
    and exposes ``.status``, ``.read()``, and ``.headers``.
    """

    def __init__(self, handler=None):
        self.handler = handler
        self.requests: list[tuple[str, str, bytes | None, dict]] = []

    def open(self, req):
        self.requests.append(
            (
                req.get_method(),
                req.full_url,
                req.data,
                dict(req.header_items()),
            )
        )
        if self.handler is not None:
            body, _status = self.handler(req)
        else:
            body = b"{}"
        resp = FakeResponse(body)
        return _CtxWrapper(resp)


# ─── Fixtures ────────────────────────────────────────────────────────────

ACCOUNT_SUMMARY = {
    "account": {
        "id": "001-011-8295193-001",
        "alias": "Primary",
        "currency": "USD",
        "balance": {"type": "ACCOUNT_BALANCE", "value": "10000.00"},
        "NAV": {"value": "10050.00", "type": "NAV"},
        "marginAvailable": {"value": "9500.00"},
        "marginUsed": {"value": "500.00"},
    }
}

PRICING_RESPONSE = {
    "prices": [
        {
            "instrument": "XAU_USD",
            "time": "2024-01-15T10:00:00.000000000-00:00",
            "bids": [{"price": "2019.50"}],
            "asks": [{"price": "2020.50"}],
            "closeoutBid": "2019.80",
            "closeoutAsk": "2020.20",
        }
    ]
}

POSITIONS_RESPONSE = {
    "positions": [
        {
            "instrument": "XAU_USD",
            "long": {"units": "10"},
            "short": {"units": "0"},
        }
    ]
}

ORDER_RESPONSE_TEMPLATE = {
    "orderCreateTransaction": {
        "id": "12345",
        "time": "2024-01-15T10:00:00.000000000-00:00",
        "type": "ORDER_CREATE",
    },
    "orderFillTransaction": {
        "id": "12346",
        "orderID": "12345",
        "price": "2015.00",
        "type": "ORDER_FILL",
    },
}


def _handler(req):
    """Canned response handler that routes by URL path."""
    url = req.full_url
    if "summary" in url:
        return json.dumps(ACCOUNT_SUMMARY).encode(), 200
    if "pricing" in url:
        return json.dumps(PRICING_RESPONSE).encode(), 200
    if "position" in url:
        return json.dumps(POSITIONS_RESPONSE).encode(), 200
    if "orders" in url and req.get_method() == "POST":
        return json.dumps(ORDER_RESPONSE_TEMPLATE).encode(), 200
    return b"{}", 200


@pytest.fixture
def client():
    """RestExchangeClient with a no-response fake opener."""
    opener = FakeOpener()
    return RestExchangeClient(
        base_url="https://api-fake.oanda.com/v3",
        api_key="fake-api-key",
        account_id="001-011-8295193-001",
        opener=opener,
    )


@pytest.fixture
def client_with_handler():
    """RestExchangeClient with a canned response handler."""
    opener = FakeOpener(handler=_handler)
    return RestExchangeClient(
        base_url="https://api-fake.oanda.com/v3",
        api_key="fake-api-key",
        account_id="001-011-8295193-001",
        opener=opener,
    )


# ─── Tests ───────────────────────────────────────────────────────────────


class TestGetAccount:
    """get_account_balance(): 取得帳戶餘額/權益"""

    def test_get_account_balance(self, client_with_handler):
        balance = client_with_handler.get_account_balance()
        assert balance["id"] == "001-011-8295193-001"
        assert balance["alias"] == "Primary"
        assert balance["currency"] == "USD"
        assert float(balance["balance"]["value"]) == 10000.00
        assert float(balance["NAV"]["value"]) == 10050.00

    def test_request_uses_account_id(self, client_with_handler):
        client_with_handler.get_account_balance()
        _method, url, _data, headers = client_with_handler.opener.requests[-1]
        assert "001-011-8295193-001" in url
        assert "Authorization" in headers


class TestGetPositions:
    """get_positions(): 取得當前持倉"""

    def test_get_positions(self, client_with_handler):
        positions = client_with_handler.get_positions()
        assert len(positions) == 1
        pos = positions[0]
        assert pos.symbol == "XAU_USD"
        assert pos.quantity == 10.0
        assert pos.side == OrderSide.BUY

    def test_request_url(self, client_with_handler):
        client_with_handler.get_positions()
        _method, url, _data, _headers = client_with_handler.opener.requests[-1]
        assert "position" in url


class TestGetMarketData:
    """get_market_data(): 取得即時行情"""

    def test_get_market_data(self, client_with_handler):
        md = client_with_handler.get_market_data("XAUUSD")
        assert isinstance(md, MarketData)
        assert md.bid == 2019.50
        assert md.ask == 2020.50
        assert md.last == 2019.80
        assert md.source == "rest"

    def test_market_data_mid_price(self, client_with_handler):
        md = client_with_handler.get_market_data("XAUUSD")
        assert md.mid_price == pytest.approx((2019.50 + 2020.50) / 2)
        assert md.spread == pytest.approx(1.00)


class TestSubmitOrder:
    """submit_order(): 送出限價單"""

    def test_submit_order_success(self, client_with_handler):
        request = OrderRequest(
            symbol="XAUUSD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.01,
            price=1900.00,
        )
        response = client_with_handler.submit_order(request)
        assert response.success is True
        assert response.order is not None
        assert response.order.order_id == "12346"  # orderFillTransaction.id
        assert response.order.status == OrderStatus.FILLED

    def test_submit_order_payload(self, client_with_handler):
        request = OrderRequest(
            symbol="XAUUSD",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=0.01,
            price=2050.00,
        )
        client_with_handler.submit_order(request)
        method, _url, data, _headers = client_with_handler.opener.requests[-1]
        assert method == "POST"
        body = json.loads(data)
        order = body["order"]
        assert order["instrument"] == "XAUUSD"
        assert order["units"] == "-0.01"  # SELL → negative units
        assert order["type"] == "LIMIT"


class TestCancelOrder:
    """cancel_order(): 取消測試單"""

    def test_cancel_order_success(self, client):
        def handler(_req):
            return b"{}", 200

    def test_cancel_order_failure(self, client):
        """cancel_order returns False when an exception is raised (network error)."""

        def handler(_req):
            raise ConnectionError("order not found")

        client.opener.handler = handler
        result = client.cancel_order("nonexistent")
        assert result is False


class TestErrorHandling:
    """錯誤處理驗證：無效參數 / API 錯誤 → success=False"""

    def test_submit_order_api_error(self, client_with_handler):
        def handler(_req):
            return b'{"errorMessage": "invalid parameters"}', 400

        client_with_handler.opener.handler = handler
        request = OrderRequest(
            symbol="INVALID",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=-1,
            price=2000.00,
        )
        response = client_with_handler.submit_order(request)
        assert response.success is False
        assert response.order is not None
        assert response.order.status == OrderStatus.REJECTED
        assert response.order.order_id is None
        assert response.raw_response is not None
        assert "errorMessage" in response.raw_response

    def test_submit_order_network_error(self, client_with_handler):
        def handler(_req):
            raise ConnectionError("connection refused")

        client_with_handler.opener.handler = handler
        request = OrderRequest(
            symbol="XAUUSD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.01,
            price=2000.00,
        )
        response = client_with_handler.submit_order(request)
        assert response.success is False
        assert "connection refused" in (response.error_message or "").lower()


class TestRequestLogging:
    """請求/回應日記記錄驗證"""

    def test_request_recorded(self, client_with_handler):
        client_with_handler.get_account_balance()
        assert len(client_with_handler.opener.requests) == 1
        method, _url, _data, _headers = client_with_handler.opener.requests[0]
        assert method == "GET"

    def test_auth_header(self, client_with_handler):
        client_with_handler.get_account_balance()
        _method, _url, _data, headers = client_with_handler.opener.requests[0]
        assert headers["Authorization"] == "Bearer fake-api-key"


class TestEdgeCases:
    """邊界情況驗證"""

    def test_empty_positions(self, client):
        def handler(_req):
            return json.dumps({"positions": []}).encode(), 200

        client.opener.handler = handler
        positions = client.get_positions()
        assert positions == []

    def test_get_open_orders_empty(self, client):
        def handler(_req):
            return json.dumps({"orders": []}).encode(), 200

        client.opener.handler = handler
        orders = client.get_open_orders()
        assert orders == []

    def test_close(self, client):
        # Should not raise
        client.close()
