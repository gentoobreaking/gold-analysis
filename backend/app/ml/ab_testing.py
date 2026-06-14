"""
A/B Testing Framework for ML Models
支援多模型的線上 A/B 測試與統計分析。
"""

from __future__ import annotations

import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── 數據模型 ───────────────────────────────────────────────────────

@dataclass
class ExperimentConfig:
    """A/B 測試配置"""
    name: str
    variants: List[str]  # 例如 ["v1", "v2"]
    traffic_split: List[float] = field(default_factory=lambda: [0.5, 0.5])
    metrics: List[str] = field(default_factory=lambda: ["accuracy", "profit"])
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    def __post_init__(self) -> None:
        if len(self.variants) != len(self.traffic_split):
            raise ValueError("variants 與 traffic_split 長度必須相同")
        if not 0.999 < sum(self.traffic_split) < 1.001:
            raise ValueError("traffic_split 必須加總為 1.0")


@dataclass
class ExperimentRun:
    """單次實驗紀錄（每條決策）"""
    experiment_id: str
    variant: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    features: Dict[str, Any] = field(default_factory=dict)
    prediction: Any = None
    actual: Any = None
    metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "variant": self.variant,
            "timestamp": self.timestamp.isoformat(),
            "features": self.features,
            "prediction": self.prediction,
            "actual": self.actual,
            "metrics": self.metrics,
        }


# ─── A/B 測試管理器 ─────────────────────────────────────────────────────

class ABTestEngine:
    """管理所有實驗與統計分析"""

    def __init__(self):
        self.experiments: Dict[str, ExperimentConfig] = {}
        self.runs: List[ExperimentRun] = []
        self.logger = logging.getLogger(__name__)

    # ─── 實驗生命週期 ────────────────────────────────────────
    def create_experiment(self, config: ExperimentConfig) -> str:
        exp_id = uuid.uuid4().hex[:8]
        self.experiments[exp_id] = config
        self.logger.info(f"建立 A/B 測試 {config.name} (id={exp_id})")
        return exp_id

    def delete_experiment(self, exp_id: str) -> bool:
        if exp_id in self.experiments:
            del self.experiments[exp_id]
            self.runs = [r for r in self.runs if r.experiment_id != exp_id]
            self.logger.info(f"刪除 A/B 測試 {exp_id}")
            return True
        return False

    # ─── 變體分配 ────────────────────────────────────────
    def _select_variant(self, config: ExperimentConfig) -> str:
        """根據 traffic_split 隨機抽樣返回 variant"""
        rnd = random.random()
        cumulative = 0.0
        for variant, weight in zip(config.variants, config.traffic_split):
            cumulative += weight
            if rnd <= cumulative:
                return variant
        return config.variants[-1]

    # ─── 記錄一次決策 ────────────────────────────────────────
    def record_decision(
        self,
        exp_id: str,
        features: Dict[str, Any],
        prediction: Any,
        actual: Any,
        metrics: Optional[Dict[str, float]] = None,
    ) -> ExperimentRun:
        """將一次決策結果寫入實驗日誌"""
        config = self.experiments.get(exp_id)
        if not config:
            raise ValueError(f"實驗 {exp_id} 不存在")
        
        variant = self._select_variant(config)
        run = ExperimentRun(
            experiment_id=exp_id,
            variant=variant,
            features=features,
            prediction=prediction,
            actual=actual,
            metrics=metrics or {},
        )
        self.runs.append(run)
        self.logger.debug(f"A/B 記錄: exp={exp_id} variant={variant}")
        return run

    # ─── 統計分析 ────────────────────────────────────────
    def summarize(self, exp_id: str) -> Dict[str, Any]:
        """針對單個實驗返回聚合統計"""
        config = self.experiments.get(exp_id)
        if not config:
            raise ValueError(f"實驗 {exp_id} 不存在")
        
        # 過濾相關 run
        relevant = [r for r in self.runs if r.experiment_id == exp_id]
        summary: Dict[str, Any] = {"experiment": config.name, "variant_counts": {}, "metrics": {}}
        
        # 統計每個變體的樣本量
        for variant in config.variants:
            variant_runs = [r for r in relevant if r.variant == variant]
            summary["variant_counts"][variant] = len(variant_runs)
            # 指標聚合（均值）
            agg: Dict[str, float] = {}
            for metric in config.metrics:
                values = [r.metrics.get(metric, 0.0) for r in variant_runs if metric in r.metrics]
                agg[metric] = sum(values) / len(values) if values else 0.0
            summary["metrics"][variant] = agg
        
        self.logger.info(f"A/B 實驗 {exp_id} 彙總完成")
        return summary

    # ─── 持久化（簡易） ────────────────────────────────────
    def export_runs(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.runs]

    def import_runs(self, data: List[Dict[str, Any]]) -> None:
        for item in data:
            run = ExperimentRun(
                experiment_id=item["experiment_id"],
                variant=item["variant"],
                timestamp=datetime.fromisoformat(item["timestamp"]),
                features=item.get("features", {}),
                prediction=item.get("prediction"),
                actual=item.get("actual"),
                metrics=item.get("metrics", {}),
            )
            self.runs.append(run)
