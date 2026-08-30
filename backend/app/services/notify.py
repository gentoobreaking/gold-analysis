"""
Standalone notifier — env-configured, no DB session required (T056).

Used by the model monitor (drift/health anomalies) and the trading risk
breaker (T055/T056) to push alerts via Email / Webhook (Telegram/Discord/Slack
compatible). All channels degrade gracefully to a log when not configured.
"""

from __future__ import annotations

import json
import logging
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage
from typing import Any

from app.core.config import get_core_settings

logger = logging.getLogger(__name__)


def _email_transport(to: str, subject: str, body: str) -> bool:
    s = get_core_settings()
    if not (s.smtp_host and s.smtp_from and to):
        logger.debug("[notify] email not configured; skipping")
        return False
    try:
        msg = EmailMessage()
        msg["From"] = s.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(s.smtp_host, s.smtp_port) as server:
            if s.smtp_user and s.smtp_pass:
                server.starttls(context=ssl.create_default_context())
                server.login(s.smtp_user, s.smtp_pass)
            server.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001
        logger.error("[notify] email send failed: %s", e)
        return False


def _webhook_transport(url: str, payload: dict[str, Any]) -> bool:
    if not url:
        logger.debug("[notify] webhook not configured; skipping")
        return False
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception as e:  # noqa: BLE001
        logger.error("[notify] webhook send failed: %s", e)
        return False


def notify_alert(
    alert: dict[str, Any],
    channels: list[str] | None = None,
) -> dict[str, bool]:
    """Send an alert dict via configured channels.

    alert keys: title, body, level (optional), source (optional)
    Returns a per-channel success map. No-op (returns {}) when notifications
    are disabled or no channel is configured.
    """
    s = get_core_settings()
    if not getattr(s, "notify_enabled", False):
        return {}
    channels = channels or ["webhook", "email"]
    title = alert.get("title", "Gold Analysis Alert")
    body = alert.get("body", "")
    results: dict[str, bool] = {}
    if "email" in channels and s.notify_email_to:
        results["email"] = _email_transport(s.notify_email_to, title, body)
    if "webhook" in channels and s.notify_webhook_url:
        results["webhook"] = _webhook_transport(s.notify_webhook_url, alert)
    return results
