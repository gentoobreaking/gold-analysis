"""
Notification Service - 通知渠道管理
支援郵件、推送通知
"""
import logging
import json
from typing import Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.services.alert_service import AlertService

logger = logging.getLogger(__name__)


class NotificationChannel(str):
    """通知渠道常量"""
    EMAIL = "email"
    PUSH = "push"
    WEBHOOK = "webhook"


class NotificationService:
    """通知服務"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.alert_service = AlertService(session)

    # ── 通知構建 ─────────────────────────────────────────────────────────────

    def build_alert_message(self, alert: Alert) -> dict:
        """構建告警通知內容"""
        return {
            "title": self._get_title(alert),
            "body": self._get_body(alert),
            "data": {
                "alert_id": alert.id,
                "alert_type": alert.alert_type.value,
                "asset": alert.asset,
                "target_price": alert.target_price,
                "triggered_at": datetime.utcnow().isoformat(),
            },
        }

    def _get_title(self, alert: Alert) -> str:
        """生成通知標題"""
        type_labels = {
            "price_above": "📈 價格突破上行",
            "price_below": "📉 價格跌破下行",
            "indicator_cross": "📊 指標交叉提醒",
            "volume_spike": "📢 信號提醒",
        }
        label = type_labels.get(alert.alert_type.value, "🔔 告警提醒")
        return f"{label} — {alert.asset}"

    def _get_body(self, alert: Alert) -> str:
        """生成通知正文"""
        if alert.alert_type.value in ("price_above", "price_below"):
            direction = "突破" if alert.alert_type.value == "price_above" else "跌破"
            return (
                f"{alert.asset} 已{direction} {alert.target_price} 美元\n"
                f"時間: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        elif alert.alert_type.value == "indicator_cross":
            return (
                f"{alert.asset} 指標觸發條件\n"
                f"目標值: {alert.target_price}\n"
                f"詳情: {alert.extra_data or '指標交叉'}"
            )
        elif alert.alert_type.value == "volume_spike":
            return (
                f"{alert.asset} 信號監控觸發\n"
                f"強度: {alert.target_price:.2f}\n"
                f"信號: {alert.extra_data or '監控中'}"
            )
        return f"{alert.asset} 告警已觸發"

    # ── 郵件通知 ─────────────────────────────────────────────────────────────

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html: Optional[str] = None,
    ) -> bool:
        """
        發送郵件通知（需配置 SMTP）

        目前為存根實現，返回 True。
        實際部署時替換為真實 SMTP 發送（如 FastAPI mailtrap 或 SendGrid）。
        """
        try:
            # TODO: 替換為真實 SMTP 實現
            logger.info(
                f"[EMAIL STUB] To: {to_email} | Subject: {subject} | Body: {body[:80]}"
            )
            # 示例 SMTP:
            # from app.services.config import get_api_settings
            # settings = get_api_settings()
            # async with aiosmtplib.SMTP(...) as smtp:
            #     await smtp.send_message(MIMEText(body, "plain"))
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def notify_alert_by_email(
        self,
        alert: Alert,
        user_email: str,
    ) -> bool:
        """發送告警郵件通知"""
        message = self.build_alert_message(alert)
        return await self.send_email(
            to_email=user_email,
            subject=message["title"],
            body=message["body"],
        )

    # ── 推送通知 ─────────────────────────────────────────────────────────────

    async def send_push(
        self,
        user_id: int,
        title: str,
        body: str,
        data: Optional[dict] = None,
    ) -> bool:
        """
        發送 Web Push 通知（需配置 Web Push VAPID 金鑰）

        目前為存根實現，返回 True。
        """
        try:
            logger.info(f"[PUSH STUB] user={user_id} | title={title}")
            # TODO: 替換為真實 Web Push 實現
            # 需配置 app/services/config.py 中的 vapid_keys
            return True
        except Exception as e:
            logger.error(f"Failed to send push notification: {e}")
            return False

    async def notify_alert_by_push(
        self,
        alert: Alert,
        user_id: int,
    ) -> bool:
        """發送告警推送通知"""
        message = self.build_alert_message(alert)
        return await self.send_push(
            user_id=user_id,
            title=message["title"],
            body=message["body"],
            data=message["data"],
        )

    # ── Webhook ─────────────────────────────────────────────────────────────

    async def send_webhook(
        self,
        webhook_url: str,
        payload: dict,
        headers: Optional[dict] = None,
    ) -> bool:
        """
        發送 Webhook 通知

        目前為存根實現。
        """
        try:
            logger.info(f"[WEBHOOK STUB] url={webhook_url} payload={json.dumps(payload)[:100]}")
            # TODO: 替換為真實 HTTP 請求
            # import httpx
            # async with httpx.AsyncClient() as client:
            #     r = await client.post(webhook_url, json=payload, headers=headers)
            #     r.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False

    # ── 整合告警通知 ─────────────────────────────────────────────────────────

    async def process_alert_notifications(
        self,
        user_id: int,
        user_email: str,
        webhook_url: Optional[str] = None,
        enable_email: bool = True,
        enable_push: bool = True,
        enable_webhook: bool = True,
    ) -> dict:
        """
        處理用戶所有待觸發告警的通知

        調用 check_all_alerts 然後按配置渠道發送通知。
        """
        # 查詢未處理的告警
        alerts = await self.alert_service.list_alerts(user_id, active_only=True)

        results: dict[str, list[dict]] = {
            "email": [],
            "push": [],
            "webhook": [],
        }

        for alert in alerts:
            message = self.build_alert_message(alert)

            # 郵件
            if enable_email and user_email:
                sent = await self.notify_alert_by_email(alert, user_email)
                results["email"].append({"alert_id": alert.id, "sent": sent})

            # 推送
            if enable_push:
                sent = await self.notify_alert_by_push(alert, user_id)
                results["push"].append({"alert_id": alert.id, "sent": sent})

            # Webhook
            if enable_webhook and webhook_url:
                sent = await self.send_webhook(webhook_url, message)
                results["webhook"].append({"alert_id": alert.id, "sent": sent})

        return results
