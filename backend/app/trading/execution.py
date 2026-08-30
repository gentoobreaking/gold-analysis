"""Trading execution wiring.

Routes a structured :class:`Decision` (from ``app.ml.model_integration``) through
core's :class:`OrderExecutor`, applies the global trading kill-switch (T055) and a
pre-trade risk gate, then appends the outcome to the :class:`TradeLogger`.
Reuses core's existing executor and exchange client -- no advanced-only code path.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_core_settings

from .order_executor import OrderExecutor
from .order_types import OrderSide
from .risk_rules import RiskRuleEngine
from .trade_logger import TradeLogger


def _pre_trade_risk_check(
    symbol: str,
    side: str,
    quantity: float,
    price: float | None,
    account: Any,
) -> dict[str, Any]:
    """Run circuit-breaker rules; return pass/fail summary for the pre-trade gate."""
    engine = RiskRuleEngine()
    passed, results = engine.check(
        order_side=side,
        symbol=symbol,
        quantity=quantity,
        price=price or 0.0,
        account=account,
    )
    return {"passed": passed, "summary": engine.get_summary(results), "results": results}


def execute_decision(
    decision: Any,
    symbol: str = "XAUUSD",
    client: Any = None,
    logger: TradeLogger | None = None,
    quantity: float = 1.0,
    price: float | None = None,
    account: Any = None,
) -> dict[str, Any]:
    """Execute ``decision`` via core's OrderExecutor; log the result.

    Safety (T055):
      1. Master kill-switch -- if ``trading_enabled`` is not True, the order is
         NEVER submitted. To go live you must explicitly set ``trading_enabled=True``
         AND ``trading_dry_run=False`` (explicit double confirmation); otherwise
         orders are simulated/logged only.
      2. Pre-trade risk gate -- circuit breakers (daily-loss, frequency, ...) run
         before any submission; a BLOCK aborts the order.
    """
    if getattr(decision, "action", "HOLD") == "HOLD":
        return {"executed": False, "reason": "hold"}

    side = OrderSide.BUY if decision.action == "BUY" else OrderSide.SELL
    action = decision.action

    # 1. Master kill-switch
    settings = get_core_settings()
    if not settings.trading_enabled:
        event = {
            "symbol": symbol,
            "action": action,
            "side": side.value,
            "quantity": quantity,
            "executed": False,
            "reason": "trading_disabled",
            "simulated": True,
            "message": "TRADING_ENABLED=False: order NOT submitted (kill-switch active)",
        }
        if logger is not None:
            logger.log(event)
        return event

    if settings.trading_dry_run:
        event = {
            "symbol": symbol,
            "action": action,
            "side": side.value,
            "quantity": quantity,
            "executed": False,
            "reason": "dry_run",
            "simulated": True,
            "message": "TRADING_DRY_RUN=True: order simulated, not submitted",
        }
        if logger is not None:
            logger.log(event)
        return event

    # 2. Pre-trade risk gate (circuit breakers)
    risk = _pre_trade_risk_check(symbol, side.value, quantity, price, account)
    if not risk["passed"]:
        event = {
            "symbol": symbol,
            "action": action,
            "side": side.value,
            "quantity": quantity,
            "executed": False,
            "reason": "risk_blocked",
            "simulated": True,
            "blocked_rules": risk["summary"]["blocked_rules"],
        }
        if logger is not None:
            logger.log(event)
        try:
            from app.services.notify import notify_alert

            notify_alert(
                {
                    "title": f"[RISK BLOCK] {symbol} {action}",
                    "body": f"Pre-trade risk gate blocked order: {risk['summary']['blocked_rules']}",
                    "level": "critical",
                    "source": "execution",
                }
            )
        except Exception:  # noqa: BLE001,S110
            pass
        return event

    # 3. Submit real order
    executor = OrderExecutor(client=client) if client is not None else OrderExecutor(use_mock=True)
    resp = executor.execute(symbol, side.value, quantity, order_type="market", price=price)

    event = {
        "symbol": symbol,
        "action": action,
        "side": side.value,
        "quantity": quantity,
        "executed": True,
        "success": resp.success,
        "error_message": resp.error_message,
        "model_version": getattr(decision, "model_version", None),
    }
    if logger is not None:
        logger.log(event)

    return {"executed": True, "success": resp.success, "response": resp, "event": event}
