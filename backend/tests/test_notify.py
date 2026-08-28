"""
T056 - 通知通道測試（standalone notifier）

驗證 notify_alert：
- notify_enabled=False 時為 no-op
- webhook 通道實際發送（urllib 被 mock）
- email 通道在配置後實際發送（smtplib 被 mock）
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch

import app.core.config as config_mod
from app.core.config import CoreSettings
from app.services import notify


def _set(monkeypatch, **overrides):
    cfg = CoreSettings(**overrides)
    monkeypatch.setattr(config_mod, "get_core_settings", lambda: cfg)
    return cfg


def test_disabled_is_noop(monkeypatch):
    _set(monkeypatch, notify_enabled=False, notify_webhook_url="https://example.com/hook")
    with patch("app.services.notify._webhook_transport") as tr:
        result = notify.notify_alert({"title": "t", "body": "b"})
    assert result == {}
    tr.assert_not_called()


def test_webhook_sends_when_enabled(monkeypatch):
    _set(monkeypatch, notify_enabled=True, notify_webhook_url="https://example.com/hook")
    with patch("app.services.notify.urllib.request.urlopen") as urlopen:
        urlopen.return_value.__enter__.return_value.status = 200
        result = notify.notify_alert({"title": "t", "body": "b"})
    assert result.get("webhook") is True
    urlopen.assert_called_once()


def test_email_sends_when_configured(monkeypatch):
    _set(
        monkeypatch,
        notify_enabled=True,
        smtp_host="smtp.test",
        smtp_from="a@b.c",
        notify_email_to="u@b.c",
    )
    with patch("app.services.notify.smtplib.SMTP") as SMTP:
        result = notify.notify_alert({"title": "t", "body": "b"}, channels=["email"])
    assert result.get("email") is True
    SMTP.assert_called_once()
