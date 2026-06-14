"""
Data Quality Report - 數據品質報告生成器
生成數據品質評估報告
"""

import logging
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class QualityMetrics:
    """數據品質指標"""
    total_records: int
    valid_records: int
    invalid_records: int
    missing_count: int
    outlier_count: int
    duplicate_count: int
    quality_score: float
    grade: str


class DataQualityReport:
    """數據品質報告生成器"""
    
    def __init__(self):
        self.timestamp: Optional[str] = None
        self.metrics: Optional[QualityMetrics] = None
    
    def generate(
        self,
        original_data: List[Dict],
        cleaned_data: List[Dict],
        validation_stats: Dict[str, Any],
        cleaning_stats: Dict[str, Any]
    ) -> QualityMetrics:
        """生成品質報告"""
        self.timestamp = datetime.now().isoformat()
        
        total = len(original_data)
        valid = validation_stats.get('valid_count', 0)
        missing = cleaning_stats.get('missing_fixed', 0)
        duplicates = cleaning_stats.get('duplicates_removed', 0)
        outliers = cleaning_stats.get('outliers_detected', 0)
        
        quality_score = self._calculate_score(total, valid, missing, duplicates, outliers)
        grade = self._get_grade(quality_score)
        
        self.metrics = QualityMetrics(
            total_records=total,
            valid_records=valid,
            invalid_records=total - valid,
            missing_count=missing,
            outlier_count=outliers,
            duplicate_count=duplicates,
            quality_score=quality_score,
            grade=grade
        )
        
        return self.metrics
    
    def _calculate_score(
        self,
        total: int,
        valid: int,
        missing: int,
        duplicates: int,
        outliers: int
    ) -> float:
        """計算品質分數"""
        if total == 0:
            return 0.0
        
        # 有效性權重 40%
        validity_score = (valid / total) * 40 if total > 0 else 0
        
        # 完整性權重 30%
        completeness_score = ((total - missing) / total) * 30 if total > 0 else 30
        
        # 一致性權重 30%
        consistency_score = ((total - duplicates) / total) * 30 if total > 0 else 30
        
        return min(100, validity_score + completeness_score + consistency_score)
    
    def _get_grade(self, score: float) -> str:
        """根據分數給出等級"""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        return 'F'
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'timestamp': self.timestamp,
            'metrics': asdict(self.metrics) if self.metrics else None
        }
    
    def to_json(self) -> str:
        """轉換為 JSON 字串"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
    
    def generate_report(
        self,
        data: List[Dict[str, Any]],
        value_field: str = "price"
    ) -> Dict[str, Any]:
        """
        生成數據品質報告
        
        包含:
        - 缺失值統計
        - 異常值統計
        - 數據完整性評分
        - 數據分佈統計
        
        Args:
            data: 數據列表
            value_field: 數值字段名
            
        Returns:
            品質報告字典
        """
        if not data:
            return {
                "timestamp": datetime.now().isoformat(),
                "error": "No data provided",
                "completeness_score": 0
            }
        
        # 1. 基本統計
        total_records = len(data)
        
        # 2. 缺失值分析
        missing_analysis = self._analyze_missing(data, value_field)
        
        # 3. 異常值分析
        outlier_analysis = self._analyze_outliers(data, value_field)
        
        # 4. 重複值分析
        duplicate_analysis = self._analyze_duplicates(data)
        
        # 5. 時間連續性分析
        continuity_analysis = self._analyze_continuity(data)
        
        # 6. 計算完整性評分
        completeness_score = self._calculate_completeness_score(
            total_records=total_records,
            missing_count=missing_analysis["missing_count"],
            outlier_count=outlier_analysis["outlier_count"],
            duplicate_count=duplicate_analysis["duplicate_count"]
        )
        
        # 7. 數值分佈統計
        distribution = self._analyze_distribution(data, value_field)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_records": total_records,
                "completeness_score": completeness_score,
                "quality_grade": self._get_quality_grade(completeness_score)
            },
            "missing_values": missing_analysis,
            "outliers": outlier_analysis,
            "duplicates": duplicate_analysis,
            "continuity": continuity_analysis,
            "distribution": distribution
        }
        
        logger.info(f"Data quality report generated: score={completeness_score:.1f}%, grade={report['summary']['quality_grade']}")
        
        return report
    
    def _analyze_missing(
        self,
        data: List[Dict[str, Any]],
        value_field: str
    ) -> Dict[str, Any]:
        """分析缺失值"""
        total = len(data)
        missing_count = sum(1 for item in data if item.get(value_field) is None)
        
        # 檢查每個字段的缺失情況
        field_missing = {}
        if total > 0:
            all_fields = set()
            for item in data:
                all_fields.update(item.keys())
            
            for field in all_fields:
                if field.startswith("_"):
                    continue
                field_missing[field] = sum(1 for item in data if item.get(field) is None)
        
        return {
            "total_records": total,
            "missing_count": missing_count,
            "missing_rate": round(missing_count / total * 100, 2) if total > 0 else 0,
            "by_field": field_missing
        }
    
    def _analyze_outliers(
        self,
        data: List[Dict[str, Any]],
        value_field: str
    ) -> Dict[str, Any]:
        """分析異常值"""
        # 提取有效值
        valid_values = [item[value_field] for item in data if item.get(value_field) is not None]
        
        if len(valid_values) < 3:
            return {
                "outlier_count": 0,
                "outlier_rate": 0,
                "method": "insufficient_data"
            }
        
        values = np.array(valid_values)
        
        # Z-score 方法
        mean = np.mean(values)
        std = np.std(values)
        zscore_outliers = np.sum(np.abs((values - mean) / std) > 3)
        
        # IQR 方法
        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        iqr_outliers = np.sum((values < lower) | (values > upper))
        
        # 檢查已標記的異常值
        marked_outliers = sum(1 for item in data if item.get("_is_outlier", False))
        
        return {
            "outlier_count": max(zscore_outliers, iqr_outliers, marked_outliers),
            "outlier_rate": round(max(zscore_outliers, iqr_outliers, marked_outliers) / len(data) * 100, 2),
            "zscore_outliers": int(zscore_outliers),
            "iqr_outliers": int(iqr_outliers),
            "marked_outliers": marked_outliers,
            "bounds": {
                "zscore": {
                    "lower": round(mean - 3 * std, 2),
                    "upper": round(mean + 3 * std, 2)
                },
                "iqr": {
                    "lower": round(lower, 2),
                    "upper": round(upper, 2)
                }
            }
        }
    
    def _analyze_duplicates(
        self,
        data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """分析重複值"""
        total = len(data)
        
        # 檢查 timestamp 重複
        timestamps = [item.get("timestamp") for item in data]
        unique_timestamps = set(str(ts) for ts in timestamps if ts is not None)
        
        duplicate_count = total - len(unique_timestamps)
        
        return {
            "total_records": total,
            "unique_records": len(unique_timestamps),
            "duplicate_count": duplicate_count,
            "duplicate_rate": round(duplicate_count / total * 100, 2) if total > 0 else 0
        }
    
    def _analyze_continuity(
        self,
        data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """分析時間連續性"""
        # 提取有時間戳的記錄
        dated_items = [
            (item.get("timestamp"), item) 
            for item in data 
            if item.get("timestamp") is not None
        ]
        
        if len(dated_items) < 2:
            return {
                "has_timestamp": len(dated_items) > 0,
                "total_dated": len(dated_items),
                "gaps_detected": 0
            }
        
        # 排序
        dated_items.sort(key=lambda x: x[0])
        timestamps = [item[0] for item in dated_items]
        
        # 計算時間間隔
        gaps = []
        for i in range(1, len(timestamps)):
            t1, t2 = timestamps[i-1], timestamps[i]
            
            # 嘗試計算差值
            if isinstance(t1, datetime) and isinstance(t2, datetime):
                delta = (t2 - t1).total_seconds() / 3600  # 小時
                # 如果間隔超過 24 小時，視為間斷
                if delta > 24:
                    gaps.append({
                        "from": str(t1),
                        "to": str(t2),
                        "hours": round(delta, 2)
                    })
        
        return {
            "has_timestamp": True,
            "total_dated": len(dated_items),
            "gaps_detected": len(gaps),
            "gaps": gaps[:5]  # 最多返回 5 個
        }
    
    def _analyze_distribution(
        self,
        data: List[Dict[str, Any]],
        value_field: str
    ) -> Dict[str, Any]:
        """分析數值分佈"""
        valid_values = [item[value_field] for item in data if item.get(value_field) is not None]
        
        if not valid_values:
            return {"error": "No valid values"}
        
        values = np.array(valid_values)
        
        return {
            "count": len(values),
            "mean": round(np.mean(values), 4),
            "median": round(np.median(values), 4),
            "std": round(np.std(values), 4),
            "min": round(np.min(values), 4),
            "max": round(np.max(values), 4),
            "q25": round(np.percentile(values, 25), 4),
            "q75": round(np.percentile(values, 75), 4),
            "range": round(np.max(values) - np.min(values), 4)
        }
    
    def _calculate_completeness_score(
        self,
        total_records: int,
        missing_count: int,
        outlier_count: int,
        duplicate_count: int
    ) -> float:
        """計算完整性評分 (0-100)"""
        if total_records == 0:
            return 0
        
        # 加權計算
        # 缺失值權重 40%
        missing_score = (1 - missing_count / total_records) * 40
        
        # 異常值權重 30%
        outlier_score = (1 - outlier_count / total_records) * 30
        
        # 重複值權重 30%
        duplicate_score = (1 - duplicate_count / total_records) * 30
        
        total_score = missing_score + outlier_score + duplicate_score
        
        return round(total_score, 2)
    
    def _get_quality_grade(self, score: float) -> str:
        """根據評分獲取等級"""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
    
    def generate_summary(
        self,
        data: List[Dict[str, Any]],
        value_field: str = "price"
    ) -> str:
        """
        生成人類可讀的品質摘要
        
        Args:
            data: 數據列表
            value_field: 數值字段名
            
        Returns:
            品質摘要字符串
        """
        report = self.generate_report(data, value_field)
        
        if "error" in report:
            return f"Error: {report['error']}"
        
        summary = report["summary"]
        missing = report["missing_values"]
        outliers = report["outliers"]
        
        lines = [
            f"📊 數據品質報告",
            f"=" * 30,
            f"總記錄數: {summary['total_records']}",
            f"完整性評分: {summary['completeness_score']:.1f}% (Grade: {summary['quality_grade']})",
            f"",
            f"缺失值: {missing['missing_count']} ({missing['missing_rate']}%)",
            f"異常值: {outliers['outlier_count']} ({outliers['outlier_rate']}%)",
        ]
        
        if "distribution" in report and "mean" in report["distribution"]:
            dist = report["distribution"]
            lines.extend([
                f"",
                f"數值分佈:",
                f"  均值: {dist['mean']:.2f}",
                f"  中位數: {dist['median']:.2f}",
                f"  範圍: {dist['min']:.2f} - {dist['max']:.2f}",
            ])
        
        return "\n".join(lines)


# 預設實例
_default_report: Optional[DataQualityReport] = None


def get_data_quality_report() -> DataQualityReport:
    """取得預設的數據品質報告生成器"""
    global _default_report
    if _default_report is None:
        _default_report = DataQualityReport()
    return _default_report
