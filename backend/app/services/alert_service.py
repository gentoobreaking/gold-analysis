"""
Alert Service - 告警規則引擎
支援價格告警、指標告警、信號告警
"""
import logging
from typing import Optional
from datetime import datetime, timedelta
from enum import Enum

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertType

logger = logging.getLogger(__name__)


class AlertStatus(str, Enum):
    """告警觸發狀態"""
    PENDING = "pending"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AlertService:
    """告警服務"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── CRUD ────────────────────────────────────────────────────────────────

    async def create_alert(
        self,
        user_id: int,
        alert_type: AlertType,
        asset: str,
        target_price: float,
        extra_data: Optional[str] = None,
    ) -> Alert:
        """創建告警"""
        alert = Alert(
            user_id=user_id,
            alert_type=alert_type,
            asset=asset,
            target_price=target_price,
            is_active=True,
            extra_data=extra_data,
        )
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        logger.info(
            f"Created alert {alert.id}: {alert.alert_type.value} {alert.asset} @ {target_price}"
        )
        return alert

    async def get_alert(self, alert_id: int) -> Optional[Alert]:
        stmt = select(Alert).where(Alert.id == alert_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_alerts(self, user_id: int, active_only: bool = True) -> list[Alert]:
        """列出用戶告警"""
        stmt = select(Alert).where(Alert.user_id == user_id)
        if active_only:
            stmt = stmt.where(Alert.is_active == True)  # noqa: E712
        stmt = stmt.order_by(Alert.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def deactivate_alert(self, alert_id: int, user_id: int) -> bool:
        """停用告警"""
        stmt = update(Alert).where(
            Alert.id == alert_id, Alert.user_id == user_id
        ).values(is_active=False)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def delete_alert(self, alert_id: int, user_id: int) -> bool:
        """刪除告警"""
        stmt = delete(Alert).where(Alert.id == alert_id, Alert.user_id == user_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    # ── 規則引擎 ─────────────────────────────────────────────────────────────

    async def check_price_alerts(
        self,
        user_id: int,
        asset: str,
        current_price: float,
    ) -> list[Alert]:
        """
        檢查價格告警是否觸發

        Args:
            user_id: 用戶ID
            asset: 資產代碼（如 GOLD、DXY）
            current_price: 當前價格

        Returns:
            已觸發的告警列表
        """
        triggered: list[Alert] = []

        # 查詢該用戶、該資產的有效告警
        stmt = select(Alert).where(
            Alert.user_id == user_id,
            Alert.asset == asset,
            Alert.is_active == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        alerts = result.scalars().all()

        for alert in alerts:
            if self._is_price_triggered(alert, current_price):
                alert.is_active = False
                alert.triggered_at = datetime.utcnow()
                triggered.append(alert)
                logger.info(
                    f"Alert {alert.id} triggered: {asset} price {current_price} "
                    f"crossed {alert.target_price} ({alert.alert_type.value})"
                )

        if triggered:
            await self.session.commit()

        return triggered

    def _is_price_triggered(self, alert: Alert, current_price: float) -> bool:
        """判斷價格告警是否觸發"""
        if alert.alert_type == AlertType.PRICE_ABOVE:
            return current_price >= alert.target_price
        elif alert.alert_type == AlertType.PRICE_BELOW:
            return current_price <= alert.target_price
        return False

    async def check_indicator_alerts(
        self,
        user_id: int,
        asset: str,
        indicator_value: float,
        indicator_name: str,
        direction: str = "above",
        threshold: float = 0.0,
    ) -> list[Alert]:
        """
        檢查指標告警是否觸發

        Args:
            indicator_value: 指標當前值（如 RSI、MACD）
            indicator_name: 指標名稱
            direction: 觸發方向 "above" | "below"
            threshold: 閾值

        Returns:
            已觸發的告警列表
        """
        triggered: list[Alert] = []

        stmt = select(Alert).where(
            Alert.user_id == user_id,
            Alert.asset == asset,
            Alert.alert_type == AlertType.INDICATOR_CROSS,
            Alert.is_active == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        alerts = result.scalars().all()

        for alert in alerts:
            if direction == "above" and indicator_value >= threshold:
                if self._matches_indicator_filter(alert, indicator_name, direction):
                    alert.is_active = False
                    alert.triggered_at = datetime.utcnow()
                    triggered.append(alert)
            elif direction == "below" and indicator_value <= threshold:
                if self._matches_indicator_filter(alert, indicator_name, direction):
                    alert.is_active = False
                    alert.triggered_at = datetime.utcnow()
                    triggered.append(alert)

        if triggered:
            await self.session.commit()

        return triggered

    def _matches_indicator_filter(
        self, alert: Alert, indicator_name: str, direction: str
    ) -> bool:
        """匹配指標過濾條件"""
        if not alert.extra_data:
            return True
        # extra_data 格式: "indicator=RSI,direction=above,threshold=70"
        parts = dict(p.split("=") for p in alert.extra_data.split(",") if "=" in p)
        return parts.get("indicator", indicator_name) == indicator_name

    async def check_signal_alerts(
        self,
        user_id: int,
        asset: str,
        new_signal: str,
        signal_strength: float,
    ) -> list[Alert]:
        """
        檢查信號告警是否觸發

        Args:
            new_signal: 新信號 (buy/sell/hold/watch)
            signal_strength: 信號強度 0.0-1.0

        Returns:
            已觸發的告警列表
        """
        triggered: list[Alert] = []

        stmt = select(Alert).where(
            Alert.user_id == user_id,
            Alert.asset == asset,
            Alert.alert_type == AlertType.VOLUME_SPIKE,  # 用 VOLUME_SPIKE 代替信號告警
            Alert.is_active == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        alerts = result.scalars().all()

        for alert in alerts:
            if alert.extra_data and new_signal in alert.extra_data:
                if signal_strength >= alert.target_price:  # target_price 存放信號強度閾值
                    alert.is_active = False
                    alert.triggered_at = datetime.utcnow()
                    triggered.append(alert)

        if triggered:
            await self.session.commit()

        return triggered

    # ── 批量處理 ─────────────────────────────────────────────────────────────

    async def check_all_alerts(
        self,
        user_id: int,
        price_data: dict[str, float],
        indicator_data: Optional[dict] = None,
        signal_data: Optional[dict] = None,
    ) -> dict[str, list[Alert]]:
        """
        批量檢查所有告警

        Args:
            price_data: { "GOLD": 2000.0, "DXY": 104.5, ... }
            indicator_data: { "RSI": 70, "MACD": 0.5, ... }
            signal_data: { "signal": "buy", "strength": 0.85 }

        Returns:
            { "price": [...], "indicator": [...], "signal": [...] }
        """
        results: dict[str, list[Alert]] = {
            "price": [],
            "indicator": [],
            "signal": [],
        }

        # 價格告警
        for asset, price in price_data.items():
            triggered = await self.check_price_alerts(user_id, asset, price)
            results["price"].extend(triggered)

        # 指標告警
        if indicator_data:
            for asset, price in price_data.items():
                for ind_name, ind_val in indicator_data.items():
                    if isinstance(ind_val, (int, float)):
                        direction = "above" if ind_val > 50 else "below"
                        triggered = await self.check_indicator_alerts(
                            user_id, asset, ind_val, ind_name, direction, 50
                        )
                        results["indicator"].extend(triggered)

        # 信號告警
        if signal_data:
            for asset, price in price_data.items():
                triggered = await self.check_signal_alerts(
                    user_id,
                    asset,
                    signal_data.get("signal", ""),
                    signal_data.get("strength", 0.0),
                )
                results["signal"].extend(triggered)

        return results

    # ── 統計 ────────────────────────────────────────────────────────────────

    async def get_alert_stats(self, user_id: int) -> dict:
        """取得告警統計"""
        stmt = select(Alert).where(Alert.user_id == user_id)
        result = await self.session.execute(stmt)
        alerts = result.scalars().all()

        total = len(alerts)
        active = sum(1 for a in alerts if a.is_active)
        triggered = sum(1 for a in alerts if a.triggered_at is not None)

        by_type: dict[str, int] = {}
        for a in alerts:
            by_type[a.alert_type.value] = by_type.get(a.alert_type.value, 0) + 1

        return {
            "total": total,
            "active": active,
            "triggered": triggered,
            "by_type": by_type,
        }
