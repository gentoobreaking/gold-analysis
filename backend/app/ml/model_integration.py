"""
Model Integration - ML 模型與決策系統整合
提供模型的 API 包裝、決策系統調用以及持續優化入口。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .feature_engineering import FeatureEngineer
from .model_evaluator import ModelEvaluator
from .model_trainer import ModelTrainer, TrainingConfig, TrainingResult

logger = logging.getLogger(__name__)


class ModelAPI:
    """簡易的模型服務 API（HTTP/JSON）"""

    def __init__(self, model_dir: str | None = None):
        self.trainer = ModelTrainer(model_dir=model_dir)
        self.evaluator = ModelEvaluator()
        self.feature_engineer: FeatureEngineer | None = None
        self.current_model: Any | None = None
        self.model_name: str = "random_forest"

    # ─── 模型加載與初始化 ──────────────────────────────────────
    def load_latest(self) -> None:
        """載入最新模型並初始化特徵工程"""
        result = self.trainer.load_latest(self.model_name)
        self.current_model = self.trainer.current_model
        # 假設模型訓練時使用的特徵名稱已被保存
        if result and result.feature_importance:
            self.feature_engineer = FeatureEngineer()
        logger.info(f"模型 {self.model_name} {result.version} 已載入")

    # ─── 預測入口 ───────────────────────────────────────────────
    def predict(self, raw_data: list[dict[str, Any]]) -> dict[str, Any]:
        """接受原始市場/經濟數據，返回模型預測結果"""
        if not self.current_model:
            self.load_latest()
        if not self.feature_engineer:
            self.feature_engineer = FeatureEngineer()
        
        # 1. 轉為 DataFrame
        import pandas as pd
        df = pd.DataFrame(raw_data)
        
        # 2. 特徵工程（使用已訓練的特徵）
        features = self.feature_engineer.transform(df)
        
        # 3. 預測
        preds = self.trainer.predict(features)
        probs = self.trainer.predict_proba(features)
        
        # 4. 包裝返回
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "predictions": preds.tolist(),
            "probabilities": probs.tolist(),
        }

    # ─── 重新訓練入口（持續優化）──────────────────────────────────
    def retrain(self, data: list[dict[str, Any]], label_key: str = "label") -> TrainingResult:
        """接收新數據進行模型再訓練（增量或全量）"""
        import pandas as pd
        df = pd.DataFrame(data)
        y = df[label_key]
        X = df.drop(columns=[label_key])
        
        # 特徵工程（重新擬合）
        self.feature_engineer = FeatureEngineer()
        X_feat = self.feature_engineer.fit_transform(X)
        
        # 訓練配置（使用與第一次相同的模型類型）
        config = TrainingConfig(model_type=self.model_name)
        result = self.trainer.train(X_feat, y, config=config)
        logger.info(f"模型重新訓練完成，版本 {result.version}")
        return result

    # ─── 評估入口 ───────────────────────────────────────────────
    def evaluate(self, test_data: list[dict[str, Any]], label_key: str = "label") -> dict[str, Any]:
        """使用測試集評估模型並返回完整報告"""
        import pandas as pd
        df = pd.DataFrame(test_data)
        y_true = df[label_key]
        X = df.drop(columns=[label_key])
        
        if not self.feature_engineer:
            self.feature_engineer = FeatureEngineer()
        X_feat = self.feature_engineer.transform(X)
        y_pred = self.trainer.predict(X_feat)
        y_proba = self.trainer.predict_proba(X_feat)
        
        report = self.evaluator.evaluate_classification(
            y_true=y_true.values,
            y_pred=y_pred,
            y_proba=y_proba,
            model_name=self.model_name,
            version=self.trainer.current_version or "unknown",
        )
        return {
            "report": report.print_report(),
            "metrics": report.metrics,
        }
from dataclasses import dataclass, field

import pandas as pd

ACTION_NAMES = {-1: "SELL", 0: "HOLD", 1: "BUY"}


@dataclass
class Decision:
    """A structured trading decision produced by the integration layer."""

    action: str
    signal: int
    probability: float
    confidence: float
    suggested_position_pct: float
    model_version: str | None
    model_type: str | None
    as_of: str | None = None
    top_features: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "signal": self.signal,
            "probability": self.probability,
            "confidence": self.confidence,
            "suggested_position_pct": self.suggested_position_pct,
            "model_version": self.model_version,
            "model_type": self.model_type,
            "as_of": self.as_of,
            "top_features": self.top_features,
            "notes": self.notes,
        }


class DecisionEngine:
    """Integrate the latest ML model into an actionable decision (core API)."""

    def __init__(self, trainer: ModelTrainer | None = None, max_position_pct: float = 100.0):
        self.trainer = trainer
        self.max_position_pct = max_position_pct

    def decide(self, prices: pd.DataFrame, trainer: ModelTrainer | None = None) -> Decision:
        trainer = trainer or self.trainer
        if trainer is None:
            return self._fallback("no trainer configured")
        try:
            model = trainer.load_latest()
        except Exception as exc:  # noqa: BLE001
            return self._fallback(f"model load failed: {exc}")
        try:
            fe = FeatureEngineer()
            data = fe.fit_transform(prices)
            feat_names = [c for c in fe.get_feature_names() if c in data.columns]
            if not feat_names or data.empty:
                return self._fallback("no features produced")
            X = data[feat_names].tail(1)
            pred = trainer.predict(X)
            signal = int(pred[0])
            proba = trainer.predict_proba(X)[0] if hasattr(trainer, "predict_proba") else None
            confidence = float(max(proba)) if proba is not None else 0.5
            action = ACTION_NAMES.get(signal, "HOLD")
            result = trainer.get_result()
            version = getattr(result, "version", None) if result else None
            mtype = getattr(result, "model_type", None) if result else None
            return Decision(
                action=action,
                signal=signal,
                probability=float(confidence),
                confidence=float(confidence),
                suggested_position_pct=round(confidence * self.max_position_pct, 2),
                model_version=version,
                model_type=mtype,
                as_of=pd.Timestamp.now().isoformat(),
                top_features=self._explain(model, feat_names),
                notes="",
            )
        except Exception as exc:  # noqa: BLE001
            return self._fallback(f"decision error: {exc}")

    @staticmethod
    def _explain(model: Any, feat_names: list[str], top_n: int = 5) -> list[dict[str, Any]]:
        importances = getattr(model, "feature_importances_", None)
        if importances is None or not feat_names:
            return []
        pairs = sorted(zip(feat_names, importances), key=lambda kv: kv[1], reverse=True)[:top_n]
        return [{"feature": f, "importance": float(i)} for f, i in pairs]

    def _fallback(self, reason: str) -> Decision:
        return Decision(
            action="HOLD",
            signal=0,
            probability=0.0,
            confidence=0.0,
            suggested_position_pct=0.0,
            model_version=None,
            model_type=None,
            notes=reason,
        )
