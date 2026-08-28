"""
Decision explainability - SHAP / feature-importance contributions.

為決策提供「為什麼」的可解釋性：
- ML 決策：優先使用 SHAP（若已安裝），否則回落到模型內建 feature_importances_ / coef_。
- 規則決策：根據各維度評分與權重，給出 top 貢獻因子與觸發規則說明。

與 T056（告警帶理由）、T065（LLM 敘事）形成「為什麼」敘事鏈。
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:  # SHAP 為可選依賴；未安裝時自動回落到 feature_importance
    import shap  # type: ignore

    _HAS_SHAP = True
except Exception:  # pragma: no cover - 依賴缺失時不強制
    shap = None
    _HAS_SHAP = False


# 簡易快取：同一模型物件只需建一次 explainer
_EXPLAINER_CACHE: dict[int, Any] = {}


def _to_2d_row(X_row: Any) -> np.ndarray:
    """將 1 列 DataFrame / 2D array / list 轉為 (1, n) float array。"""
    if hasattr(X_row, "values"):
        arr = np.asarray(X_row.values, dtype=float)
    elif isinstance(X_row, np.ndarray):
        arr = X_row.astype(float)
    elif isinstance(X_row, (list, tuple)):
        arr = np.asarray(X_row, dtype=float)
    else:
        arr = np.asarray(X_row, dtype=float)
    arr = np.atleast_2d(arr)
    return arr


def _shap_row_values(sv: Any, model: Any, X: np.ndarray) -> np.ndarray:
    """從 SHAP 輸出中取出「預測類別」那一列的 1D 貢獻向量。"""
    # 多類別時 shap_values 為 list[array]，取預測類別
    if isinstance(sv, list):
        pred = int(np.asarray(model.predict(X))[0])
        idx = pred if pred < len(sv) else 0
        vals = np.asarray(sv[idx], dtype=float)
    else:
        vals = np.asarray(sv, dtype=float)
    return vals.reshape(-1)


def explain_ml_decision(
    model: Any,
    feature_names: Sequence[str],
    X_row: Any,
    top_n: int = 8,
    background: Any | None = None,
) -> dict[str, Any]:
    """
    對單筆特徵向量計算 top-N 特徵貢獻（含方向）。

    Returns:
        {
          "method": "shap" | "feature_importance",
          "model_type": str,
          "top_features": [
            {"feature", "contribution": float, "direction": "positive"|"negative"|"neutral", "value": float},
            ...,
          ],
        }
    """
    feature_names = list(feature_names)
    X = _to_2d_row(X_row)
    if X.shape[1] != len(feature_names):
        raise ValueError(f"特徵數不符: X 有 {X.shape[1]} 列，feature_names 有 {len(feature_names)} 個")

    contributions: dict[str, float] = {}
    method = "feature_importance"

    if _HAS_SHAP and shap is not None:
        try:
            key = id(model)
            explainer = _EXPLAINER_CACHE.get(key)
            if explainer is None:
                if hasattr(model, "feature_importances_") or "Tree" in type(model).__name__:
                    explainer = shap.TreeExplainer(model)
                else:
                    bg = background if background is not None else X
                    explainer = shap.Explainer(model, bg)
                _EXPLAINER_CACHE[key] = explainer

            sv = explainer.shap_values(X)
            vals = _shap_row_values(sv, model, X)
            for name, v in zip(feature_names, vals):
                contributions[name] = float(v)
            method = "shap"
        except Exception as exc:  # pragma: no cover - SHAP 失敗時回落
            logger.warning("SHAP 解釋失敗，回落 feature_importance: %s", exc)
            contributions = {}

    if not contributions:
        # 回落：模型內建重要性 / 係數
        if hasattr(model, "feature_importances_"):
            imp = np.asarray(model.feature_importances_, dtype=float)
            for name, v in zip(feature_names, imp):
                contributions[name] = float(v)
        elif hasattr(model, "coef_"):
            coef = np.asarray(model.coef_, dtype=float)
            coef = coef.mean(axis=0) if coef.ndim > 1 else coef
            for name, v in zip(feature_names, coef):
                contributions[name] = float(abs(v))
        else:
            contributions = {name: 0.0 for name in feature_names}
        method = "feature_importance"

    feature_values = X[0]

    def direction_of(name: str, v: float) -> str:
        if method == "feature_importance":
            return "neutral"
        return "positive" if v > 0 else "negative"

    ranked = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)[:top_n]
    top_features = [
        {
            "feature": name,
            "contribution": round(v, 8),
            "direction": direction_of(name, v),
            "value": round(float(feature_values[i]), 6) if i < len(feature_values) else None,
        }
        for i, (name, v) in enumerate(ranked)
    ]

    return {
        "method": method,
        "model_type": type(model).__name__,
        "top_features": top_features,
    }


def explain_rule_decision(
    scores: dict[str, float],
    weights: dict[str, float] | None = None,
    decision_type: str | None = None,
    reasoning_zh: str | None = None,
) -> dict[str, Any]:
    """
    對規則（維度加權）決策，產出 top 貢獻因子與觸發規則說明。

    scores: {"technical", "fundamental", "risk", "composite"}（各為 -1..1，越高越偏多頭）
    weights: {"technical", "fundamental", "risk"}（加權）
    """
    weights = weights or {"technical": 0.35, "fundamental": 0.30, "risk": 0.35}

    # 每個維度對「多頭傾向」的 tilt：
    #   tech / fund 越高越偏多頭；risk 越高代表風險越大 => 越偏空頭
    tech = float(scores.get("technical", 0.0))
    fund = float(scores.get("fundamental", 0.0))
    risk = float(scores.get("risk", 0.0))

    tilts = {
        "technical": tech * weights.get("technical", 0.35),
        "fundamental": fund * weights.get("fundamental", 0.30),
        "risk": -risk * weights.get("risk", 0.35),
    }

    notes = {
        "technical": "技術面",
        "fundamental": "基本面",
        "risk": "風險面",
    }

    factors = []
    for dim, tilt in tilts.items():
        direction = "bullish" if tilt > 0 else ("bearish" if tilt < 0 else "neutral")
        factors.append(
            {
                "factor": dim,
                "label": notes.get(dim, dim),
                "score": round(float(scores.get(dim, 0.0)), 4),
                "weight": weights.get(dim, 0.0),
                "tilt": round(tilt, 4),
                "direction": direction,
            }
        )

    factors.sort(key=lambda f: abs(f["tilt"]), reverse=True)

    triggered_rules: list[str] = []
    if decision_type:
        triggered_rules.append(f"決策類型 = {decision_type}")
    if tech > 0.3:
        triggered_rules.append("技術指標呈現明確多頭趨勢")
    if fund > 0.2:
        triggered_rules.append("基本面因素支撐金價")
    if risk < -0.3:
        triggered_rules.append("風險評估偏高，壓抑多頭信心")
    if reasoning_zh:
        triggered_rules.append(reasoning_zh)

    return {
        "method": "rule_based",
        "top_factors": factors,
        "triggered_rules": triggered_rules,
    }
