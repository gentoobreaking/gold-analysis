"""ML operations wiring: monitor + retrain cycle.

Thin entry points the runtime (scheduler / API) calls so the previously
orphaned monitor and retrain paths actually execute. They reuse core's own
:class:`ModelMonitor` and :class:`RetrainingOrchestrator`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .model_monitor import ModelMonitor
from .model_trainer import ModelTrainer
from .retraining import RetrainingOrchestrator


def run_monitor(prices: pd.DataFrame, monitor: ModelMonitor | None = None) -> dict[str, Any]:
    """Snapshot drift + health for the latest window."""
    monitor = monitor or ModelMonitor()
    snapshot = monitor.snapshot(prices)
    # T056: 監控異常時推送通知（若已配置 notify_enabled）
    try:
        alerts = snapshot.get("alerts") or []
        health = snapshot.get("health") or {}
        unhealthy = health.get("status") in ("unhealthy", "degraded")
        if alerts or unhealthy:
            from app.services.notify import notify_alert

            notify_alert(
                {
                    "title": "[MODEL MONITOR] 監控異常",
                    "body": f"alerts={alerts}, health_status={health.get('status')}",
                    "level": "warning",
                    "source": "model_monitor",
                }
            )
    except Exception:
        pass
    return snapshot


def run_retrain(
    prices: pd.DataFrame,
    trainer: ModelTrainer | None = None,
    monitor: ModelMonitor | None = None,
    trigger: str | None = None,
    min_samples: int = 200,
) -> dict[str, Any] | None:
    """Retrain only when a trigger (schedule or drift/accuracy alert) is active."""
    trainer = trainer or ModelTrainer()
    monitor = monitor or ModelMonitor()
    orch = RetrainingOrchestrator(trainer, monitor, min_samples=min_samples)
    return orch.maybe_retrain(prices, trigger=trigger)
