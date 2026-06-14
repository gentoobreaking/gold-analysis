"""
Model Evaluator Module - 模型評估與分析
負責模型性能評估、錯誤分析、預測解釋。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

logger = logging.getLogger(__name__)


@dataclass
class ClassificationMetrics:
    """分類模型指標"""
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: Optional[float] = None
    confusion_matrix: Optional[np.ndarray] = None
    per_class_metrics: Optional[Dict[str, Dict[str, float]]] = None


@dataclass
class RegressionMetrics:
    """迴歸模型指標"""
    mse: float
    rmse: float
    mae: float
    r2: float


@dataclass
class EvaluationReport:
    """完整評估報告"""
    model_name: str
    version: str
    evaluated_at: str
    task_type: str  # "classification" | "regression"
    metrics: Any
    feature_analysis: Dict[str, float] = field(default_factory=dict)
    prediction_distribution: Dict[str, int] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


class ModelEvaluator:
    """
    模型評估器 - 全面評估模型性能
    
    功能:
    - 分類/迴歸指標計算
    - 混淆矩陣分析
    - 類別分佈評估
    - 預測解釋（錯誤分析）
    - 評估報告生成
    """
    
    def __init__(self):
        self.current_report: Optional[EvaluationReport] = None
    
    # ─── 公開 API ─────────────────────────────────────────────────────────────
    
    def evaluate_classification(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: Optional[np.ndarray] = None,
        class_labels: Optional[List[str]] = None,
        model_name: str = "unknown",
        version: str = "v0",
    ) -> EvaluationReport:
        """
        評估分類模型
        
        Args:
            y_true: 真實標籤
            y_pred: 預測標籤
            y_proba: 預測概率（用於 ROC-AUC）
            class_labels: 類別標籤
            model_name: 模型名稱
            version: 模型版本
            
        Returns:
            EvaluationReport
        """
        from datetime import datetime
        
        # 基本指標
        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, average="weighted", zero_division=0)
        recall = recall_score(y_true, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)
        
        # 混淆矩陣
        cm = confusion_matrix(y_true, y_pred)
        
        # ROC-AUC（多類別使用 OvR）
        roc_auc = None
        if y_proba is not None and len(np.unique(y_true)) == 2:
            try:
                roc_auc = roc_auc_score(y_true, y_proba[:, 1])
            except Exception:
                pass
        
        # 類別報告
        report = classification_report(
            y_true, y_pred, zero_division=0, output_dict=True
        )
        per_class = {
            str(k): {
                "precision": v["precision"] if "precision" in v else 0.0,
                "recall": v["recall"] if "recall" in v else 0.0,
                "f1": v["f1-score"] if "f1-score" in v else 0.0,
                "support": int(v["support"]) if "support" in v else 0,
            }
            for k, v in report.items()
            if isinstance(v, dict) and k != "accuracy"
        }
        
        # 預測分佈
        unique, counts = np.unique(y_pred, return_counts=True)
        pred_dist = {str(k): int(c) for k, c in zip(unique, counts)}
        
        # 構建指標
        metrics = ClassificationMetrics(
            accuracy=float(accuracy),
            precision=float(precision),
            recall=float(recall),
            f1=float(f1),
            roc_auc=float(roc_auc) if roc_auc else None,
            confusion_matrix=cm,
            per_class_metrics=per_class,
        )
        
        # 構建報告
        notes = []
        if accuracy < 0.5:
            notes.append("⚠️ 準確率低於 50%，模型表現不佳")
        if metrics.roc_auc and metrics.roc_auc < 0.6:
            notes.append("⚠️ ROC-AUC 偏低，區分能力不足")
        if len(unique) < 2 and len(np.unique(y_true)) > 1:
            notes.append("⚠️ 模型預測結果只有一個類別，存在偏差")
        
        self.current_report = EvaluationReport(
            model_name=model_name,
            version=version,
            evaluated_at=datetime.utcnow().isoformat(),
            task_type="classification",
            metrics=metrics,
            prediction_distribution=pred_dist,
            notes=notes,
        )
        
        logger.info(
            f"分類評估完成: Acc={accuracy:.4f} | "
            f"Precision={precision:.4f} | Recall={recall:.4f} | F1={f1:.4f}"
        )
        
        return self.current_report
    
    def evaluate_regression(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        model_name: str = "unknown",
        version: str = "v0",
    ) -> EvaluationReport:
        """
        評估迴歸模型
        
        Args:
            y_true: 真實值
            y_pred: 預測值
            model_name: 模型名稱
            version: 模型版本
            
        Returns:
            EvaluationReport
        """
        from datetime import datetime
        
        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_true, y_pred)
        r2 = r2_score(y_true, y_pred)
        
        # 殘差分析
        residuals = y_true - y_pred
        notes = []
        if r2 < 0:
            notes.append("⚠️ R² 為負，模型解釋力極差")
        if rmse / np.mean(y_true) > 0.5:
            notes.append("⚠️ RMSE/均值 比過高，相對誤差大")
        
        metrics = RegressionMetrics(
            mse=float(mse),
            rmse=float(rmse),
            mae=float(mae),
            r2=float(r2),
        )
        
        self.current_report = EvaluationReport(
            model_name=model_name,
            version=version,
            evaluated_at=datetime.utcnow().isoformat(),
            task_type="regression",
            metrics=metrics,
            notes=notes,
        )
        
        logger.info(f"迴歸評估完成: RMSE={rmse:.4f} | MAE={mae:.4f} | R²={r2:.4f}")
        
        return self.current_report
    
    def analyze_errors(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        feature_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        錯誤分析 - 找出模型預測錯誤的樣本模式
        
        Args:
            y_true: 真實標籤
            y_pred: 預測標籤
            feature_df: 特徵數據框（用於關聯分析）
            
        Returns:
            錯誤分析結果
        """
        errors_mask = y_true != y_pred
        total_errors = errors_mask.sum()
        total_samples = len(y_true)
        error_rate = total_errors / total_samples
        
        analysis: Dict[str, Any] = {
            "total_errors": int(total_errors),
            "total_samples": int(total_samples),
            "error_rate": float(error_rate),
            "error_by_true_class": {},
            "most_confused_pairs": [],
        }
        
        # 錯誤按真實類別分組
        for cls in np.unique(y_true):
            mask = y_true == cls
            n_total = mask.sum()
            n_errors = (errors_mask & mask).sum()
            analysis["error_by_true_class"][str(cls)] = {
                "total": int(n_total),
                "errors": int(n_errors),
                "error_rate": float(n_errors / n_total) if n_total > 0 else 0.0,
            }
        
        # 混淆對
        cm = confusion_matrix(y_true, y_pred)
        n_classes = cm.shape[0]
        for i in range(n_classes):
            for j in range(n_classes):
                if i != j and cm[i, j] > 0:
                    analysis["most_confused_pairs"].append({
                        "true": str(i),
                        "predicted": str(j),
                        "count": int(cm[i, j]),
                    })
        
        # 按錯誤數量排序
        analysis["most_confused_pairs"] = sorted(
            analysis["most_confused_pairs"],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]  # Top 5
        
        # 特徵分析（若提供）
        if feature_df is not None:
            error_features = feature_df.iloc[errors_mask]
            correct_features = feature_df.iloc[~errors_mask]
            
            if not error_features.empty:
                error_mean = error_features.mean()
                correct_mean = correct_features.mean()
                diff = (error_mean - correct_mean) / (correct_mean + 1e-10)
                
                analysis["feature_analysis"] = {
                    col: float(d)
                    for col, d in diff.items()
                    if not np.isnan(d)
                }
                # 取差異最大的特徵
                sorted_features = sorted(
                    analysis["feature_analysis"].items(),
                    key=lambda x: abs(x[1]),
                    reverse=True
                )[:10]
                analysis["top_differentiating_features"] = sorted_features
        
        return analysis
    
    def cross_validate_with_report(
        self,
        model: Any,
        X: np.ndarray,
        y: np.ndarray,
        cv: int = 5,
        task_type: str = "classification",
    ) -> Dict[str, List[float]]:
        """
        使用交叉驗證生成評估報告
        
        Args:
            model: sklearn 模型
            X: 特徵矩陣
            y: 標籤
            cv: 折數
            task_type: 任務類型
            
        Returns:
            各指標的交叉驗證分數
        """
        from sklearn.model_selection import cross_val_predict, TimeSeriesSplit
        
        tscv = TimeSeriesSplit(n_splits=cv)
        scores: Dict[str, List[float]] = {
            "accuracy": [],
            "f1": [],
        }
        
        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]
            
            model.fit(X_train, y_train)
            y_pred = model.predict(X_val)
            
            scores["accuracy"].append(accuracy_score(y_val, y_pred))
            scores["f1"].append(f1_score(y_val, y_pred, average="weighted", zero_division=0))
        
        summary = {
            metric: {
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals)),
                "min": float(np.min(vals)),
                "max": float(np.max(vals)),
            }
            for metric, vals in scores.items()
        }
        
        logger.info(f"交叉驗證完成: {summary}")
        return summary
    
    def get_report(self) -> Optional[EvaluationReport]:
        """獲取當前評估報告"""
        return self.current_report
    
    def print_report(self, report: Optional[EvaluationReport] = None) -> str:
        """
        格式化打印評估報告
        
        Args:
            report: 報告對象，預設使用當前報告
            
        Returns:
            格式化的報告字符串
        """
        report = report or self.current_report
        if not report:
            return "沒有可用的評估報告"
        
        lines = [
            f"═══ {report.model_name} ({report.version}) 評估報告 ═══",
            f"評估時間: {report.evaluated_at}",
            f"任務類型: {report.task_type}",
            "",
        ]
        
        if report.task_type == "classification":
            m = report.metrics
            lines.extend([
                "【分類指標】",
                f"  準確率 (Accuracy):  {m.accuracy:.4f}",
                f"  精確率 (Precision): {m.precision:.4f}",
                f"  召回率 (Recall):    {m.recall:.4f}",
                f"  F1 分數:            {m.f1:.4f}",
            ])
            if m.roc_auc:
                lines.append(f"  ROC-AUC:            {m.roc_auc:.4f}")
            
            if m.per_class_metrics:
                lines.append("")
                lines.append("【按類別】")
                for cls, cls_metrics in m.per_class_metrics.items():
                    lines.append(
                        f"  類別 {cls}: P={cls_metrics['precision']:.2f} "
                        f"R={cls_metrics['recall']:.2f} F1={cls_metrics['f1']:.2f} "
                        f"(n={cls_metrics['support']})"
                    )
            
            if report.prediction_distribution:
                lines.append("")
                lines.append("【預測分佈】")
                for cls, count in report.prediction_distribution.items():
                    lines.append(f"  類別 {cls}: {count}")
        
        elif report.task_type == "regression":
            m = report.metrics
            lines.extend([
                "【迴歸指標】",
                f"  MSE:  {m.mse:.6f}",
                f"  RMSE: {m.rmse:.6f}",
                f"  MAE:  {m.mae:.6f}",
                f"  R²:   {m.r2:.4f}",
            ])
        
        if report.notes:
            lines.append("")
            lines.append("【注意事項】")
            for note in report.notes:
                lines.append(f"  {note}")
        
        return "\n".join(lines)
