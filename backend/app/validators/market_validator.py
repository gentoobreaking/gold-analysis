# backend/app/validators/market_validator.py


class MarketValidator:
    """市場數據驗證器"""

    def __init__(self):
        self.dxy_range = (80, 120)  # DXY 合理範圍
        self.rate_range = (0, 25)   # 利率合理範圍（%）

    def validate_dxy(self, value: float) -> bool:
        """DXY 範圍驗證"""
        if value is None:
            return False
        return self.dxy_range[0] <= value <= self.dxy_range[1]

    def validate_rate(self, rate: float) -> bool:
        """利率驗證"""
        if rate is None:
            return False
        return self.rate_range[0] <= rate <= self.rate_range[1]

    def validate_volume(self, volume: float) -> bool:
        """成交量驗證"""
        if volume is None:
            return False
        return volume >= 0

    def validate(self, data: dict) -> dict:
        """綜合驗證"""
        return {
            "dxy_valid": self.validate_dxy(data.get("dxy")),
            "rate_valid": self.validate_rate(data.get("rate")),
            "volume_valid": self.validate_volume(data.get("volume")),
            "is_valid": all(
                [
                    self.validate_dxy(data.get("dxy")),
                    self.validate_rate(data.get("rate")),
                ]
            ),
        }
