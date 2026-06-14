"""
Model Integration - ML 模型與決策系統整合
提供模型的 API 包裝、決策系統調用以及持續優化入口。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .feature_engineering import FeatureEngineer
from .model_trainer import ModelTrainer, ModelRegistry, TrainingResult, TrainingConfig
from .model_evaluator import ModelEvaluator

logger = logging.getLogger(__name__)


class ModelAPI:
    """簡易的模型服務 API（HTTP/JSON）"""

    def __init__(self, model_dir: Optional[str] = None):
        self.trainer = ModelTrainer(model_dir=model_dir)
        self.evaluator = ModelEvaluator()
        self.feature_engineer: Optional[FeatureEngineer] = None
        self.current_model: Optional[Any] = None
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
    def predict(self, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
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
            "timestamp": datetime.utcnow().isoformat(),
            "predictions": preds.tolist(),
            "probabilities": probs.tolist(),
        }

    # ─── 重新訓練入口（持續優化）──────────────────────────────────
    def retrain(self, data: List[Dict[str, Any]], label_key: str = "label") -> TrainingResult:
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
        logger.info("模型重新訓練完成，版本 {}".format(result.version))
        return result

    # ─── 評估入口 ───────────────────────────────────────────────
    def evaluate(self, test_data: List[Dict[str, Any]], label_key: str = "label") -> Dict[str, Any]:
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
