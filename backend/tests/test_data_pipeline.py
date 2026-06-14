"""
Tests for Data Pipeline Integration
Validates end-to-end: validation -> cleaning -> reporting
"""

import pytest
from datetime import datetime, timezone
from app.validators import PriceValidator, MarketValidator
from app.cleaners import PriceCleaner, OutlierDetector
from app.reports import DataQualityReport


class TestDataPipeline:
    """數據管道整合測試"""
    
    def test_full_pipeline(self):
        """測試完整數據處理流程"""
        # 1. 模擬原始數據
        raw_data = [
            {'timestamp': datetime(2026, 4, 7, 10, 0, tzinfo=timezone.utc), 'price': 4792.0},
            {'timestamp': datetime(2026, 4, 7, 10, 1, tzinfo=timezone.utc), 'price': 4795.0},
            {'timestamp': datetime(2026, 4, 7, 10, 2, tzinfo=timezone.utc), 'price': None},  # 缺失
            {'timestamp': datetime(2026, 4, 7, 10, 0, tzinfo=timezone.utc), 'price': 4792.0},  # 重複
            {'timestamp': datetime(2026, 4, 7, 10, 3, tzinfo=timezone.utc), 'price': 5000.0},  # 異常
        ]
        
        # 2. 驗證
        validator = PriceValidator()
        validation_results = [validator.validate(d) for d in raw_data]
        valid_count = sum(1 for r in validation_results if r['is_valid'])
        
        # 3. 清洗
        cleaner = PriceCleaner()
        cleaned_data = cleaner.remove_duplicates(raw_data)
        cleaned_data = cleaner.clean_missing_values(cleaned_data, method='interpolate')
        
        # 4. 異常檢測
        detector = OutlierDetector()
        outlier_indices, outlier_stats = detector.detect_iqr(
            cleaned_data, field='price', return_indices=True
        )
        cleaned_data = detector.remove_outliers(cleaned_data, outlier_indices)
        
        # 5. 生成報告
        reporter = DataQualityReport()
        metrics = reporter.generate(
            original_data=raw_data,
            cleaned_data=cleaned_data,
            validation_stats={'valid_count': valid_count},
            cleaning_stats=cleaner.get_stats()
        )
        
        # 6. 驗證結果
        assert metrics.total_records == 5
        assert metrics.quality_score >= 0
        assert metrics.grade in ['A', 'B', 'C', 'D', 'F']
        assert len(reporter.to_json()) > 0
    
    def test_report_generation(self):
        """測試報告生成"""
        reporter = DataQualityReport()
        
        metrics = reporter.generate(
            original_data=[{'price': 100}, {'price': 200}],
            cleaned_data=[{'price': 100}, {'price': 200}],
            validation_stats={'valid_count': 2},
            cleaning_stats={'missing_fixed': 0, 'duplicates_removed': 0}
        )
        
        assert metrics.quality_score > 80
        assert metrics.grade == 'A'
