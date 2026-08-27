"""Automated retraining orchestration (core API aligned).

Ties the monitor to the trainer: when the monitor flags data drift or an
accuracy drop -- or a scheduled trigger fires -- retrain on the latest data and
register the new model version. ``maybe_retrain`` is a no-op (returns ``None``)
when no trigger is active, so it is safe to call on every cycle.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from .feature_engineering import FeatureEngineer
from .model_monitor import ModelMonitor
from .model_trainer import ModelTrainer, TrainingConfig


class RetrainingOrchestrator:
    """Decide when to retrain and execute it."""

    def __init__(
        self,
        trainer: ModelTrainer,
        monitor: ModelMonitor,
        min_samples: int = 200,
        model_type: str = "random_forest",
    ):
        self.trainer = trainer
        self.monitor = monitor
        self.min_samples = min_samples
        self.model_type = model_type

    @staticmethod
    def _alert_triggers(alerts: List[str]) -> bool:
        return any(a.startswith("data_drift") or a.startswith("accuracy_drop") for a in alerts)

    def needs_retrain(self, trigger: Optional[str] = None, alerts: Optional[List[str]] = None) -> bool:
        if trigger == "schedule":
            return True
        if alerts is None and self.monitor is not None:
            alerts = self.monitor.snapshot().get("alerts", [])
        return self._alert_triggers(alerts or [])

    def maybe_retrain(self, prices: pd.DataFrame, trigger: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.needs_retrain(trigger=trigger):
            return None
        fe = FeatureEngineer()
        data = fe.fit_transform(prices)
        if len(data) < self.min_samples:
            return {"retrained": False, "reason": f"only {len(data)} samples < min_samples={self.min_samples}"}
        X = data.drop(columns=["date", "label"], errors="ignore")
        y = data["label"]
        report = self.trainer.train(X, y, config=TrainingConfig(model_type=self.model_type))
        return {
            "retrained": True,
            "version": getattr(report, "version", None),
            "metrics": getattr(report, "metrics", None),
        }
