"""
數據收集 Agent
實現數據聚合、驗證、存儲功能
"""
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field

from data_adapters.bot_adapter import BotBankAdapter
from data_adapters.yahoo_finance_adapter import YahooFinanceAdapter
from db.database import Database, get_database

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """重試配置"""
    max_retries: int = 3
    base_delay: float = 1.0  # 秒
    max_delay: float = 10.0  # 秒
    timeout: float = 10.0    # 秒


@dataclass
class CollectionResult:
    """收集結果"""
    source: str
    success: bool
    data: List[Dict] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: int = 0
    retries: int = 0


class DataCollectorAgent:
    """數據收集 Agent"""
    
    def __init__(self, db: Database = None, retry_config: RetryConfig = None):
        """
        初始化數據收集 Agent
        
        Args:
            db: 數據庫實例
            retry_config: 重試配置
        """
        self.db = db or get_database()
        self.retry_config = retry_config or RetryConfig()
        
        # 初始化數據源適配器
        self.adapters = {
            'BOT': BotBankAdapter(timeout=self.retry_config.timeout),
            'YAHOO': YahooFinanceAdapter(
                timeout=self.retry_config.timeout,
                convert_to_twd=True
            ),
        }
    
    def collect_all_prices(self, sources: List[str] = None) -> Dict[str, CollectionResult]:
        """
        並行收集所有金屬價格
        
        Args:
            sources: 要收集的數據源列表，默認全部
        
        Returns:
            各數據源的收集結果
        """
        if sources is None:
            sources = list(self.adapters.keys())
        
        results = {}
        
        # 使用 ThreadPoolExecutor 並行調用
        with ThreadPoolExecutor(max_workers=len(sources)) as executor:
            # 提交所有任務
            future_to_source = {
                executor.submit(self._collect_from_source, source): source
                for source in sources
            }
            
            # 收集結果
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    result = future.result()
                    results[source] = result
                    logger.info(f"Collected {len(result.data)} records from {source}")
                except Exception as e:
                    logger.error(f"Unexpected error from {source}: {e}")
                    results[source] = CollectionResult(
                        source=source,
                        success=False,
                        error=str(e)
                    )
        
        return results
    
    def _collect_from_source(self, source: str) -> CollectionResult:
        """從指定數據源收集數據（帶重試）"""
        start_time = time.time()
        adapter = self.adapters.get(source)
        
        if not adapter:
            return CollectionResult(
                source=source,
                success=False,
                error=f"Unknown source: {source}"
            )
        
        retries = 0
        last_error = None
        
        # 重試機制：指數退避
        delay = self.retry_config.base_delay
        
        while retries <= self.retry_config.max_retries:
            try:
                data = adapter.fetch_prices()
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                return CollectionResult(
                    source=source,
                    success=True,
                    data=data,
                    duration_ms=duration_ms,
                    retries=retries
                )
                
            except Exception as e:
                last_error = str(e)
                retries += 1
                
                if retries <= self.retry_config.max_retries:
                    logger.warning(
                        f"{source} fetch failed (attempt {retries}), "
                        f"retrying in {delay}s: {e}"
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, self.retry_config.max_delay)  # 指數退避
                else:
                    logger.error(f"{source} failed after {retries} attempts: {e}")
        
        duration_ms = int((time.time() - start_time) * 1000)
        return CollectionResult(
            source=source,
            success=False,
            error=last_error,
            duration_ms=duration_ms,
            retries=retries
        )
    
    def validate_data(self, data: List[Dict]) -> tuple[List[Dict], List[Dict]]:
        """
        驗證數據有效性
        
        Args:
            data: 原始數據列表
        
        Returns:
            (有效數據, 無效數據)
        """
        valid_data = []
        invalid_data = []
        
        for item in data:
            if self._validate_single(item):
                valid_data.append(item)
            else:
                invalid_data.append(item)
        
        if invalid_data:
            logger.warning(f"Found {len(invalid_data)} invalid records")
        
        return valid_data, invalid_data
    
    def _validate_single(self, item: Dict) -> bool:
        """驗證單條數據"""
        # 必需字段
        required_fields = ['symbol', 'source', 'timestamp']
        for field in required_fields:
            if field not in item or item[field] is None:
                return False
        
        # 符號必須有效
        valid_symbols = ['GOLD', 'SILVER', 'PLATINUM', 'PALLADIUM']
        if item['symbol'] not in valid_symbols:
            return False
        
        # 至少有一個價格
        price_fields = ['buy_price', 'sell_price', 'spot_price']
        has_price = any(
            item.get(field) is not None and item.get(field, 0) > 0
            for field in price_fields
        )
        if not has_price:
            return False
        
        # 時間戳必須是有效日期
        if not isinstance(item['timestamp'], datetime):
            try:
                datetime.fromisoformat(str(item['timestamp']))
            except (ValueError, TypeError):
                return False
        
        return True
    
    def deduplicate(self, data: List[Dict]) -> List[Dict]:
        """
        數據去重
        
        Args:
            data: 原始數據列表
        
        Returns:
            去重後的數據列表
        """
        seen = set()
        unique_data = []
        
        for item in data:
            # 使用 (symbol, source, timestamp) 作為唯一鍵
            key = (
                item.get('symbol'),
                item.get('source'),
                self._normalize_timestamp(item.get('timestamp'))
            )
            
            if key not in seen:
                seen.add(key)
                unique_data.append(item)
            else:
                logger.debug(f"Duplicate removed: {key}")
        
        duplicates_removed = len(data) - len(unique_data)
        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate records")
        
        return unique_data
    
    def _normalize_timestamp(self, ts) -> str:
        """標準化時間戳為字符串"""
        if isinstance(ts, datetime):
            return ts.isoformat()
        return str(ts) if ts else ''
    
    def store_to_db(self, data: List[Dict]) -> tuple[int, int]:
        """
        存儲數據到數據庫
        
        Args:
            data: 待存儲的數據列表
        
        Returns:
            (成功存儲數, 重複跳過數)
        """
        stored = 0
        skipped = 0
        
        for item in data:
            try:
                # 確保時間戳是 datetime 對象
                if isinstance(item.get('timestamp'), str):
                    item['timestamp'] = datetime.fromisoformat(item['timestamp'])
                
                if self.db.insert_price(item):
                    stored += 1
                else:
                    skipped += 1
                    
            except Exception as e:
                logger.error(f"Failed to store record: {e}")
                skipped += 1
        
        logger.info(f"Stored {stored} records, skipped {skipped} duplicates")
        return stored, skipped
    
    def run_collection(self) -> Dict:
        """
        執行完整收集流程
        
        Returns:
            收集結果摘要
        """
        summary = {
            'start_time': datetime.now().isoformat(),
            'sources': {},
            'total_collected': 0,
            'total_valid': 0,
            'total_stored': 0,
            'errors': []
        }
        
        # 1. 並行收集
        results = self.collect_all_prices()
        
        all_data = []
        for source, result in results.items():
            summary['sources'][source] = {
                'success': result.success,
                'records': len(result.data),
                'duration_ms': result.duration_ms,
                'retries': result.retries,
                'error': result.error
            }
            
            if result.success:
                all_data.extend(result.data)
                self.db.log_collection(
                    source=source,
                    status='SUCCESS',
                    message=f"Collected {len(result.data)} records",
                    records=len(result.data),
                    duration_ms=result.duration_ms
                )
            else:
                summary['errors'].append(f"{source}: {result.error}")
                self.db.log_collection(
                    source=source,
                    status='FAILED',
                    message=result.error,
                    duration_ms=result.duration_ms
                )
            
            summary['total_collected'] += len(result.data)
        
        # 2. 數據驗證
        valid_data, invalid_data = self.validate_data(all_data)
        summary['total_valid'] = len(valid_data)
        summary['invalid_count'] = len(invalid_data)
        
        # 3. 去重
        unique_data = self.deduplicate(valid_data)
        summary['deduplicated'] = len(valid_data) - len(unique_data)
        
        # 4. 存儲
        stored, skipped = self.store_to_db(unique_data)
        summary['total_stored'] = stored
        summary['skipped'] = skipped
        
        summary['end_time'] = datetime.now().isoformat()
        
        logger.info(f"Collection summary: {summary}")
        return summary
    
    def run_scheduled(self):
        """定時執行（由調度器調用）"""
        logger.info("Starting scheduled collection run")
        try:
            result = self.run_collection()
            logger.info(f"Scheduled run completed: {result['total_stored']} stored")
            return result
        except Exception as e:
            logger.error(f"Scheduled run failed: {e}")
            raise
    
    def close(self):
        """關閉資源"""
        for adapter in self.adapters.values():
            adapter.close()
        self.db.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 便捷函數
def run_once():
    """執行一次收集"""
    with DataCollectorAgent() as agent:
        return agent.run_collection()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    result = run_once()
    print(f"\nCollected: {result['total_collected']} records")
    print(f"Valid: {result['total_valid']} records")
    print(f"Stored: {result['total_stored']} records")
    print(f"Errors: {len(result['errors'])}")
