"""
Model Monitor - 監控已部署模型的運行狀態與數據漂移
提供模型健康檢查、特徵分佈漂移檢測、性能指標持續追蹤。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from .feature_engineering import FeatureEngineer
from .model_evaluator import ModelEvaluator
from .model_trainer import ModelRegistry

logger = logging.getLogger(__name__)


class DriftDetector:
    """簡易的特徵分佈漂移檢測（基於 KS 測試）"""

    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold
        self.reference_stats: dict[str, Any] = {}

    def fit_reference(self, data: pd.DataFrame) -> None:
        """使用歷史基線數據建立參考分佈"""
        for col in data.columns:
            self.reference_stats[col] = {
                "mean": data[col].mean(),
                "std": data[col].std(ddof=0),
            }
        logger.info("漂移檢測參考統計已建立")

    def check(self, data: pd.DataFrame) -> dict[str, bool]:
        """檢查當前數據是否發生漂移，返回 {feature: bool}"""
        drifted: dict[str, bool] = {}
        for col, ref in self.reference_stats.items():
            if col not in data.columns:
                continue
            cur_mean = data[col].mean()
            cur_std = data[col].std(ddof=0)
            # 相對變化率
            mean_diff = abs(cur_mean - ref["mean"]) / (abs(ref["mean"]) + 1e-9)
            std_diff = abs(cur_std - ref["std"]) / (abs(ref["std"]) + 1e-9)
            drifted[col] = mean_diff > self.threshold or std_diff > self.threshold
        return drifted


class ModelHealthChecker:
    """模型健康檢查與指標報告"""

    def __init__(self, model_dir: str | None = None):
        self.registry = ModelRegistry(model_dir)
        self.evaluator = ModelEvaluator()
        self.drift_detector = DriftDetector()
        self.logger = logging.getLogger(__name__)
        self.last_checked: datetime | None = None
        self.check_interval = timedelta(minutes=10)

    def _load_latest_model(self) -> tuple[Any, dict[str, Any]]:
        latest = self.registry.get_latest()
        if not latest:
            raise RuntimeError("未找到已註冊的模型")
        return self.registry.load_model(latest["version"], latest["model_name"]), latest

    def health_check(self, recent_data: pd.DataFrame, label_key: str = "label") -> dict[str, Any]:
        """對最近的數據執行完整健康檢查"""
        now = datetime.now(timezone.utc)
        if self.last_checked and now - self.last_checked < self.check_interval:
            self.logger.debug("檢查間隔過短，跳過本輪健康檢查")
            return {"skipped": True}
        self.last_checked = now

        # 1. 載入模型
        model, latest = self._load_latest_model()

        # 2. 特徵工程（使用相同的 FE 設定）
        fe = FeatureEngineer()
        X = fe.fit_transform(recent_data.drop(columns=[label_key]))
        y = recent_data[label_key]

        # 3. 產生預測 & 評估指標
        y_pred = model.predict(X)
        try:
            y_proba = model.predict_proba(X)
        except Exception:
            y_proba = None

        report = self.evaluator.evaluate_classification(
            y_true=y.values,
            y_pred=y_pred,
            y_proba=y_proba,
            model_name=latest["model_name"],
            version=latest["version"],
        )

        # 4. 漂移檢測
        if not self.drift_detector.reference_stats:
            self.drift_detector.fit_reference(X)
            drift = dict.fromkeys(X.columns, False)
        else:
            drift = self.drift_detector.check(X)

        # 5. 整合報告
        health = {
            "timestamp": now.isoformat(),
            "model_version": latest["version"],
            "metrics": report.metrics,
            "drift": drift,
        }
        self.logger.info("模型健康檢查完成")
        return health


class ModelMonitor:
    """High-level model monitor: drift + health snapshot.

    Wraps :class:`DriftDetector` and :class:`ModelHealthChecker` and exposes a
    single ``snapshot`` the retraining orchestrator consumes.
    """

    def __init__(
        self, drift_threshold: float = 0.05, health_checker: ModelHealthChecker | None = None
    ):
        self.drift = DriftDetector(threshold=drift_threshold)
        self.health = health_checker or ModelHealthChecker()
        self._reference_fit = False

    def fit_reference(self, prices: pd.DataFrame) -> None:
        fe = FeatureEngineer()
        data = fe.fit_transform(prices)
        feats = data.drop(columns=["date", "label"], errors="ignore")
        self.drift.fit_reference(feats)
        self._reference_fit = True

    def snapshot(self, prices: pd.DataFrame | None = None) -> dict[str, Any]:
        alerts: list[str] = []
        out: dict[str, Any] = {"alerts": alerts, "drift": {}, "health": {}}
        if prices is None:
            return out
        fe = FeatureEngineer()
        data = fe.fit_transform(prices)
        feats = data.drop(columns=["date", "label"], errors="ignore")
        if self._reference_fit:
            drifted = self.drift.check(feats)
            out["drift"] = {k: bool(v) for k, v in drifted.items()}
            for feat, is_drifted in drifted.items():
                if is_drifted:
                    alerts.append(f"data_drift:{feat}")
        try:
            out["health"] = self.health.health_check(data, label_key="label")
        except Exception as exc:
            out["health"] = {"error": str(exc)}
        return out
