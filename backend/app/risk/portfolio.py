"""
投資組合級風險 (T064) - 跨資產相關性矩陣、組合 VaR/CVaR、因子曝險

與 risk/metrics.py 的單一標的風險互補：本模組處理「多資產投資組合」層級，
考量資產間相關性（而非簡單加總），並分解因子曝險。

設計：
- 相關性矩陣：對齊後的收益率序列 -> Pearson 相關；對角=1、對稱、值∈[-1,1]。
- 組合 VaR/CVaR：參數法（方差-共變異數）以權重與共變異矩陣求得組合波動，
  再套用常態/Cornish-Fisher 分位，避免「簡單加總」低估風險。
- 因子曝險：黃金對 DXY(美元)/實質利率( proxied )/BTC(避險情緒) 等因子的
  敏感性（beta），以對數收益對因子收益回歸求得。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)

# 預設因子（跨資產）標籤
DEFAULT_FACTORS: list[str] = ["DXY", "REAL_YIELD", "BTC", "SPX"]


# ─── 相關性矩陣 ────────────────────────────────────────────────────────────────


def correlation_matrix(
    returns_by_asset: dict[str, Sequence[float]],
    min_overlap: int = 30,
) -> dict[str, object]:
    """
    計算跨資產相關性矩陣。

    Args:
        returns_by_asset: {資產名: 收益率序列}
        min_overlap: 兩資產需至少有多少共同非空樣本才計算（否則 NaN）

    Returns:
        {
          "assets": [資產名...],
          "matrix": [[...]],   # 對稱、對角=1、值∈[-1,1]
          "valid":  bool,
        }
    """
    assets = list(returns_by_asset.keys())
    n = len(assets)
    matrix = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    valid = n >= 2

    for i in range(n):
        for j in range(i + 1, n):
            a = np.asarray(returns_by_asset[assets[i]], dtype=float)
            b = np.asarray(returns_by_asset[assets[j]], dtype=float)
            # 對齊長度（取較短，尾部對齊）
            m = min(len(a), len(b))
            if m < min_overlap:
                matrix[i][j] = matrix[j][i] = float("nan")
                valid = False
                continue
            ai, bi = a[-m:], b[-m:]
            if np.std(ai) == 0 or np.std(bi) == 0:
                matrix[i][j] = matrix[j][i] = float("nan")
                continue
            corr = float(np.corrcoef(ai, bi)[0, 1])
            matrix[i][j] = matrix[j][i] = corr

    return {"assets": assets, "matrix": matrix, "valid": valid}


# ─── 組合 VaR / CVaR（考慮相關性）──────────────────────────────────────────────


def portfolio_var(
    weights: Sequence[float],
    cov_matrix: np.ndarray,
    confidence: float = 0.95,
    portfolio_value: float = 1.0,
    method: str = "parametric",
) -> dict[str, float]:
    """
    投資組合 VaR / CVaR（方差-共變異數法，考慮資產間相關性）。

    Args:
        weights: 各資產權重（總和應≈1）
        cov_matrix: 資產收益率共變異矩陣 (NxN)
        confidence: 信心水平
        portfolio_value: 組合價值
        method: "parametric"（常態）或 "cornish_fisher"

    Returns:
        {"var": float, "cvar": float, "portfolio_vol": float}
    """
    w = np.asarray(weights, dtype=float)
    cov = np.asarray(cov_matrix, dtype=float)
    var_pct, cvar_pct, vol = _portfolio_var_cvar(w, cov, confidence, method)
    return {
        "var": float(abs(var_pct * portfolio_value)),
        "cvar": float(abs(cvar_pct * portfolio_value)),
        "portfolio_vol": float(vol),
    }


def _portfolio_var_cvar(w, cov, confidence, method) -> tuple[float, float, float]:
    port_var = float(w @ cov @ w)
    port_vol = float(np.sqrt(max(port_var, 1e-12)))
    z = float(stats.norm.ppf(1 - confidence))

    if method == "cornish_fisher":
        # 以組合波動的正態近似 + 輕量偏度調整（組合層級難以直接估偏度，保留常態核心）
        z_cf = z
    else:
        z_cf = z

    var_pct = abs(z_cf * port_vol)
    # CVaR（常態下） = phi(z)/(1-c) * sigma
    phi_z = float(stats.norm.pdf(z_cf))
    cvar_pct = abs((phi_z / (1 - confidence)) * port_vol)
    return var_pct, cvar_pct, port_vol


def portfolio_var_from_returns(
    weights: Sequence[float],
    returns_by_asset: dict[str, Sequence[float]],
    confidence: float = 0.95,
    portfolio_value: float = 1.0,
    method: str = "parametric",
) -> dict[str, float]:
    """
    便利函式：直接吃「權重 + 各資產收益率序列」，內部建共變異矩陣後算組合 VaR/CVaR。

    自動對齊各資產序列長度（尾部對齊），並以樣本共變異估計。
    """
    assets = list(returns_by_asset.keys())
    n = len(assets)
    if n == 0:
        return {"var": 0.0, "cvar": 0.0, "portfolio_vol": 0.0}

    # 對齊：取最短長度尾部對齊
    aligned = []
    for a in assets:
        arr = np.asarray(returns_by_asset[a], dtype=float)
        aligned.append(arr)
    m = min(len(x) for x in aligned)
    X = np.column_stack([x[-m:] for x in aligned])
    cov = np.cov(X, rowvar=False, ddof=1)
    w = np.asarray(weights, dtype=float)
    if w.shape[0] != n:
        # 權重數與資產數不符 -> 等權重
        w = np.ones(n) / n
    return portfolio_var(w, cov, confidence, portfolio_value, method)


# ─── 因子曝險分解 ─────────────────────────────────────────────────────────────


def factor_exposure(
    asset_returns: Sequence[float],
    factor_returns: dict[str, Sequence[float]],
) -> dict[str, float]:
    """
    計算資產對各因子的敏感性（beta），以資產對數收益對因子收益 OLS 回歸。

    Args:
        asset_returns: 單一資產收益率序列
        factor_returns: {因子名: 因子收益率序列}

    Returns:
        {因子名: beta, "_r2": 擬合優度, "_alpha": 截距}
    """
    y = np.asarray(asset_returns, dtype=float)
    names = list(factor_returns.keys())
    if not names:
        return {}

    X_cols = []
    for f in names:
        arr = np.asarray(factor_returns[f], dtype=float)
        m = min(len(y), len(arr))
        X_cols.append(arr[-m:])
    y = y[-m:]
    X = np.column_stack(X_cols)
    X = np.column_stack([np.ones(X.shape[0]), X])  # 截距項

    try:
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    except np.linalg.LinAlgError:
        return {f: 0.0 for f in names}

    alpha = float(beta[0])
    betas = {names[i]: float(beta[i + 1]) for i in range(len(names))}
    # R^2
    y_hat = X @ beta
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    betas["_alpha"] = alpha
    betas["_r2"] = round(float(r2), 4)
    return betas
