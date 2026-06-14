# backend/tests/test_validators.py

import pytest
from datetime import datetime, timedelta, timezone

from app.validators import PriceValidator, MarketValidator


class TestPriceValidator:
    def test_validate_price_valid(self):
        validator = PriceValidator()
        assert validator.validate_price(4792.0) is True

    def test_validate_price_invalid(self):
        validator = PriceValidator()
        assert validator.validate_price(-100) is False
        assert validator.validate_price(0) is False
        assert validator.validate_price(None) is False

    def test_validate_timestamp_valid(self):
        validator = PriceValidator()
        now = datetime.now(timezone.utc)
        assert validator.validate_timestamp(now) is True

    def test_validate_timestamp_future(self):
        validator = PriceValidator()
        future = datetime.now(timezone.utc) + timedelta(days=1)
        assert validator.validate_timestamp(future) is False


class TestMarketValidator:
    def test_validate_dxy_valid(self):
        validator = MarketValidator()
        assert validator.validate_dxy(100.0) is True

    def test_validate_dxy_invalid(self):
        validator = MarketValidator()
        assert validator.validate_dxy(50.0) is False

    def test_validate_rate_valid(self):
        validator = MarketValidator()
        assert validator.validate_rate(5.0) is True
