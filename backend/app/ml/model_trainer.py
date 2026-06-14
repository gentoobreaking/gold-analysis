"""
Model Trainer Module - 模型訓練與管理
負責模型訓練、驗證、持久化與版本管理。
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

import numpy as np
import pandas as pd
from dataclasses import dataclass, field, asdict

from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


# ─── 資料類別 ────────────────────────────────────────────────────────────────

@dataclass
class TrainingConfig:
    """訓練配置"""
    model_type: str = "random_forest"          # random_forest | gradient_boosting | logistic
    test_size: float = 0.2
    random_state: int = 42
    cv_folds: int = 5
    model_params: Dict[str, Any] = field(default_factory=dict)
    scaler_enabled: bool = True


@dataclass
class TrainingResult:
    """訓練結果"""
    model_name: str
    version: str
    trained_at: str
    train_accuracy: float
    val_accuracy: float
    cv_mean: float
    cv_std: float
    feature_importance: Dict[str, float]
    config: Dict[str, Any]
    metrics: Dict[str, float] = field(default_factory=dict)
    path: Optional[str] = None


class ModelRegistry:
    """
    模型註冊表 - 管理所有已訓練模型的版本與元數據
    
    目錄結構:
        models/
        ├── registry.json           # 模型元數據索引
        ├── v1_random_forest.pkl    # 模型文件
        ├── v2_gradient_boosting.pkl
        └── ...
    """
    
    REGISTRY_FILE = "registry.json"
    DEFAULT_MODEL_DIR = "models"
    
    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = Path(model_dir or self.DEFAULT_MODEL_DIR)
        self.registry_path = self.model_dir / self.REGISTRY_FILE
        self._registry: Dict[str, Any] = {}
        self._load_registry()
    
    def _load_registry(self) -> None:
        """從磁盤加載註冊表"""
        if self.registry_path.exists():
            with open(self.registry_path, "r", encoding="utf-8") as f:
                self._registry = json.load(f)
            logger.info(f"已加載模型註冊表，包含 {len(self._registry)} 個模型")
        else:
            self._registry = {"models": {}}
    
    def _save_registry(self) -> None:
        """保存註冊表到磁盤"""
        self.model_dir.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(self._registry, f, indent=2, ensure_ascii=False)
    
    def register(self, result: TrainingResult) -> str:
        """
        註冊新訓練的模型
        
        Args:
            result: 訓練結果
            
        Returns:
            模型版本號
        """
        model_key = f"{result.model_name}_{result.version}"
        
        self._registry["models"][model_key] = {
            "version": result.version,
            "model_name": result.model_name,
            "trained_at": result.trained_at,
            "train_accuracy": result.train_accuracy,
            "val_accuracy": result.val_accuracy,
            "cv_mean": result.cv_mean,
            "cv_std": result.cv_std,
            "config": result.config,
            "metrics": result.metrics,
            "path": result.path,
            "feature_importance": result.feature_importance,
        }
        self._registry["latest"] = model_key
        self._save_registry()
        
        logger.info(f"模型 {model_key} 已註冊")
        return model_key
    
    def get_latest(self, model_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """獲取最新註冊的模型信息"""
        if model_name:
            candidates = [k for k in self._registry["models"] if k.startswith(model_name)]
            if not candidates:
                return None
            key = sorted(candidates)[-1]
        else:
            key = self._registry.get("latest")
            if not key:
                return None
        
        return self._registry["models"].get(key)
    
    def list_models(self) -> List[Dict[str, Any]]:
        """列出所有註冊的模型"""
        return list(self._registry["models"].values())
    
    def load_model(self, version: str, model_name: str) -> BaseEstimator:
        """
        加載指定的模型文件
        
        Args:
            version: 模型版本（如 "v1"）
            model_name: 模型名稱
            
        Returns:
            sklearn 模型對象
        """
        key = f"{model_name}_{version}"
        model_info = self._registry["models"].get(key)
        
        if not model_info or not model_info.get("path"):
            raise FileNotFoundError(f"模型 {key} 不存在於註冊表中")
        
        model_path = self.model_dir / model_info["path"]
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        
        logger.info(f"已加載模型: {key}")
        return model


class ModelTrainer:
    """
    模型訓練器 - 統一封裝 scikit-learn 模型的訓練流程
    
    支持:
    - 多種模型類型（Random Forest, Gradient Boosting, Logistic Regression）
    - 時間序列交叉驗證（避免未來數據洩漏）
    - 標準化特徵
    - 自動化超參數搜索
    - 模型持久化與版本管理
    """
    
    # 支援的模型類型
    SUPPORTED_MODELS = {
        "random_forest": RandomForestClassifier,
        "gradient_boosting": GradientBoostingClassifier,
        "logistic": LogisticRegression,
    }
    
    def __init__(
        self,
        model_dir: Optional[str] = None,
        registry: Optional[ModelRegistry] = None,
    ):
        self.model_dir = Path(model_dir or ModelRegistry.DEFAULT_MODEL_DIR)
        self.registry = registry or ModelRegistry(str(self.model_dir))
        self.scaler: Optional[StandardScaler] = None
        self.current_model: Optional[BaseEstimator] = None
        self.current_version: Optional[str] = None
        self.current_result: Optional[TrainingResult] = None
        self.feature_names: List[str] = []
    
    # ─── 公開 API ─────────────────────────────────────────────────────────────
    
    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        config: Optional[TrainingConfig] = None,
        feature_names: Optional[List[str]] = None,
    ) -> TrainingResult:
        """
        訓練模型
        
        Args:
            X: 特徵矩陣（DataFrame）
            y: 標籤向量
            config: 訓練配置
            feature_names: 特徵名稱列表（用於特徵重要性映射）
            
        Returns:
            TrainingResult 訓練結果
        """
        config = config or TrainingConfig()
        self.feature_names = list(X.columns)
        
        # 1. 數據分割（時間序列分割）
        split_idx = int(len(X) * (1 - config.test_size))
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]
        
        # 2. 標準化
        if config.scaler_enabled:
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_val_scaled = self.scaler.transform(X_val)
        else:
            X_train_scaled = X_train.values
            X_val_scaled = X_val.values
            self.scaler = None
        
        # 3. 模型選擇與訓練
        model_cls = self.SUPPORTED_MODELS.get(config.model_type)
        if not model_cls:
            raise ValueError(f"不支援的模型類型: {config.model_type}")
        
        default_params = self._get_default_params(config.model_type)
        model_params = {**default_params, **config.model_params}
        
        model: BaseEstimator = model_cls(**model_params)
        model.fit(X_train_scaled, y_train)
        self.current_model = model
        
        # 4. 評估
        train_acc = model.score(X_train_scaled, y_train)
        val_acc = model.score(X_val_scaled, y_val)
        
        # 時間序列交叉驗證
        cv_scores = cross_val_score(
            model,
            X_train_scaled,
            y_train,
            cv=TimeSeriesSplit(n_splits=config.cv_folds),
            scoring="accuracy",
        )
        cv_mean = float(cv_scores.mean())
        cv_std = float(cv_scores.std())
        
        # 5. 特徵重要性
        feature_importance = self._get_feature_importance(model, feature_names)
        
        # 6. 版本管理
        version = self._generate_version()
        self.current_version = version
        
        # 7. 保存模型
        model_path = self._save_model(model, config.model_type, version)
        
        # 8. 構建結果
        self.current_result = TrainingResult(
            model_name=config.model_type,
            version=version,
            trained_at=datetime.utcnow().isoformat(),
            train_accuracy=float(train_acc),
            val_accuracy=float(val_acc),
            cv_mean=cv_mean,
            cv_std=cv_std,
            feature_importance=feature_importance,
            config=asdict(config),
            metrics={
                "precision": self._compute_metric(model, X_val_scaled, y_val, "precision"),
                "recall": self._compute_metric(model, X_val_scaled, y_val, "recall"),
                "f1": self._compute_metric(model, X_val_scaled, y_val, "f1"),
            },
            path=str(model_path.relative_to(self.model_dir)),
        )
        
        # 9. 註冊到 registry
        self.registry.register(self.current_result)
        
        logger.info(
            f"訓練完成: {config.model_type} {version} | "
            f"Train Acc={train_acc:.4f} | Val Acc={val_acc:.4f} | "
            f"CV={cv_mean:.4f}±{cv_std:.4f}"
        )
        
        return self.current_result
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        使用當前模型預測
        
        Args:
            X: 特徵矩陣
            
        Returns:
            預測類別
        """
        if self.current_model is None:
            raise RuntimeError("模型未訓練，請先調用 train()")
        
        if self.scaler:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X.values
        
        return self.current_model.predict(X_scaled)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        預測概率
        
        Args:
            X: 特徵矩陣
            
        Returns:
            預測概率矩陣 [N, n_classes]
        """
        if self.current_model is None:
            raise RuntimeError("模型未訓練，請先調用 train()")
        
        if self.scaler:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X.values
        
        if hasattr(self.current_model, "predict_proba"):
            return self.current_model.predict_proba(X_scaled)
        
        raise AttributeError(f"模型 {type(self.current_model)} 不支持概率預測")
    
    def load_latest(self, model_name: Optional[str] = None) -> BaseEstimator:
        """加載最新註冊的模型"""
        model_info = self.registry.get_latest(model_name)
        if not model_info:
            raise FileNotFoundError("沒有找到已註冊的模型")
        
        self.current_model = self.registry.load_model(
            model_info["version"],
            model_info["model_name"],
        )
        self.current_version = model_info["version"]
        self.current_result = TrainingResult(
            model_name=model_info["model_name"],
            version=model_info["version"],
            trained_at=model_info["trained_at"],
            train_accuracy=model_info["train_accuracy"],
            val_accuracy=model_info["val_accuracy"],
            cv_mean=model_info["cv_mean"],
            cv_std=model_info["cv_std"],
            feature_importance=model_info["feature_importance"],
            config=model_info["config"],
            metrics=model_info["metrics"],
            path=model_info["path"],
        )
        
        # 加載 scaler（若存在）
        scaler_path = self.model_dir / f"{model_info['model_name']}_{model_info['version']}_scaler.pkl"
        if scaler_path.exists():
            with open(scaler_path, "rb") as f:
                self.scaler = pickle.load(f)
        
        return self.current_model
    
    def get_result(self) -> Optional[TrainingResult]:
        """獲取當前訓練結果"""
        return self.current_result
    
    # ─── 私有輔助方法 ─────────────────────────────────────────────────────────
    
    def _get_default_params(self, model_type: str) -> Dict[str, Any]:
        """返回各模型類型的默認超參數"""
        defaults = {
            "random_forest": {
                "n_estimators": 100,
                "max_depth": 10,
                "min_samples_split": 10,
                "random_state": 42,
                "n_jobs": -1,
            },
            "gradient_boosting": {
                "n_estimators": 100,
                "max_depth": 5,
                "learning_rate": 0.1,
                "random_state": 42,
            },
            "logistic": {
                "max_iter": 1000,
                "random_state": 42,
                "multi_class": "multinomial",
            },
        }
        return defaults.get(model_type, {})
    
    def _get_feature_importance(
        self,
        model: BaseEstimator,
        feature_names: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """提取特徵重要性"""
        names = feature_names or self.feature_names
        
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        elif hasattr(model, "coef_"):
            importances = np.abs(model.coef_).mean(axis=0)
        else:
            return {}
        
        # 標準化到 [0, 1]
        max_imp = importances.max() if importances.max() > 0 else 1
        return {name: float(imp / max_imp) for name, imp in zip(names, importances)}
    
    def _compute_metric(
        self,
        model: BaseEstimator,
        X: np.ndarray,
        y: np.ndarray,
        metric: str,
        average: str = "weighted"
    ) -> float:
        """計算指定指標"""
        from sklearn.metrics import precision_score, recall_score, f1_score
        
        y_pred = model.predict(X)
        
        if metric == "precision":
            return precision_score(y, y_pred, average=average, zero_division=0)
        elif metric == "recall":
            return recall_score(y, y_pred, average=average, zero_division=0)
        elif metric == "f1":
            return f1_score(y, y_pred, average=average, zero_division=0)
        
        return 0.0
    
    def _generate_version(self) -> str:
        """生成版本號"""
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        count = sum(
            1 for k in self.registry._registry["models"]
            if timestamp in k
        )
        return f"{timestamp}_{count + 1}"
    
    def _save_model(
        self,
        model: BaseEstimator,
        model_name: str,
        version: str,
    ) -> Path:
        """保存模型到磁盤"""
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{model_name}_{version}.pkl"
        path = self.model_dir / filename
        
        with open(path, "wb") as f:
            pickle.dump(model, f)
        
        # 同時保存 scaler
        if self.scaler:
            scaler_path = self.model_dir / f"{model_name}_{version}_scaler.pkl"
            with open(scaler_path, "wb") as f:
                pickle.dump(self.scaler, f)
        
        return path
