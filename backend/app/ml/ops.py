"""ML operations wiring: monitor + retrain cycle.

Thin entry points the runtime (scheduler / API) calls so the previously
orphaned monitor and retrain paths actually execute. They reuse core's own
:class:`ModelMonitor` and :class:`RetrainingOrchestrator`.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from .model_monitor import ModelMonitor
from .model_trainer import ModelTrainer
from .retraining import RetrainingOrchestrator


def run_monitor(prices: pd.DataFrame, monitor: Optional[ModelMonitor] = None) -> Dict[str, Any]:
    """Snapshot drift + health for the latest window."""
    monitor = monitor or ModelMonitor()
    return monitor.snapshot(prices)


def run_retrain(
    prices: pd.DataFrame,
    trainer: Optional[ModelTrainer] = None,
    monitor: Optional[ModelMonitor] = None,
    trigger: Optional[str] = None,
    min_samples: int = 200,
) -> Optional[Dict[str, Any]]:
    """Retrain only when a trigger (schedule or drift/accuracy alert) is active."""
    trainer = trainer or ModelTrainer()
    monitor = monitor or ModelMonitor()
    orch = RetrainingOrchestrator(trainer, monitor, min_samples=min_samples)
    return orch.maybe_retrain(prices, trigger=trigger)
