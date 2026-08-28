"""
T053 - ModelHealthChecker.health_check `latest` 修復測試

驗證：
- health_check 不再因未定義 `latest` 拋 NameError
- 正確把已註冊模型的 model_name / version 傳遞到評估報告與健康報告
- registry 無模型時（get_latest 回傳 None）應拋 RuntimeError 而非崩潰
"""

import numpy as np
import pandas as pd
import pytest
from app.ml.model_monitor import ModelHealthChecker


class _FakeModel:
    def predict(self, X):
        return np.zeros(len(X))

    def predict_proba(self, X):
        return np.tile([0.5, 0.5], (len(X), 1))


class _FakeRegistry:
    def __init__(self, latest=None):
        self._latest = latest

    def get_latest(self, model_name=None):
        return self._latest

    def load_model(self, version, model_name):
        return _FakeModel()


class _FakeEval:
    def evaluate_classification(self, *, y_true, y_pred, y_proba, model_name, version):
        class _Report:
            def __init__(self):
                self.metrics = {"accuracy": 1.0}

        return _Report()


class _FakeFE:
    def fit_transform(self, df):
        return df


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(
        "app.ml.model_monitor.ModelRegistry", lambda *a, **k: _FakeRegistry()
    )
    monkeypatch.setattr("app.ml.model_monitor.FeatureEngineer", _FakeFE)
    monkeypatch.setattr("app.ml.model_monitor.ModelEvaluator", _FakeEval)
    yield


def _sample_df(n=20):
    return pd.DataFrame(
        {
            "feature_a": np.random.rand(n),
            "feature_b": np.random.rand(n),
            "label": np.random.randint(0, 2, n),
        }
    )


def test_health_check_uses_latest_without_name_error(patched):
    monkeypatch_registry()

    checker = ModelHealthChecker()
    result = checker.health_check(_sample_df())

    assert result.get("skipped") is not True
    assert result["model_version"] == "v1"
    assert result["metrics"] == {"accuracy": 1.0}
    assert "drift" in result


def monkeypatch_registry():
    # 由於 fixture 已替換 ModelRegistry 為無參 factory，
    # 這裡進一步指定回傳內容
    import app.ml.model_monitor as mm

    mm.ModelRegistry = lambda *a, **k: _FakeRegistry(
        latest={"version": "v1", "model_name": "gold_clf"}
    )


def test_health_check_no_model_raises(patched):
    checker = ModelHealthChecker()
    with pytest.raises(RuntimeError):
        checker.health_check(_sample_df())
