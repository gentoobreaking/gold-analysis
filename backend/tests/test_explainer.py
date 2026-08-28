"""
T062 - 決策可解釋性 (SHAP / feature_importance / rule-based) 單元測試
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from app.ml.explainer import explain_ml_decision, explain_rule_decision
from sklearn.ensemble import RandomForestClassifier

FEATURE_NAMES = ["rsi", "macd", "ma_20", "volume", "atr", "sentiment"]


def _train_tiny_model(n_samples: int = 200, seed: int = 42):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n_samples, len(FEATURE_NAMES)))
    # 簡單線性邊界：rsi 與 sentiment 偏多頭
    logits = 0.8 * X[:, 0] + 0.6 * X[:, 4] - 0.5 * X[:, 1]
    y = (logits > 0).astype(int)
    model = RandomForestClassifier(n_estimators=30, random_state=seed)
    model.fit(X, y)
    return model


def test_explain_ml_decision_returns_top_features_with_direction():
    model = _train_tiny_model()
    row = pd.DataFrame([{f: 0.3 for f in FEATURE_NAMES}])

    result = explain_ml_decision(model, FEATURE_NAMES, row, top_n=4)

    assert result["method"] in ("shap", "feature_importance")
    assert result["model_type"] == "RandomForestClassifier"
    top = result["top_features"]
    assert 1 <= len(top) <= 4
    for item in top:
        assert set(item.keys()) >= {"feature", "contribution", "direction", "value"}
        assert item["feature"] in FEATURE_NAMES
        assert isinstance(item["contribution"], float)
        assert item["direction"] in ("positive", "negative", "neutral")
    # 貢獻應依絕對值遞減
    contribs = [abs(i["contribution"]) for i in top]
    assert contribs == sorted(contribs, reverse=True)


def test_explain_ml_decision_feature_count_guard():
    model = _train_tiny_model()
    row = pd.DataFrame([{f: 0.1 for f in FEATURE_NAMES[:-1]}])  # 少一個特徵
    with pytest.raises(ValueError):
        explain_ml_decision(model, FEATURE_NAMES, row)


def test_explain_rule_decision_top_factors_and_triggered_rules():
    scores = {"technical": 0.6, "fundamental": 0.2, "risk": 0.4, "composite": 0.3}
    weights = {"technical": 0.35, "fundamental": 0.30, "risk": 0.35}

    result = explain_rule_decision(
        scores=scores,
        weights=weights,
        decision_type="buy",
        reasoning_zh="技術面與基本面共振",
    )

    assert result["method"] == "rule_based"
    factors = result["top_factors"]
    assert len(factors) == 3
    for f in factors:
        assert set(f.keys()) >= {"factor", "label", "score", "weight", "tilt", "direction"}
        assert f["direction"] in ("bullish", "bearish", "neutral")
    # 技術面評分最高（tilt 最大）應排第一
    assert factors[0]["factor"] == "technical"
    assert factors[0]["direction"] == "bullish"
    # 風險面為正（較高風險）=> 偏空
    risk = next(f for f in factors if f["factor"] == "risk")
    assert risk["direction"] == "bearish"

    rules = result["triggered_rules"]
    assert any("buy" in r for r in rules)
    assert any("技術" in r for r in rules)


def test_recommendation_schema_accepts_explanation():
    from datetime import datetime

    from app.api.schemas.decisions import DecisionResponse, RecommendationResponse
    from app.models.decision import DecisionType, DecisionSource

    decision = DecisionResponse(
        id=1,
        user_id=1,
        decision_type=DecisionType.BUY,
        source=DecisionSource.AI_ANALYSIS,
        asset="GOLD",
        signal_strength=0.8,
        confidence=0.75,
        price_target=2050.0,
        stop_loss=1980.0,
        reason_zh="技術面與基本面共振",
        reason_en="Technical and fundamental aligned",
        indicators_snapshot="{\"rsi\": 55}",
        analysis_scores="{\"technical\": 0.4}",
        is_executed=False,
        executed_at=None,
        execution_price=None,
        model_version="v1",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    explanation = explain_rule_decision(
        scores={"technical": 0.5, "fundamental": 0.2, "risk": -0.2},
        decision_type="buy",
    )
    rec = RecommendationResponse(
        decision=decision,
        reasoning="test",
        risk_level="medium",
        explanation=explanation,
    )
    assert rec.explanation is not None
    assert rec.explanation["method"] == "rule_based"
