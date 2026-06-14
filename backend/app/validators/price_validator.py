# backend/app/validators/price_validator.py

from datetime import datetime, timezone
from typing import Optional


class PriceValidator:
    """價格數據驗證器"""

    def __init__(self, max_daily_change: float = 0.05):
        self.max_daily_change = max_daily_change

    def validate_price(self, price: float) -> bool:
        """驗證價格合理性"""
        if price is None or price <= 0:
            return False
        return True

    def validate_timestamp(self, ts: datetime) -> bool:
        """驗證時間戳"""
        if ts is None:
            return False
        now = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts > now:
            return False  # 未來時間
        if (now - ts).days > 365:
            return False  # 超過1年
        return True

    def validate_price_change(self, old_price: float, new_price: float) -> bool:
        """驗證價格變動是否在合理範圍"""
        if old_price is None or old_price <= 0:
            return False
        if new_price is None or new_price <= 0:
            return False
        change = abs(new_price - old_price) / old_price
        return change <= self.max_daily_change

    def validate(self, data: dict) -> dict:
        """綜合驗證"""
        return {
            "price_valid": self.validate_price(data.get("price")),
            "timestamp_valid": self.validate_timestamp(data.get("timestamp")),
            "is_valid": (
                self.validate_price(data.get("price"))
                and self.validate_timestamp(data.get("timestamp"))
            ),
        }
