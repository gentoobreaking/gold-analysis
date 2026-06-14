"""
Model Monitor - 監控已部署模型的運行狀態與數據漂移
提供模型健康檢查、特徵分佈漂移檢測、性能指標持續追蹤。
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .model_trainer import ModelRegistry
from .feature_engineering import FeatureEngineer
from .model_evaluator import ModelEvaluator

logger = logging.getLogger(__name__)


class DriftDetector:
    """簡易的特徵分佈漂移檢測（基於 KS 測試）"""

    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold
        self.reference_stats: Dict[str, Any] = {}

    def fit_reference(self, data: pd.DataFrame) -> None:
        """使用歷史基線數據建立參考分佈"""
        for col in data.columns:
            self.reference_stats[col] = {
                "mean": data[col].mean(),
                "std": data[col].std(ddof=0),
            }
        logger.info("漂移檢測參考統計已建立")

    def check(self, data: pd.DataFrame) -> Dict[str, bool]:
        """檢查當前數據是否發生漂移，返回 {feature: bool}"""
        drifted: Dict[str, bool] = {}
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

    def __init__(self, model_dir: Optional[str] = None):
        self.registry = ModelRegistry(model_dir)
        self.evaluator = ModelEvaluator()
        self.drift_detector = DriftDetector()
        self.logger = logging.getLogger(__name__)
        self.last_checked: Optional[datetime] = None
        self.check_interval = timedelta(minutes=10)

    def _load_latest_model(self) -> Any:
        latest = self.registry.get_latest()
        if not latest:
            raise RuntimeError("未找到已註冊的模型")
        return self.registry.load_model(latest["version"], latest["model_name"])

    def health_check(self, recent_data: pd.DataFrame, label_key: str = "label") -> Dict[str, Any]:
        """對最近的數據執行完整健康檢查"""
        now = datetime.utcnow()
        if self.last_checked and now - self.last_checked < self.check_interval:
            self.logger.debug("檢查間隔過短，跳過本輪健康檢查")
            return {"skipped": True}
        self.last_checked = now
        
        # 1. 載入模型
        model = self._load_latest_model()
        
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
            drift = {k: False for k in X.columns}
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
