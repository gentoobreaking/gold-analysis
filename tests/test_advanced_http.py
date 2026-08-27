"""HTTP-level e2e for the merged ops triggers (approach 2).

Mounts only the ops router on a fresh FastAPI app so it runs without core's
``Settings`` (which fails to validate in this environment). Proves the runtime
trigger -> observable side-effect path works over HTTP.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.advanced_ops import ml_router, trade_router

app = FastAPI()
app.include_router(ml_router)
app.include_router(trade_router)
client = TestClient(app)


def _prices(n: int = 80, seed: int = 2) -> list:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 1900 + np.cumsum(rng.normal(0, 4, n))
    return [
        {
            "date": str(d),
            "open": float(close[i] + 1),
            "high": float(close[i] + 5),
            "low": float(close[i] - 5),
            "close": float(close[i]),
            "volume": float(rng.integers(1000, 5000)),
        }
        for i, d in enumerate(idx)
    ]


def test_monitor_endpoint():
    r = client.post("/api/ml/monitor", json={"prices": _prices()})
    assert r.status_code == 200
    assert "alerts" in r.json()


def test_retrain_endpoint_no_trigger():
    r = client.post("/api/ml/retrain", json={"prices": _prices()})
    assert r.status_code == 200
    body = r.json()
    assert body.get("retrained") is False


def test_execute_endpoint_writes_log(tmp_path):
    log = str(tmp_path / "http.jsonl")
    r = client.post(
        "/api/trading/execute",
        json={
            "action": "BUY",
            "signal": 1,
            "probability": 0.9,
            "confidence": 0.9,
            "suggested_position_pct": 90.0,
            "model_version": "v1",
            "model_type": "rf",
            "symbol": "XAUUSD",
            "quantity": 0.5,
            "log_path": log,
        },
    )
    assert r.status_code == 200
    assert r.json()["executed"] is True
    from app.trading.trade_logger import TradeLogger

    rows = TradeLogger(path=log).read()
    assert rows and rows[0]["action"] == "BUY"
