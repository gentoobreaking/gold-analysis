"""Integration tests for the advanced capabilities merged into core (approach 2).

These exercise the previously-orphaned monitor / retrain / trade-execution paths
against core's real ML + trading stack, with no external network (RestExchangeClient
uses an injectable opener).
"""
from __future__ import annotations

import json
import pandas as pd
import numpy as np

from app.ml.feature_engineering import FeatureEngineer
from app.ml.model_trainer import ModelTrainer, TrainingConfig
from app.ml.model_integration import DecisionEngine, Decision, ACTION_NAMES
from app.ml.model_monitor import ModelMonitor
from app.ml.retraining import RetrainingOrchestrator
from app.ml.ops import run_monitor, run_retrain

from app.trading.exchange_client import RestExchangeClient, ExchangeClient
from app.trading.exchange_interface import OrderRequest, OrderResponse
from app.trading.order_types import OrderSide, OrderType, OrderStatus
from app.trading.trade_logger import TradeLogger
from app.trading.execution import execute_decision


def _prices(n: int = 150, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 1900 + np.cumsum(rng.normal(0, 4, n))
    return pd.DataFrame(
        {
            "date": idx,
            "open": close + rng.normal(0, 1, n),
            "high": close + 5 + rng.normal(0, 1, n),
            "low": close - 5 + rng.normal(0, 1, n),
            "close": close,
            "volume": rng.integers(1000, 5000, n).astype(float),
        }
    )


def _train(tmp_path):
    trainer = ModelTrainer(model_dir=str(tmp_path))
    fe = FeatureEngineer()
    data = fe.fit_transform(_prices())
    X = data.drop(columns=["date", "label"])
    y = data["label"]
    trainer.train(X, y, config=TrainingConfig(model_type="random_forest"))
    return trainer


def test_decision_engine(tmp_path):
    trainer = _train(tmp_path)
    eng = DecisionEngine(trainer=trainer)
    dec = eng.decide(_prices(80))
    assert isinstance(dec, Decision)
    assert dec.action in {"BUY", "SELL", "HOLD"}
    assert 0.0 <= dec.confidence <= 1.0
    assert dec.to_dict()["action"] == dec.action
    # fallback without a model
    fallback = DecisionEngine(trainer=ModelTrainer(model_dir=str(tmp_path / "empty"))).decide(_prices(80))
    assert fallback.action == "HOLD"


def test_model_monitor_and_retrain(tmp_path):
    trainer = _train(tmp_path)
    monitor = ModelMonitor()
    monitor.fit_reference(_prices())
    orch = RetrainingOrchestrator(trainer, monitor, min_samples=10)
    # schedule trigger forces a retrain
    rep = orch.maybe_retrain(_prices(), trigger="schedule")
    assert rep["retrained"] is True
    # alert-driven triggers
    assert orch.needs_retrain(alerts=["data_drift:rsi"]) is True
    assert orch.needs_retrain(alerts=["accuracy_drop"]) is True
    assert orch.needs_retrain(alerts=["something_else"]) is False
    assert orch.needs_retrain(alerts=[]) is False


def test_rest_exchange_client_mock():
    class FakeResp:
        def __init__(self, d):
            self._d = d

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(self._d).encode()

    class FakeOpener:
        def __init__(self, payload):
            self.payload = payload
            self.reqs = []

        def open(self, req):
            self.reqs.append(req)
            return FakeResp(self.payload)

    op = FakeOpener({"orderCreateTransaction": {"id": "100"}})
    client = RestExchangeClient("https://api.example.com", "KEY", account_id="acc", opener=op)
    resp = client.submit_order(
        OrderRequest(symbol="XAUUSD", side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=1.0)
    )
    assert isinstance(resp, OrderResponse)
    assert resp.success is True
    assert op.reqs  # the REST path was actually hit (mocked)
    md = client.get_market_data("XAUUSD")
    assert md.symbol == "XAUUSD"
    assert client.cancel_order("100") is True


def test_trade_logger(tmp_path):
    tl = TradeLogger(path=str(tmp_path / "trades.jsonl"))
    tl.log({"a": 1})
    tl.log({"b": 2})
    rows = tl.read()
    assert len(rows) == 2
    assert rows[0]["a"] == 1


def test_execution_e2e(tmp_path):
    buy = Decision(
        action="BUY",
        signal=1,
        probability=0.9,
        confidence=0.9,
        suggested_position_pct=90.0,
        model_version="v1",
        model_type="rf",
    )
    tl = TradeLogger(path=str(tmp_path / "exec.jsonl"))
    out = execute_decision(buy, client=ExchangeClient(use_mock=True), logger=tl, quantity=0.5)
    assert out["executed"] is True
    assert tl.read()[0]["action"] == "BUY"

    tl2 = TradeLogger(path=str(tmp_path / "exec2.jsonl"))
    hold = Decision(
        action="HOLD",
        signal=0,
        probability=0.0,
        confidence=0.0,
        suggested_position_pct=0.0,
        model_version=None,
        model_type=None,
    )
    out2 = execute_decision(hold, logger=tl2)
    assert out2["executed"] is False
    assert tl2.read() == []


def test_ops_cycle(tmp_path):
    trainer = _train(tmp_path)
    snap = run_monitor(_prices(), monitor=ModelMonitor())
    assert "alerts" in snap
    rep = run_retrain(
        _prices(), trainer=trainer, monitor=ModelMonitor(), trigger="schedule", min_samples=10
    )
    assert rep["retrained"] is True
