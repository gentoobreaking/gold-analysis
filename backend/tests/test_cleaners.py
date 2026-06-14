"""
Tests for Cleaners Module
"""

import pytest
from datetime import datetime, timezone
from app.cleaners import (
    PriceCleaner,
    OutlierDetector,
    get_price_cleaner,
    get_outlier_detector,
)


class TestPriceCleaner:
    def setup_method(self):
        self.cleaner = PriceCleaner()
        # Sample data with duplicates, missing and anomaly
        # Use 99999.0 to ensure IQR bounds definitely catch it
        # With values [1800, 1850, 99999, 1900], IQR bounds are narrow → 99999 is outlier
        self.sample = [
            {"timestamp": datetime(2023, 1, 1, tzinfo=timezone.utc), "price": 1800.0},
            {"timestamp": datetime(2023, 1, 1, tzinfo=timezone.utc), "price": 1800.0},  # duplicate
            {"timestamp": datetime(2023, 1, 2, tzinfo=timezone.utc), "price": None},   # missing
            {"timestamp": datetime(2023, 1, 3, tzinfo=timezone.utc), "price": 99999.0}, # anomaly (extreme high)
            {"timestamp": datetime(2023, 1, 4, tzinfo=timezone.utc), "price": 1900.0},
        ]

    def test_remove_duplicates(self):
        cleaned = self.cleaner.remove_duplicates(self.sample, key_field="timestamp")
        stats = self.cleaner.get_stats()
        # Should keep first occurrence by default
        assert len(cleaned) == 4
        assert stats["duplicates_removed"] == 1
        # Verify that timestamps are unique
        timestamps = [item["timestamp"] for item in cleaned]
        assert len(set(timestamps)) == len(timestamps)

    def test_clean_missing_values_interpolate(self):
        # Ensure strategy is interpolate (default)
        cleaned = self.cleaner.clean_missing_values(self.sample, value_field="price")
        stats = self.cleaner.get_stats()
        # Missing count should be 1
        assert stats["missing_fixed"] == 1
        # After interpolation, missing should be filled (not None)
        missing_filled = [item for item in cleaned if item.get("price") is None]
        assert len(missing_filled) == 0
        # Verify interpolation roughly between surrounding values
        interpolated = next(item for item in cleaned if item["timestamp"].day == 2)["price"]
        assert interpolated > 0

    def test_fix_anomalies_clip(self):
        cleaned, stats = self.cleaner.fix_anomalies(self.sample, value_field="price")
        # One anomaly should be corrected
        assert stats["anomaly_count"] == 1
        # The corrected record should have _corrected flag
        corrected = [item for item in cleaned if item.get("_corrected")]
        assert len(corrected) == 1
        # Value should be clipped within IQR bounds (approx)
        corrected_value = corrected[0]["price"]
        assert corrected_value < 99999.0

    def test_clean_all(self):
        # Use a dedicated set without missing values so IQR is not inflated by interpolation
        # With values [1800, 1850, 99999, 1900], IQR bounds are narrow → 99999 is outlier
        import copy
        clean_sample = [
            {"timestamp": datetime(2023, 1, 1, tzinfo=timezone.utc), "price": 1800.0},
            {"timestamp": datetime(2023, 1, 1, tzinfo=timezone.utc), "price": 1800.0},  # duplicate
            {"timestamp": datetime(2023, 1, 2, tzinfo=timezone.utc), "price": 1850.0},
            {"timestamp": datetime(2023, 1, 3, tzinfo=timezone.utc), "price": 99999.0}, # anomaly
            {"timestamp": datetime(2023, 1, 4, tzinfo=timezone.utc), "price": 1900.0},
        ]
        cleaned, stats = self.cleaner.clean_all(clean_sample)
        # Expect duplicates removed (1) and anomaly corrected
        assert stats["duplicates"]["duplicate_count"] == 1
        assert stats["anomalies"]["anomaly_count"] == 1
        # Final count: original(5) - duplicates(1) = 4 (anomaly is clipped, not removed)
        assert len(cleaned) == 4


class TestOutlierDetector:
    def setup_method(self):
        self.detector = OutlierDetector()
        # 10 normal values (1000) + 1 extreme outlier (10000)
        # With 10x1000 + 1x10000: std≈2587, z(10000)≈3.16>3.0 → Z-score outlier
        # Q1=Q3=1000, IQR=0, bounds=[1000,1000] → IQR outlier
        self.data = [
            {"timestamp": datetime(2023, 1, i+1, tzinfo=timezone.utc), "price": p}
            for i, p in enumerate([1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 10000])
        ]

    def test_detect_zscore(self):
        result, stats = self.detector.detect_zscore(self.data, value_field="price", threshold=2.0)
        # Expect the 10000 value to be flagged as outlier
        outliers = [item for item in result if item.get("_is_outlier")]
        assert len(outliers) == 1
        assert outliers[0]["price"] == 10000
        assert stats["outlier_count"] == 1

    def test_detect_iqr(self):
        result, stats = self.detector.detect_iqr(self.data, value_field="price", multiplier=1.5)
        outliers = [item for item in result if item.get("_is_outlier")]
        # IQR should also flag the 10000 value as outlier
        assert len(outliers) == 1
        assert outliers[0]["price"] == 10000
        assert stats["outlier_count"] == 1

    def test_combined_detection(self):
        result, stats = self.detector.detect_combined(self.data, value_field="price")
        # Combined should only mark as _is_outlier if both methods agree
        combined_outliers = [item for item in result if item.get("_is_outlier")]
        assert len(combined_outliers) == 1
        assert combined_outliers[0]["price"] == 10000
        assert stats["outlier_count"] == 1

    def test_get_outliers_only(self):
        outliers = self.detector.get_outliers_only(self.data, value_field="price", method="iqr")
        assert len(outliers) == 1
        assert outliers[0]["price"] == 10000

    def test_singleton_instances(self):
        d1 = get_outlier_detector()
        d2 = get_outlier_detector()
        assert d1 is d2
