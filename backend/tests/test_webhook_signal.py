"""
T067 - Webhook signal ingest tests

驗證：
- HMAC 簽章驗證：合法簽章通過，錯誤簽章拒絕
- payload 各種形狀的解析
- T055 交易開關控管：關閉/dry-run 時僅模擬，不下單
- source=external 正確對應
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.routes.webhooks import (
    _compute_signature,
    _map_to_decision,
    _verify_signature,
)


def _make_secret() -> str:
    return "test-webhook-secret-12345"


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestHmacSignature:
    """HMAC signature computation and verification."""

    def test_compute_signature_matches_manual(self):
        secret = _make_secret()
        body = json.dumps({"action": "buy", "symbol": "GOLD"}).encode()
        sig = _compute_signature(body, secret)
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert sig == expected

    def test_verify_signature_valid(self):
        secret = _make_secret()
        body = json.dumps({"action": "buy"}).encode()
        sig = _sign(body, secret)
        assert _verify_signature(body, sig, secret) is True

    def test_verify_signature_invalid(self):
        secret = _make_secret()
        body = json.dumps({"action": "buy"}).encode()
        wrong_sig = _sign(b"wrong body", secret)
        assert _verify_signature(body, wrong_sig, secret) is False

    def test_verify_signature_wrong_secret(self):
        body = json.dumps({"action": "buy"}).encode()
        sig = _sign(body, "wrong-secret")
        assert _verify_signature(body, sig, _make_secret()) is False


class TestMapToDecision:
    """External signal to internal Decision mapping."""

    def test_map_buy(self):
        from app.api.schemas.webhooks import WebhookSignal

        signal = WebhookSignal(
            symbol="XAUUSD",
            action="buy",
            price=2050.5,
            confidence=0.85,
            signal="RSI oversold",
            reason=["RSI < 30", "Bounce from support"],
        )
        decision = _map_to_decision(signal)
        assert decision["decision_type"] == "buy"
        assert decision["source"] == "external"
        assert decision["asset"] == "XAUUSD"
        assert decision["confidence"] == 0.85
        assert decision["reason_en"] == "RSI < 30; Bounce from support"

    def test_map_sell(self):
        from app.api.schemas.webhooks import WebhookSignal

        signal = WebhookSignal(
            symbol="GOLD",
            action="sell",
            price=2040.0,
            confidence=0.9,
            signal="RSI overbought",
            reason=["RSI > 70"],
        )
        decision = _map_to_decision(signal)
        assert decision["decision_type"] == "sell"
        assert decision["source"] == "external"

    def test_map_hold(self):
        from app.api.schemas.webhooks import WebhookSignal

        signal = WebhookSignal(
            symbol="GOLD",
            action="hold",
            confidence=0.5,
            signal="Neutral",
        )
        decision = _map_to_decision(signal)
        assert decision["decision_type"] == "hold"
        assert decision["source"] == "external"

    def test_map_watch(self):
        from app.api.schemas.webhooks import WebhookSignal

        signal = WebhookSignal(
            symbol="GOLD",
            action="watch",
            confidence=0.6,
            signal="Monitor",
        )
        decision = _map_to_decision(signal)
        assert decision["decision_type"] == "watch"

    def test_map_includes_timestamp(self):
        from app.api.schemas.webhooks import WebhookSignal

        signal = WebhookSignal(
            symbol="GOLD",
            action="buy",
            confidence=0.7,
            signal="Test",
            timestamp="2026-08-28T03:34:16+00:00",
        )
        decision = _map_to_decision(signal)
        assert decision["timestamp"] == "2026-08-28T03:34:16+00:00"

    def test_map_default_timestamp_when_none(self):
        from app.api.schemas.webhooks import WebhookSignal

        signal = WebhookSignal(
            symbol="GOLD",
            action="buy",
            confidence=0.7,
            signal="Test",
        )
        decision = _map_to_decision(signal)
        # Should have generated a timestamp
        assert decision["timestamp"] is not None
        # Should be parseable
        dt = datetime.fromisoformat(decision["timestamp"])
        assert dt.year == 2026


class TestWebhookEndpoint:
    """Webhook endpoint integration tests using FastAPI TestClient."""

    def _get_app(self):
        from app.api.routes.webhooks import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return app

    def _client(self):
        from fastapi.testclient import TestClient

        return TestClient(self._get_app())

    def test_valid_signature_accepted(self):
        """Legal HMAC signature → 200, signal accepted."""
        secret = _make_secret()
        payload = {
            "symbol": "GOLD",
            "action": "buy",
            "price": 2050.5,
            "confidence": 0.85,
            "signal": "RSI oversold bounce",
            "reason": ["RSI < 30", "Support bounce"],
        }
        body = json.dumps(payload).encode()
        sig = _sign(body, secret)

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=False,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": f"sha256={sig}",
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["accepted"] is True
        assert data["source"] == "external"
        assert data["action_taken"] == "simulated"

    def test_valid_signature_raw_header(self):
        """Raw X-Webhook-Signature header (without sha256= prefix) also works."""
        secret = _make_secret()
        payload = {
            "symbol": "GOLD",
            "action": "sell",
            "price": 2040.0,
            "confidence": 0.75,
            "signal": "RSI overbought",
        }
        body = json.dumps(payload).encode()
        sig = _sign(body, secret)

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=False,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": sig,
                },
            )

        assert resp.status_code == 200
        assert resp.json()["accepted"] is True

    def test_invalid_signature_rejected(self):
        """Wrong signature → 401."""
        secret = _make_secret()
        payload = {
            "symbol": "GOLD",
            "action": "buy",
            "confidence": 0.8,
            "signal": "Test",
        }
        body = json.dumps(payload).encode()
        bad_sig = _sign(b"completely wrong body", secret)

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=False,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": f"sha256={bad_sig}",
                },
            )

        assert resp.status_code == 401
        assert "Invalid signature" in resp.json()["detail"]

    def test_missing_signature_rejected(self):
        """HMAC secret configured but no signature header → 401."""
        secret = _make_secret()
        payload = {"symbol": "GOLD", "action": "buy", "confidence": 0.8, "signal": "Test"}
        body = json.dumps(payload).encode()

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=False,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={"Content-Type": "application/json"},
            )

        assert resp.status_code == 401
        assert "Missing signature header" in resp.json()["detail"]

    def test_no_secret_dev_mode_accepted(self):
        """No webhook_secret configured → dev mode, accepts without HMAC."""
        payload = {"symbol": "GOLD", "action": "buy", "confidence": 0.8, "signal": "Test"}
        body = json.dumps(payload).encode()

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=None,
                trading_enabled=False,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={"Content-Type": "application/json"},
            )

        assert resp.status_code == 200
        assert resp.json()["accepted"] is True

    def test_kill_switch_off_simulated(self):
        """T055 trading_enabled=False → action_taken=simulated."""
        secret = _make_secret()
        payload = {"symbol": "GOLD", "action": "buy", "confidence": 0.8, "signal": "Test"}
        body = json.dumps(payload).encode()
        sig = _sign(body, secret)

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=False,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={sig}"},
            )

        data = resp.json()
        assert data["action_taken"] == "simulated"

    def test_dry_run_simulated(self):
        """trading_enabled=True but dry_run=True → action_taken=simulated."""
        secret = _make_secret()
        payload = {"symbol": "GOLD", "action": "sell", "confidence": 0.8, "signal": "Test"}
        body = json.dumps(payload).encode()
        sig = _sign(body, secret)

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=True,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={sig}"},
            )

        data = resp.json()
        assert data["action_taken"] == "simulated"

    def test_live_mode_accepted(self):
        """trading_enabled=True + dry_run=False → action_taken=accepted."""
        secret = _make_secret()
        payload = {"symbol": "GOLD", "action": "buy", "confidence": 0.8, "signal": "Test"}
        body = json.dumps(payload).encode()
        sig = _sign(body, secret)

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=True,
                trading_dry_run=False,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={sig}"},
            )

        data = resp.json()
        assert data["action_taken"] == "accepted"

    def test_payload_buy_shape(self):
        """Full buy payload with all fields."""
        secret = _make_secret()
        payload = {
            "symbol": "XAUUSD",
            "action": "buy",
            "price": 2050.5,
            "confidence": 0.95,
            "signal": "Golden cross",
            "reason": ["MA5 > MA20", "RSI rising"],
            "timestamp": "2026-08-28T10:00:00Z",
        }
        body = json.dumps(payload).encode()
        sig = _sign(body, secret)

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings, \
             patch("app.api.routes.webhooks._store_external_decision", new_callable=AsyncMock) as mock_store:
            mock_store.return_value = 42
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=False,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={sig}"},
            )

        data = resp.json()
        assert resp.status_code == 200
        assert data["accepted"] is True
        assert data["decision_id"] == 42
        assert data["source"] == "external"
        mock_store.assert_awaited_once()

    def test_payload_sell_shape(self):
        """Sell payload with price and stop_loss."""
        secret = _make_secret()
        payload = {
            "symbol": "GOLD",
            "action": "sell",
            "price": 2030.0,
            "confidence": 0.88,
            "signal": "Resistance hit",
            "reason": ["Price at resistance"],
        }
        body = json.dumps(payload).encode()
        sig = _sign(body, secret)

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=False,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={sig}"},
            )

        assert resp.status_code == 200
        assert resp.json()["accepted"] is True

    def test_payload_hold_shape(self):
        """Hold payload minimal fields."""
        secret = _make_secret()
        payload = {
            "symbol": "GOLD",
            "action": "hold",
            "confidence": 0.5,
            "signal": "Waiting for confirmation",
        }
        body = json.dumps(payload).encode()
        sig = _sign(body, secret)

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=False,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={sig}"},
            )

        assert resp.status_code == 200
        assert resp.json()["accepted"] is True

    def test_payload_missing_signal_422(self):
        """Missing required field 'signal' → 422 validation error."""
        secret = _make_secret()
        payload = {
            "symbol": "GOLD",
            "action": "buy",
            "confidence": 0.8,
        }
        body = json.dumps(payload).encode()
        sig = _sign(body, secret)

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=False,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={sig}"},
            )

        assert resp.status_code == 422

    def test_payload_invalid_action_422(self):
        """Invalid action value → 422."""
        secret = _make_secret()
        payload = {
            "symbol": "GOLD",
            "action": "invalid_action",
            "confidence": 0.8,
            "signal": "Test",
        }
        body = json.dumps(payload).encode()
        sig = _sign(body, secret)

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=False,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={sig}"},
            )

        assert resp.status_code == 422

    def test_payload_confidence_out_of_range_422(self):
        """Confidence > 1.0 → 422."""
        secret = _make_secret()
        payload = {
            "symbol": "GOLD",
            "action": "buy",
            "confidence": 1.5,
            "signal": "Test",
        }
        body = json.dumps(payload).encode()
        sig = _sign(body, secret)

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=False,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={sig}"},
            )

        assert resp.status_code == 422

    def test_source_is_external(self):
        """Verify source=external is set in response."""
        secret = _make_secret()
        payload = {
            "symbol": "GOLD",
            "action": "buy",
            "confidence": 0.8,
            "signal": "Test signal",
            "reason": ["reason1"],
        }
        body = json.dumps(payload).encode()
        sig = _sign(body, secret)

        with patch("app.api.routes.webhooks.get_core_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                webhook_secret=secret,
                trading_enabled=False,
                trading_dry_run=True,
            )
            client = self._client()
            resp = client.post(
                "/api/webhooks/signal",
                content=body,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={sig}"},
            )

        data = resp.json()
        assert data["source"] == "external"
