"""Runtime triggers for the advanced ML/trading ops merged into core (approach 2).

Exposes the previously-orphaned monitor / retrain / trade-execution paths as HTTP
endpoints so a scheduler or the dashboard can drive them. The heavy lifting is done
by :mod:`app.ml.ops` and :mod:`app.trading.execution`.

Kept in the ``app.routers`` namespace package (no ``__init__``) so importing it does
not pull in the API routes package that constructs ``Settings`` at import time.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from app.ml.ops import run_monitor, run_retrain
from app.trading.execution import execute_decision
from app.trading.trade_logger import TradeLogger
from app.ml.model_integration import Decision

ml_router = APIRouter(prefix="/api/ml", tags=["ml-ops"])
trade_router = APIRouter(prefix="/api/trading", tags=["trading-ops"])


class PricesIn(BaseModel):
    prices: List[Dict[str, Any]]


class RetrainIn(PricesIn):
    trigger: Optional[str] = None
    min_samples: int = 200


class DecisionIn(BaseModel):
    action: str
    signal: int = 0
    probability: float = 0.0
    confidence: float = 0.0
    suggested_position_pct: float = 0.0
    model_version: Optional[str] = None
    model_type: Optional[str] = None
    symbol: str = "XAUUSD"
    quantity: float = 1.0
    log_path: Optional[str] = None


def _to_df(prices: List[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(prices)


@ml_router.post("/monitor")
def monitor(payload: PricesIn) -> Dict[str, Any]:
    """Snapshot drift + health for the latest window."""
    return run_monitor(_to_df(payload.prices))


@ml_router.post("/retrain")
def retrain(payload: RetrainIn) -> Dict[str, Any]:
    """Retrain only when a trigger (schedule or drift/accuracy alert) is active."""
    result = run_retrain(_to_df(payload.prices), trigger=payload.trigger, min_samples=payload.min_samples)
    return result or {"retrained": False, "reason": "no active trigger"}


@trade_router.post("/execute")
def execute(payload: DecisionIn) -> Dict[str, Any]:
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
