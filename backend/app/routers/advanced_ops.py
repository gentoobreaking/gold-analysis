"""Runtime triggers for the advanced ML/trading ops merged into core (approach 2).

Exposes the previously-orphaned monitor / retrain / trade-execution paths as HTTP
endpoints so a scheduler or the dashboard can drive them. The heavy lifting is done
by :mod:`app.ml.ops` and :mod:`app.trading.execution`.

Kept in the ``app.routers`` namespace package (no ``__init__``) so importing it does
not pull in the API routes package that constructs ``Settings`` at import time.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from app.ml.ab_testing import ABTestEngine
from app.ml.model_integration import Decision
from app.ml.ops import run_monitor, run_retrain
from app.trading.execution import execute_decision
from app.trading.trade_logger import TradeLogger
from fastapi import APIRouter
from pydantic import BaseModel

ml_router = APIRouter(prefix="/api/ml", tags=["ml-ops"])
trade_router = APIRouter(prefix="/api/trading", tags=["trading-ops"])


class PricesIn(BaseModel):
    prices: list[dict[str, Any]]


class RetrainIn(PricesIn):
    trigger: str | None = None
    min_samples: int = 200


class DecisionIn(BaseModel):
    action: str
    signal: int = 0
    probability: float = 0.0
    confidence: float = 0.0
    suggested_position_pct: float = 0.0
    model_version: str | None = None
    model_type: str | None = None
    symbol: str = "XAUUSD"
    quantity: float = 1.0
    log_path: str | None = None


# ABTestEngine 實例（單例模式）
ab_test_engine = ABTestEngine()

# 建立一個預設實驗（使用固定 ID）
if "default" not in ab_test_engine.experiments:
    from app.ml.ab_testing import ExperimentConfig

    default_config = ExperimentConfig(
        name="default_ml_model",
        variants=["model_a", "model_b"],
        traffic_split=[0.5, 0.5],
    )
    # 使用固定 ID "default"
    ab_test_engine.experiments["default"] = default_config


def _to_df(prices: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(prices)


class ABAssignIn(BaseModel):
    user_id: str
    symbol: str = "XAUUSD"
    experiment_id: str | None = "default"


@ml_router.post("/ab/assign")
def ab_assign(payload: ABAssignIn) -> dict[str, Any]:
    """Assign a variant for A/B test based on deterministic split."""
    exp_id = payload.experiment_id or "default"
    config = ab_test_engine.experiments.get(exp_id)
    if not config:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Experiment {exp_id} not found")

    # 確定性分流：基於 user_id hash
    import hashlib

    hash_val = int(hashlib.md5(f"{exp_id}:{payload.user_id}".encode()).hexdigest(), 16)
    rnd = hash_val / (2**128)
    cumulative = 0.0
    for variant, weight in zip(config.variants, config.traffic_split, strict=False):
        cumulative += weight
        if rnd <= cumulative:
            assigned = variant
            break
    else:
        assigned = config.variants[-1]

    return {
        "experiment_id": exp_id,
        "variant": assigned,
        "user_id": payload.user_id,
        "symbol": payload.symbol,
    }


@ml_router.post("/monitor")
def monitor(payload: PricesIn) -> dict[str, Any]:
    """Snapshot drift + health for the latest window."""
    return run_monitor(_to_df(payload.prices))


@ml_router.post("/retrain")
def retrain(payload: RetrainIn) -> dict[str, Any]:
    """Retrain only when a trigger (schedule or drift/accuracy alert) is active."""
    result = run_retrain(
        _to_df(payload.prices), trigger=payload.trigger, min_samples=payload.min_samples
    )
    return result or {"retrained": False, "reason": "no active trigger"}


@trade_router.post("/execute")
def execute(payload: DecisionIn) -> dict[str, Any]:
    """Execute a structured Decision via core's OrderExecutor; log the outcome."""
    dec = Decision(
        action=payload.action,
        signal=payload.signal,
        probability=payload.probability,
        confidence=payload.confidence,
        suggested_position_pct=payload.suggested_position_pct,
        model_version=payload.model_version,
        model_type=payload.model_type,
    )
    logger = TradeLogger(path=payload.log_path) if payload.log_path else TradeLogger()
    return execute_decision(dec, symbol=payload.symbol, logger=logger, quantity=payload.quantity)
