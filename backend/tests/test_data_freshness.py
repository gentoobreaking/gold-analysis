"""
T066 - 資料新鮮度 SLA 監控測試（註冊過期來源觸發 stale + 通知）
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.data_freshness import (
    DataFreshnessMonitor,
    _parse_ts,
)


def test_parse_ts_iso_and_date():
    dt = _parse_ts("2026-08-28T03:34:16+00:00")
    assert dt is not None and dt.year == 2026
    d2 = _parse_ts("2026-08-28")
    assert d2 is not None and d2.hour == 0
    assert _parse_ts("") is None
    assert _parse_ts("not-a-date") is None


def test_aged_source_marks_stale_and_notifies(monkeypatch):
    """註冊一個早就過期的來源 → stale + 通知被呼叫。"""
    notified = {}

    def fake_notify(alert, channels=None):
        notified[alert["source"]] = alert
        return {"webhook": True}

    # 必須先 import 模組，monkeypatch 才能正確 patch 屬性
    import app.services.notify

    monkeypatch.setattr(app.services.notify, "notify_alert", fake_notify)
    # run_check_and_notify 僅在 notify_enabled 時發送，測試環境需開啟
    from app.core.config import settings as _core_settings

    monkeypatch.setattr(_core_settings, "notify_enabled", True)

    mon = DataFreshnessMonitor()
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    mon.register(
        "fake_old",
        sla_seconds=60,  # 1 分鐘 SLA
        fetcher=lambda: (old_ts, False),
    )
    # 關閉節流：強制立即告警
    mon._last_alerted["fake_old"] = 0.0

    results = __import__("asyncio").run(mon.run_check_and_notify())
    st = next(s for s in results if s.name == "fake_old")
    assert st.status == "stale"
    assert st.age_seconds is not None and st.age_seconds > 60
    assert "data_freshness" in notified  # 通知已發送（source 為 data_freshness）


def test_mock_source_not_flagged_stale(monkeypatch):
    """mock 模式來源（時間戳為即時合成值）不應被標 stale 或告警。"""
    notified = {}

    def fake_notify(alert, channels=None):
        notified[alert["source"]] = alert
        return {}

    monkeypatch.setattr("app.services.notify.notify_alert", fake_notify)

    mon = DataFreshnessMonitor()
    now_iso = datetime.now(timezone.utc).isoformat()
    mon.register("mock_src", sla_seconds=60, fetcher=lambda: (now_iso, True))
    results = __import__("asyncio").run(mon.run_check_and_notify())
    st = next(s for s in results if s.name == "mock_src")
    assert st.status == "fresh"
    assert st.is_mock is True
    assert "mock_src" not in notified  # mock 不告警


def test_unavailable_source_no_stale_alarm(monkeypatch):
    """來源不可用（無 last_update）→ unavailable，不告警為 stale。"""
    notified = {}

    def fake_notify(alert, channels=None):
        notified[alert["source"]] = alert
        return {}

    monkeypatch.setattr("app.services.notify.notify_alert", fake_notify)

    mon = DataFreshnessMonitor()
    mon.register("down_src", sla_seconds=60, fetcher=lambda: (None, False))
    results = __import__("asyncio").run(mon.run_check_and_notify())
    st = next(s for s in results if s.name == "down_src")
    assert st.status == "unavailable"
    assert "down_src" not in notified


def test_fresh_within_sla(monkeypatch):
    mon = DataFreshnessMonitor()
    now_iso = datetime.now(timezone.utc).isoformat()
    mon.register("fresh_src", sla_seconds=3600, fetcher=lambda: (now_iso, False))
    results = __import__("asyncio").run(mon.run_check_and_notify())
    st = next(s for s in results if s.name == "fresh_src")
    assert st.status == "fresh"
