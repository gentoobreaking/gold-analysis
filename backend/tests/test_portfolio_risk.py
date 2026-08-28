"""
T064 - 投資組合級風險單元測試（相關性矩陣 / 組合 VaR-CVaR / 因子曝險）
"""
from __future__ import annotations

import numpy as np
from app.risk.portfolio import (
    correlation_matrix,
    factor_exposure,
    portfolio_var_from_returns,
)


def _series(n: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    return list(rng.normal(0.0005, 0.01, n))


def test_correlation_matrix_properties():
    # 構造一組有已知關係的序列
    base = np.array(_series(200, 1))
    gold = list(base + np.random.default_rng(2).normal(0, 0.002, 200))
    dxy = list(-0.8 * base + np.random.default_rng(3).normal(0, 0.004, 200))  # 與 gold 負相關
    btc = list(0.3 * base + np.random.default_rng(4).normal(0, 0.02, 200))   # 與 gold 弱正相關
    spx = list(np.random.default_rng(5).normal(0, 0.01, 200))               # 近似無關

    returns = {"GOLD": gold, "DXY": dxy, "BTC": btc, "SPX": spx}
    res = correlation_matrix(returns)
    m = res["matrix"]
    assets = res["assets"]

    assert res["valid"] is True
    assert len(assets) == 4
    # 對角線 = 1
    for i in range(4):
        assert abs(m[i][i] - 1.0) < 1e-9
    # 對稱
    for i in range(4):
        for j in range(4):
            assert abs(m[i][j] - m[j][i]) < 1e-9
    # 值落在 [-1, 1]
    for row in m:
        for v in row:
            assert -1.0 <= v <= 1.0
    # GOLD vs DXY 應為負相關
    gi, di = assets.index("GOLD"), assets.index("DXY")
    assert m[gi][di] < -0.3
    # GOLD vs SPX 應接近 0
    si = assets.index("SPX")
    assert abs(m[gi][si]) < 0.3


def test_correlation_matrix_handles_short_overlap():
    a = _series(100, 7)
    b = _series(10, 8)  # 過短，低於預設 min_overlap=30
    res = correlation_matrix({"A": a, "B": b})
    assert res["valid"] is False
    assert np.isnan(res["matrix"][0][1])


def test_portfolio_var_considers_correlation_not_simple_sum():
    # 兩資產等權重；當完全正相關時組合波動≈單資產，當負相關時更小
    x = np.array(_series(300, 11))
    y_pos = list(x)                                   # 完全相關
    y_neg = list(-x)                                  # 完全負相關
    cov_pos = np.cov(np.column_stack([x, x]), rowvar=False, ddof=1)
    cov_neg = np.cov(np.column_stack([x, -x]), rowvar=False, ddof=1)

    r_pos = portfolio_var_from_returns([0.5, 0.5], {"A": list(x), "B": y_pos}, confidence=0.95)
    r_neg = portfolio_var_from_returns([0.5, 0.5], {"A": list(x), "B": y_neg}, confidence=0.95)

    # 完全正相關：組合 VaR 應大於（或等於）完全負相關的對沖效果
    assert r_pos["var"] > r_neg["var"]
    assert r_pos["portfolio_vol"] > r_neg["portfolio_vol"]
    # CVaR >= VaR（常態下）
    assert r_pos["cvar"] >= r_pos["var"]
    # 數值有限
    assert np.isfinite(r_pos["var"]) and np.isfinite(r_neg["cvar"])


def test_factor_exposure_recovers_known_beta():
    # 構造 gold = 0.5*DXY + 0.3*BTC + noise，回歸應逼近 beta
    dxy = np.array(_series(300, 21))
    btc = np.array(_series(300, 22))
    rng = np.random.default_rng(23)
    gold = 0.5 * dxy + 0.3 * btc + rng.normal(0, 0.001, 300)

    exp = factor_exposure(list(gold), {"DXY": list(dxy), "BTC": list(btc)})
    assert "DXY" in exp and "BTC" in exp
    assert abs(exp["DXY"] - 0.5) < 0.1
    assert abs(exp["BTC"] - 0.3) < 0.1
    assert 0.0 <= exp.get("_r2", 0.0) <= 1.0


def test_factor_exposure_empty_factors():
    assert factor_exposure([0.01, 0.02], {}) == {}
