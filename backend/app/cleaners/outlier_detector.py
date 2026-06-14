"""
Outlier Detector - 異常值檢測器
使用 Z-score 和 IQR 方法檢測異常值
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from ..validators.config import get_cleaning_settings

logger = logging.getLogger(__name__)


class OutlierDetector:
    """異常值檢測器"""
    
    def __init__(self):
        self.settings = get_cleaning_settings()
        self._last_stats: Dict[str, Any] = {}
    
    def detect_zscore(
        self,
        data: List[Dict[str, Any]],
        value_field: str = "price",
        threshold: Optional[float] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        使用 Z-score 方法檢測異常值
        
        Z-score = (x - mean) / std
        絕對值 > threshold 視為異常
        
        Args:
            data: 數據列表
            value_field: 數值字段名
            threshold: Z-score 閾值（預設從配置讀取）
            
        Returns:
            (附加異常標記的數據, 檢測統計)
        """
        if threshold is None:
            threshold = self.settings.zscore_threshold
        
        # 提取有效值
        valid_data = [item for item in data if item.get(value_field) is not None]
        
        if len(valid_data) < 3:
            return data, {"outlier_count": 0, "method": "zscore", "reason": "insufficient data"}
        
        values = np.array([item[value_field] for item in valid_data])
        
        # 計算 Z-score
        mean = np.mean(values)
        std = np.std(values)
        
        if std == 0:
            logger.warning("Standard deviation is 0, cannot compute Z-score")
            return data, {"outlier_count": 0, "method": "zscore", "reason": "std=0"}
        
        z_scores = (values - mean) / std
        
        # 建立 valid_data 索引映射（避免重複 price 造成混淆）
        # valid_indices[i] = valid_data[i] 在原始 data 中的 index
        valid_indices = [i for i, item in enumerate(data) if item.get(value_field) is not None]
        
        # 標記異常值
        outlier_count = 0
        result = []
        
        for i, item in enumerate(data.copy()):
            value = item.get(value_field)
            
            if value is None:
                result.append(item)
                continue
            
            # 查找此 item 在 valid_data 中的位置
            try:
                valid_data_idx = valid_indices.index(i)
                z = z_scores[valid_data_idx]
                
                if abs(z) > threshold:
                    outlier_count += 1
                    new_item = item.copy()
                    new_item["_is_outlier"] = True
                    new_item["_outlier_zscore"] = round(z, 4)
                    new_item["_outlier_method"] = "zscore"
                    result.append(new_item)
                    logger.debug(f"Z-score outlier detected: value={value}, z={z:.4f}")
                else:
                    result.append(item)
            except ValueError:
                result.append(item)
        
        logger.info(f"Z-score detection found {outlier_count} outliers (threshold={threshold})")
        
        return result, {
            "outlier_count": outlier_count,
            "method": "zscore",
            "threshold": threshold,
            "mean": round(mean, 4),
            "std": round(std, 4),
            "bounds": {
                "lower": round(mean - threshold * std, 4),
                "upper": round(mean + threshold * std, 4)
            }
        }
    
    def detect_iqr(
        self,
        data: List[Dict[str, Any]],
        value_field: Optional[str] = None,
        multiplier: Optional[float] = None,
        field: Optional[str] = None,
        return_indices: bool = False,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        使用 IQR (四分位距) 方法檢測異常值
        
        IQR = Q3 - Q1
        低於 Q1 - multiplier*IQR 或 高於 Q3 + multiplier*IQR 視為異常
        
        Args:
            data: 數據列表
            value_field: 數值字段名
            multiplier: IQR 倍數（預設從配置讀取）
            
        Returns:
            (附加異常標記的數據, 檢測統計)
        """
        if multiplier is None:
            multiplier = self.settings.iqr_multiplier

        # 支援 field 參數別名
        _field = field if field is not None else (value_field or "price")

        # 提取有效值
        valid_data = [item for item in data if item.get(_field) is not None]

        if len(valid_data) < 4:
            return data, {"outlier_count": 0, "method": "iqr", "reason": "insufficient data"}

        values = np.array([item[_field] for item in valid_data])

        # 計算 Q1, Q3, IQR
        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1

        lower_bound = q1 - multiplier * iqr
        upper_bound = q3 + multiplier * iqr

        # 標記異常值 / 收集索引
        outlier_count = 0
        outlier_indices: List[int] = []
        result = []

        for i, item in enumerate(data):
            value = item.get(_field)

            if value is None:
                result.append(item)
                continue

            is_outlier = value < lower_bound or value > upper_bound

            if is_outlier:
                outlier_count += 1
                outlier_indices.append(i)
                if not return_indices:
                    new_item = item.copy()
                    new_item["_is_outlier"] = True
                    new_item["_outlier_iqr"] = round(value - q1, 4) if value < q1 else round(value - q3, 4)
                    new_item["_outlier_method"] = "iqr"
                    result.append(new_item)
                logger.debug(f"IQR outlier detected: value={value}, bounds=[{lower_bound:.2f}, {upper_bound:.2f}]")
            else:
                result.append(item)
        
        logger.info(f"IQR detection found {outlier_count} outliers (multiplier={multiplier})")

        stats = {
            "outlier_count": outlier_count,
            "method": "iqr",
            "multiplier": multiplier,
            "q1": round(q1, 4),
            "q3": round(q3, 4),
            "iqr": round(iqr, 4),
            "bounds": {
                "lower": round(lower_bound, 4),
                "upper": round(upper_bound, 4)
            }
        }

        if return_indices:
            self._last_stats = stats
            return outlier_indices, stats

        self._last_stats = stats
        return result, stats
    
    def detect_combined(
        self,
        data: List[Dict[str, Any]],
        value_field: str = "price"
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        組合檢測：同時使用 Z-score 和 IQR
        
        兩種方法都標記為異常才算異常
        
        Args:
            data: 數據列表
            value_field: 數值字段名
            
        Returns:
            (附加異常標記的數據, 檢測統計)
        """
        # 先用 Z-score
        data_zscore, stats_zscore = self.detect_zscore(data, value_field)
        
        # 再用 IQR
        data_iqr, stats_iqr = self.detect_iqr(data, value_field)
        
        # 合併結果
        outlier_count = 0
        result = []
        
        for i, item in enumerate(data):
            zscore_outlier = data_zscore[i].get("_is_outlier", False)
            iqr_outlier = data_iqr[i].get("_is_outlier", False)
            
            new_item = item.copy()
            
            # 組合邏輯：兩種方法都認為是異常才算
            if zscore_outlier and iqr_outlier:
                new_item["_is_outlier"] = True
                new_item["_outlier_method"] = "combined"
                outlier_count += 1
            elif zscore_outlier:
                new_item["_is_outlier_zscore_only"] = True
            elif iqr_outlier:
                new_item["_is_outlier_iqr_only"] = True
            
            result.append(new_item)
        
        return result, {
            "outlier_count": outlier_count,
            "method": "combined",
            "zscore_outliers": stats_zscore["outlier_count"],
            "iqr_outliers": stats_iqr["outlier_count"],
            "zscore_stats": stats_zscore,
            "iqr_stats": stats_iqr
        }
    
    def get_outliers_only(
        self,
        data: List[Dict[str, Any]],
        value_field: str = "price",
        method: str = "zscore"
    ) -> List[Dict[str, Any]]:
        """
        僅返回異常值列表
        
        Args:
            data: 數據列表
            value_field: 數值字段名
            method: 檢測方法 ("zscore", "iqr", "combined")
            
        Returns:
            異常值列表
        """
        if method == "zscore":
            result, _ = self.detect_zscore(data, value_field)
        elif method == "iqr":
            result, _ = self.detect_iqr(data, value_field)
        elif method == "combined":
            result, _ = self.detect_combined(data, value_field)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        return [item for item in result if item.get("_is_outlier", False)]

    def remove_outliers(
        self,
        data: List[Dict[str, Any]],
        outlier_indices: List[int]
    ) -> List[Dict[str, Any]]:
        """
        移除指定的異常值記錄
        
        Args:
            data: 數據列表
            outlier_indices: 需要移除的記錄索引列表
            
        Returns:
            移除異常值後的數據列表
        """
        outlier_set = set(outlier_indices)
        result = [item for i, item in enumerate(data) if i not in outlier_set]
        self._last_stats["removed_count"] = len(outlier_set)
        return result

    def get_stats(self) -> Dict[str, Any]:
        """取得最近一次操作的統計信息"""
        return self._last_stats.copy()


# 預設實例
_default_detector: Optional[OutlierDetector] = None


def get_outlier_detector() -> OutlierDetector:
    """取得預設的異常值檢測器實例"""
    global _default_detector
    if _default_detector is None:
        _default_detector = OutlierDetector()
    return _default_detector
