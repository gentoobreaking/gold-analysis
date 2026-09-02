"""
資料新鮮度 SLA 監控 (T066)。

監控各資料來源的最後更新時間；超過 SLA 閾值標記 stale 並透過 T056 通知通道告警，
避免模型/決策在陳舊資料上靜默運作（補強 T054 真實資料健康度）。

設計要點：
- 來源註冊表含 SLA 閾值（價格來源 core.daily_prices ≤ 2 天、market_sentiment ≤ 1 天）。
- 區分三種狀態：fresh / stale（真實資料過期，告警）/ unavailable（來源不可用，不視為 stale 告警）。
- mock 模式下（sentiment 來源標記 source='mock'）因時間戳為即時合成值，不告警，僅標註 is_mock。
- 同一來源連續 stale 時做簡易節流（每 source 僅於狀態首次進入 stale 或每 alert_cooldown 秒後再報）。
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import get_core_settings
from app.db.config import get_db_session
from app.tools.data_tools import DataTools

logger = logging.getLogger(__name__)

ALERT_COOLDOWN_S = 3600  # 同一來源最多每小時告警一次


@dataclass
class SourceStatus:
    name: str
    sla_seconds: int
    last_update: str | None = None  # ISO 字串；None = 無資料
    age_seconds: float | None = None
    status: str = "unavailable"  # fresh | stale | unavailable
    is_mock: bool = False
    detail: str = ""


def _parse_ts(value: str) -> datetime | None:
    """寬容解析日期/時間字串為 UTC datetime。失敗回 None。"""
    if not value:
        return None
    try:
        s = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        # 嘗試單純日期 YYYY-MM-DD
        try:
            dt = datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None


async def _price_fetcher() -> tuple[str | None, bool]:
    """core.daily_prices 最後更新：PostgreSQL MAX(trade_date)；真實資料。"""
    from sqlalchemy import select, func
    from app.models.daily_price import DailyPrice
    async for session in get_db_session():
        try:
            result = await session.execute(
                select(func.max(DailyPrice.trade_date)).where(DailyPrice.symbol == "GOLD")
            )
            max_date = result.scalar()
            if max_date is not None:
                return max_date.isoformat(), False
            return None, False
        except Exception as e:
            logger.warning("daily_prices freshness check failed: %s", e)
            return None, False
    return None, False


async def _sentiment_fetcher() -> tuple[str | None, bool]:
    """市場情緒最後更新：get_sentiment_data().timestamp；不可用時標 unavailable。"""
    try:
        tools = DataTools()
        data = await tools.get_sentiment_data()
    except Exception as e:
        logger.warning("sentiment freshness check failed: %s", e)
        return None, False
    if not data.get("available"):
        return None, False
    return data.get("timestamp"), (data.get("source") == "mock")


class DataFreshnessMonitor:
    """資料新鮮度監控器。"""

    def __init__(self) -> None:
        self._sources: dict[str, dict] = {
            "daily_prices": {
                "sla_seconds": 2 * 24 * 60 * 60,  # GOLD 為日結資料，SLA 2 天
                "fetcher": _price_fetcher,
            },
            "market_sentiment": {
                "sla_seconds": 24 * 60 * 60,
                "fetcher": _sentiment_fetcher,
            },
        }
        self._last_alerted: dict[str, float] = {}

    def register(
        self, name: str, sla_seconds: int, fetcher: Callable[[], tuple[str | None, bool]]
    ) -> None:
        self._sources[name] = {"sla_seconds": sla_seconds, "fetcher": fetcher}

    async def _call_fetcher(self, fetcher: Callable[[], object]) -> tuple[str | None, bool]:
        """呼叫 fetcher；若為 coroutine 則 await，否則直接回傳。"""
        res = fetcher()
        if hasattr(res, "__await__"):
            return await res  # type: ignore[misc]
        return res  # type: ignore[return-value]

    async def check(self) -> list[SourceStatus]:
        """檢查所有來源，回傳狀態清單（不發送通知）。"""
        now = datetime.now(timezone.utc)
        results: list[SourceStatus] = []
        for name, cfg in self._sources.items():
            sla = cfg["sla_seconds"]
            last_update, is_mock = await self._call_fetcher(cfg["fetcher"])
            status = SourceStatus(
                name=name, sla_seconds=sla, last_update=last_update, is_mock=is_mock
            )
            if last_update is None:
                status.status = "unavailable"
                status.detail = "無最後更新時間（來源不可用或未取數）"
            else:
                ts = _parse_ts(last_update)
                if ts is None:
                    status.status = "unavailable"
                    status.detail = "時間戳解析失敗"
                elif is_mock:
                    status.status = "fresh"
                    status.detail = "mock 模式：時間戳為即時合成值，不計 SLA"
                else:
                    age = (now - ts).total_seconds()
                    status.age_seconds = age
                    if age <= sla:
                        status.status = "fresh"
                        status.detail = f"資料新鮮（{age:.0f}s / SLA {sla}s）"
                    else:
                        status.status = "stale"
                        status.detail = f"資料過期（{age:.0f}s > SLA {sla}s）"
            results.append(status)
        return results

    async def run_check_and_notify(self) -> list[SourceStatus]:
        """檢查並對進入 stale 的來源發送 T056 通知（含簡易節流）。"""
        results = await self.check()
        s = get_core_settings()
        notify_enabled = getattr(s, "notify_enabled", False)
        for st in results:
            if st.status != "stale":
                continue
            last = self._last_alerted.get(st.name, 0.0)
            if not notify_enabled or (time.time() - last) < ALERT_COOLDOWN_S:
                continue
            try:
                from app.services.notify import notify_alert

                notify_alert(
                    {
                        "title": f"資料新鮮度告警：{st.name}",
                        "body": f"{st.name} 資料過期（{st.detail}）。請檢查取數管線。",
                        "level": "warning",
                        "source": "data_freshness",
                    }
                )
                self._last_alerted[st.name] = time.time()
            except Exception as e:
                logger.error("freshness notify failed: %s", e)
        return results


# 預設單例（供路由/排程共用）
_default_monitor = DataFreshnessMonitor()


async def check_freshness() -> list[SourceStatus]:
    return await _default_monitor.check()


async def run_freshness_check() -> list[SourceStatus]:
    return await _default_monitor.run_check_and_notify()
