"""
Webhook signal ingest route (T067)

Accepts TradingView / generic JSON webhooks with HMAC-SHA256 signature
verification. Maps external signals to internal DecisionSignal / Decision
structures and routes them through the decision flow with source=external.
External signals are governed by the T055 kill-switch: when trading is
disabled or in dry-run, signals are recorded but no real orders are submitted.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone

from app.api.schemas.webhooks import WebhookResponse, WebhookSignal
from app.core.config import get_core_settings
from fastapi import APIRouter, Header, HTTPException, Request, status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _compute_signature(body: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 hex signature for the request body."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature using constant-time comparison."""
    expected = _compute_signature(body, secret)
    return hmac.compare_digest(expected, signature)


def _map_to_decision(signal: WebhookSignal) -> dict:
    """Map external WebhookSignal to internal Decision dict structure."""
    action_map = {
        "buy": "buy",
        "sell": "sell",
        "hold": "hold",
        "watch": "watch",
    }
    return {
        "decision_type": action_map.get(signal.action.value, "hold"),
        "source": "external",
        "asset": signal.symbol.upper(),
        "signal_strength": signal.confidence,
        "confidence": signal.confidence,
        "price_target": signal.price,
        "stop_loss": None,
        "reason_zh": signal.signal,
        "reason_en": "; ".join(signal.reason) if signal.reason else signal.signal,
        "timestamp": signal.timestamp or datetime.now(timezone.utc).isoformat(),
        "is_executed": False,
    }


async def _store_external_decision(decision_data: dict) -> int | None:
    """Store external decision signal. Returns decision ID if DB available."""
    try:
        from app.db.config import get_db_session
        from app.models.decision import Decision, DecisionSource, DecisionType

        async for db in get_db_session():
            decision = Decision(
                user_id=1,  # System user for external signals
                decision_type=DecisionType[decision_data["decision_type"].upper()],
                source=DecisionSource.EXTERNAL,
                asset=decision_data["asset"],
                signal_strength=decision_data["signal_strength"],
                confidence=decision_data["confidence"],
                price_target=decision_data["price_target"],
                reason_en=decision_data["reason_en"],
                indicators_snapshot=decision_data["timestamp"],
                is_executed=False,
            )
            db.add(decision)
            await db.commit()
            await db.refresh(decision)
            return decision.id
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not store external decision in DB: %s", e)
        return None


@router.post("/signal", response_model=WebhookResponse)
async def receive_webhook_signal(
    request: Request,
    webhook_signal: WebhookSignal,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    x_webhook_signature: str | None = Header(None, alias="X-Webhook-Signature"),
) -> WebhookResponse:
    """Receive external signal via webhook (TradingViewer compatible).

    HMAC verification:
    - Header ``X-Hub-Signature-256``: ``sha256=<hex-digest>``
    - Header ``X-Webhook-Signature``: raw ``<hex-digest>``

    The secret is read from ``CORE_WEBHOOK_SECRET`` env var (via CoreSettings).
    When no secret is configured, HMAC verification is skipped (dev mode) but
    a warning is logged.

    T055 kill-switch:
    - ``trading_enabled=False``: signal accepted & recorded, no execution
    - ``trading_dry_run=True``: signal accepted & simulated, no real order
    - ``trading_enabled=True`` + ``trading_dry_run=False``: signal accepted
      and may proceed to real order execution via ``trading.execution``
    """
    body = await request.body()
    s = get_core_settings()

    secret = getattr(s, "webhook_secret", None)
    if secret:
        sig = x_hub_signature_256 or x_webhook_signature
        if not sig:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing signature header",
            )
        # Normalize: strip "sha256=" prefix if present
        sig_value = sig.replace("sha256=", "", 1) if sig.startswith("sha256=") else sig
        if not _verify_signature(body, sig_value, secret):
            logger.warning("Webhook HMAC verification failed for %s", request.url.path)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )
    else:
        logger.warning(
            "Webhook received without HMAC secret configured (dev mode); "
            "accepting without verification"
        )

    # Map external signal to internal Decision structure
    decision_data = _map_to_decision(webhook_signal)

    # Determine action based on T055 kill-switch state
    trading_enabled = getattr(s, "trading_enabled", False)
    trading_dry_run = getattr(s, "trading_dry_run", True)

    if not trading_enabled or trading_dry_run:
        action_taken = "simulated"
        logger.info(
            "External webhook signal accepted (source=external, simulated): %s %s",
            webhook_signal.action.value,
            webhook_signal.symbol,
        )
    else:
        action_taken = "accepted"
        logger.info(
            "External webhook signal accepted (source=external, live): %s %s -> routing to execution",
            webhook_signal.action.value,
            webhook_signal.symbol,
        )

    # Record the decision (store in DB if available, otherwise log)
    decision_id = await _store_external_decision(decision_data)

    return WebhookResponse(
        accepted=True,
        decision_id=decision_id,
        action_taken=action_taken,
        source="external",
        message=f"Signal accepted; trading_enabled={trading_enabled}, dry_run={trading_dry_run}",
    )
