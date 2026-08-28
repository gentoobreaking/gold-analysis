"""
T055 - 交易 kill-switch 與 pre-trade 風險閘門測試

驗證：
- trading_enabled=False 時，絕不下真實單（不呼叫 executor.execute / client.submit_order）
- trading_dry_run=True 時，僅模擬/記錄，不下單
- pre-trade 斷路器（DailyLossLimitRule）觸發 BLOCK 時中止下單
- 同時啟用（enabled + dry_run=False）時才真正下單
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.config import CoreSettings
from app.trading import execution as ex


class _Decision:
    def __init__(self, action, model_version=None):
        self.action = action
        self.model_version = model_version


def _set_settings(monkeypatch, **overrides):
    cfg = CoreSettings(**overrides)
    monkeypatch.setattr(ex, "get_core_settings", lambda: cfg)
    return cfg


def _make_client():
    client = MagicMock()
    client.submit_order = MagicMock(
        return_value=SimpleNamespace(
            success=True, error_message=None, order=SimpleNamespace(order_id="mock-1")
        )
    )
    return client


def test_disabled_refuses_order(monkeypatch):
    _set_settings(monkeypatch, trading_enabled=False)
    executor_spy = MagicMock()
    monkeypatch.setattr(ex, "OrderExecutor", executor_spy)

    result = ex.execute_decision(_Decision("BUY"), client=_make_client())

    assert result["executed"] is False
    assert result["reason"] == "trading_disabled"
    executor_spy.assert_not_called()


def test_dry_run_simulates_only(monkeypatch):
    _set_settings(monkeypatch, trading_enabled=True, trading_dry_run=True)
    executor_spy = MagicMock()
    monkeypatch.setattr(ex, "OrderExecutor", executor_spy)

    result = ex.execute_decision(_Decision("BUY"), client=_make_client())

    assert result["executed"] is False
    assert result["reason"] == "dry_run"
    assert result.get("simulated") is True
    executor_spy.assert_not_called()


def test_daily_loss_breaker_blocks(monkeypatch):
    _set_settings(monkeypatch, trading_enabled=True, trading_dry_run=False)
    # 帳戶今日大額虧損 → DailyLossLimitRule BLOCK
    account = SimpleNamespace(
        total_equity=100000.0, buying_power=100000.0, realized_pnl_today=-5000.0
    )

    result = ex.execute_decision(_Decision("BUY"), client=_make_client(), account=account)

    assert result["executed"] is False
    assert result["reason"] == "risk_blocked"
    assert any("daily_loss" in b.get("name", "") for b in result["blocked_rules"])


def test_live_submits_when_enabled(monkeypatch):
    _set_settings(monkeypatch, trading_enabled=True, trading_dry_run=False)
    client = _make_client()
    account = SimpleNamespace(
        total_equity=100000.0, buying_power=100000.0, realized_pnl_today=0.0
    )

    result = ex.execute_decision(_Decision("BUY"), client=client, account=account)

    assert result["executed"] is True
    client.submit_order.assert_called_once()
