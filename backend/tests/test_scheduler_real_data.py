"""
T054 - 排程監控/重訓改用真實資料來源測試

驗證：
- run_monitor_job / run_retrain_job 呼叫真實取數路徑（_fetch_real_price_df），
  而非 np.random 合成價格
- 真實取數回傳 None（資料不足/失敗）時，跳過本輪且不呼叫 run_monitor/run_retrain
- 傳入的 DataFrame 具備 date / close / label 欄位（符合 FeatureEngineer 與 health_check 需求）
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import AsyncMock, MagicMock

import app.main as main_mod
import numpy as np
import pandas as pd


def _real_shaped_df(n: int = 60) -> pd.DataFrame:
    """構造與 _fetch_real_price_df 同形狀的真實資料（date/close/label）"""
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 1900.0 + np.arange(n) * 0.5
    df = pd.DataFrame({"date": idx, "close": close})
    horizon, threshold = 5, 0.01
    future_return = df["close"].shift(-horizon) / df["close"] - 1
    df["label"] = np.select(
        [future_return > threshold, future_return < -threshold],
        [1, -1],
        default=0,
    )
    return df.dropna().reset_index(drop=True)


def test_run_monitor_job_uses_real_data(monkeypatch):
    spy = MagicMock(return_value={"health": {}, "drift": {}, "alerts": []})
    monkeypatch.setattr("app.ml.ops.run_monitor", spy)
    real_df = _real_shaped_df()
    monkeypatch.setattr(main_mod, "_fetch_real_price_df", AsyncMock(return_value=real_df))

    asyncio.run(main_mod.run_monitor_job())

    spy.assert_called_once()
    called_df = spy.call_args.args[0]
    assert isinstance(called_df, pd.DataFrame)
    assert {"date", "close", "label"}.issubset(called_df.columns)
    # 確保使用真實取數結果（而非 np.random 合成）
    assert called_df is real_df


def test_run_monitor_job_skips_when_no_data(monkeypatch):
    spy = MagicMock(return_value={})
    monkeypatch.setattr("app.ml.ops.run_monitor", spy)
    monkeypatch.setattr(main_mod, "_fetch_real_price_df", AsyncMock(return_value=None))

    asyncio.run(main_mod.run_monitor_job())

    spy.assert_not_called()


def test_run_retrain_job_uses_real_data(monkeypatch):
    spy = MagicMock(return_value={"retrained": False})
    monkeypatch.setattr("app.ml.ops.run_retrain", spy)
    real_df = _real_shaped_df()
    monkeypatch.setattr(main_mod, "_fetch_real_price_df", AsyncMock(return_value=real_df))

    asyncio.run(main_mod.run_retrain_job())

    spy.assert_called_once()
    called_df = spy.call_args.args[0]
    assert isinstance(called_df, pd.DataFrame)
    assert "label" in called_df.columns
    assert called_df is real_df
