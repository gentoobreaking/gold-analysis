"""Trading execution wiring.

Routes a structured :class:`Decision` (from ``app.ml.model_integration``) through
core's :class:`OrderExecutor` and appends the outcome to the :class:`TradeLogger`.
Reuses core's existing executor and exchange client -- no advanced-only code path.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .order_executor import OrderExecutor
from .order_types import OrderSide, OrderType
from .trade_logger import TradeLogger


def execute_decision(
    decision: Any,
    symbol: str = "XAUUSD",
    client: Any = None,
    logger: Optional[TradeLogger] = None,
    quantity: float = 1.0,
) -> Dict[str, Any]:
    """Execute ``decision`` via core's OrderExecutor; log the result.

    ``client`` is any object exposing the ExchangeClient surface (e.g.
    ``ExchangeClient(use_mock=True)`` or ``RestExchangeClient(...)``). If ``None``,
    a mock client is used so the call is always safe/testable.
    """
    if getattr(decision, "action", "HOLD") == "HOLD":
        return {"executed": False, "reason": "hold"}

    side = OrderSide.BUY if decision.action == "BUY" else OrderSide.SELL
    executor = OrderExecutor(client=client) if client is not None else OrderExecutor(use_mock=True)
    resp = executor.execute(symbol, side.value, quantity, order_type="market")

    event: Dict[str, Any] = {
        "symbol": symbol,
        "action": decision.action,
        "side": side.value,
        "quantity": quantity,
        "success": resp.success,
        "error_message": resp.error_message,
        "model_version": getattr(decision, "model_version", None),
    }
    if logger is not None:
        logger.log(event)

    return {"executed": True, "success": resp.success, "response": resp, "event": event}
