"""
風險評估 Agent

整合風險指標（VaR/波動率/回撤等）+ 止損/倉位管理，輸出風險報告。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from ..agents.base import GoldAnalysisAgent
from ..risk.metrics import (
    calculate_volatility,
    calculate_var_historical,
    calculate_var_parametric,
    calculate_var_cornish_fisher,
    calculate_cvar,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_calmar_ratio,
)
from ..risk.position import (
    RiskLevel,
    StopLossStrategy,
    PositionSizer,
    calculate_stop_loss,
    calculate_position_size,
    assess_risk_level,
)

logger = logging.getLogger(__name__)


class RiskAssessmentAgent(GoldAnalysisAgent):
    """
    風險評估 Agent

    接收持倉數據，輸出：
    - 風險指標（VaR/波動率/回撤/夏普等）
    - 止損建議
    - 倉位建議
    - 風險評級
    """

    def __init__(
        self,
        model: str = "qclaw/modelroute",
        temperature: float = 0.3,
        max_tokens: int = 1500,
    ):
        super().__init__(
            name="RiskAssessmentAgent",
            role="risk_assessment",
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        執行風險評估

        Args:
            context: {
                "prices": List[float]（價格序列），
                "returns": List[float]（可選，收益率序列），
                "entry_price": float（進場價），
                "position_type": str（"long" 或 "short"），
                "capital": float（總資金），
                "ohlc": Dict（可選，含 highs/lows），
            }

        Returns:
            風險評估報告
        """
        prices = np.array(context.get("prices", []), dtype=np.float64)
        entry_price = float(context.get("entry_price", prices[-1] if len(prices) > 0 else 0))
        position_type = context.get("position_type", "long")
        capital = float(context.get("capital", 100000))
        ohlc = context.get("ohlc", {})
        highs = ohlc.get("highs")
        lows = ohlc.get("lows")
        closes = prices.tolist()

        if len(prices) < 20:
            return {
                "error": "數據不足，至少需要 20 根 K 線",
                "risk_level": "unknown",
            }

        # ── 收益率 ──────────────────────────────────────────────────────
        if len(prices) >= 2:
            returns = np.diff(prices) / prices[:-1]
        else:
            returns = np.array([])

        # ── 風險指標 ─────────────────────────────────────────────────────
        volatility = calculate_volatility(returns.tolist())
        var_95 = calculate_var_historical(returns.tolist(), confidence=0.95, portfolio_value=capital)
        var_99 = calculate_var_historical(returns.tolist(), confidence=0.99, portfolio_value=capital)
        var_param_95 = calculate_var_parametric(returns.tolist(), confidence=0.95, portfolio_value=capital)
        var_cf_95 = calculate_var_cornish_fisher(returns.tolist(), confidence=0.95, portfolio_value=capital)
        cvar_95 = calculate_cvar(returns.tolist(), confidence=0.95, portfolio_value=capital)
        sharpe = calculate_sharpe_ratio(returns.tolist())
        sortino = calculate_sortino_ratio(returns.tolist())
        max_dd, dd_start, dd_end = calculate_max_drawdown(prices.tolist())
        calmar = calculate_calmar_ratio(returns.tolist(), prices.tolist())

        # ── 止損 ──────────────────────────────────────────────────────
        stop = calculate_stop_loss(
            entry_price=entry_price,
            position_type=position_type,
            closes=closes,
            highs=highs,
            lows=lows,
        )

        # ── 倉位 ──────────────────────────────────────────────────────
        atr_val = None
        if highs is not None and lows is not None:
            tr = []
            for i in range(1, len(closes)):
                hl = highs[i] - lows[i]
                hc = abs(highs[i] - closes[i - 1])
                lc = abs(lows[i] - closes[i - 1])
                tr.append(max(hl, hc, lc))
            atr_val = np.mean(tr[-14:]) if len(tr) >= 14 else np.mean(tr)

        if atr_val and atr_val > 0:
            position = PositionSizer.atr_based(
                entry_price=entry_price,
                atr=float(atr_val),
                capital=capital,
                risk_pct=0.01,
            )
        else:
            position = PositionSizer.fixed_risk(
                entry_price=entry_price,
                stop_price=stop.stop_price,
                capital=capital,
                risk_pct=0.02,
            )

        # ── 風險評級 ──────────────────────────────────────────────────
        risk_level = assess_risk_level(
            var_pct=var_95 / capital,
            volatility=volatility,
            drawdown=max_dd,
        )

        # ── 構建報告 ────────────────────────────────────────────────────
        var_pct_val = var_95 / capital * 100

        return {
            "timestamp": np.datetime64("now").astype(str),
            "risk_level": risk_level.value,
            "metrics": {
                "volatility_annual": round(volatility, 4),
                "var_95": round(var_95, 2),
                "var_99": round(var_99, 2),
                "var_param_95": round(var_param_95, 2),
                "var_cornish_fisher_95": round(var_cf_95, 2),
                "cvar_95": round(cvar_95, 2),
                "sharpe_ratio": round(sharpe, 3),
                "sortino_ratio": round(sortino, 3),
                "max_drawdown": round(max_dd, 4),
                "calmar_ratio": round(calmar, 3),
            },
            "var_breakdown": {
                "var_95_pct": round(var_pct_val, 2),
                "interpretation": f"在 95% 信心下，每日最大損失不超過 {var_pct_val:.2f}%（{var_95:.0f} 元）",
            },
            "stop_loss": {
                "stop_price": stop.stop_price,
                "strategy": stop.strategy.value,
                "atr": stop.atr_or_volatility,
                "risk_amount": stop.risk_amount,
                "risk_pct": stop.risk_pct,
            },
            "position": {
                "recommended_size": position.size,
                "units": position.units,
                "risk_per_unit": position.risk_per_unit,
                "total_risk": position.total_risk,
                "method": position.method,
            },
            "summary": self._generate_summary(
                risk_level, var_pct_val, max_dd, sharpe, stop.risk_pct
            ),
        }

    def _generate_summary(
        self,
        risk_level: RiskLevel,
        var_pct: float,
        max_dd: float,
        sharpe: float,
        stop_risk_pct: float,
    ) -> str:
        parts = []
        parts.append(f"風險等級：{risk_level.value.replace('_', ' ').upper()}")
        parts.append(f"日 VaR（95%）：{var_pct:.2f}%")
        parts.append(f"最大回撤：{max_dd * 100:.2f}%")
        parts.append(f"夏普比率：{sharpe:.2f}")
        parts.append(f"建議止損幅度：{stop_risk_pct * 100:.2f}%")
        return " | ".join(parts)
