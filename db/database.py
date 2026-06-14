"""
SQLite 數據庫管理模組
"""
import sqlite3
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Database:
    """SQLite 數據庫管理類"""
    
    def __init__(self, db_path: str = None):
        """
        初始化數據庫連接
        
        Args:
            db_path: 數據庫文件路徑，默認為 ~/gold-analysis/db/prices.db
        """
        if db_path is None:
            base_dir = Path(__file__).parent.parent
            db_path = base_dir / "db" / "prices.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
    
    @property
    def conn(self) -> sqlite3.Connection:
        """獲取數據庫連接（惰性初始化）"""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._init_schema()
        return self._conn
    
    def _init_schema(self):
        """初始化數據庫 schema"""
        schema_path = Path(__file__).parent / "schema.sql"
        if schema_path.exists():
            with open(schema_path, 'r', encoding='utf-8') as f:
                self._conn.executescript(f.read())
            logger.info(f"Schema initialized from {schema_path}")
    
    def close(self):
        """關閉數據庫連接"""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def get_metal_id(self, symbol: str) -> Optional[int]:
        """獲取金屬 ID"""
        cursor = self.conn.execute(
            "SELECT id FROM metals WHERE symbol = ?", (symbol,)
        )
        row = cursor.fetchone()
        return row['id'] if row else None
    
    def insert_price(self, data: Dict[str, Any]) -> bool:
        """
        插入價格數據
        
        Args:
            data: 價格數據字典
        
        Returns:
            是否插入成功（去重時返回 False）
        """
        try:
            metal_id = self.get_metal_id(data['symbol'])
            if metal_id is None:
                logger.warning(f"Unknown metal symbol: {data['symbol']}")
                return False
            
            cursor = self.conn.execute("""
                INSERT OR IGNORE INTO prices 
                (metal_id, source, buy_price, sell_price, spot_price, currency, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                metal_id,
                data['source'],
                data.get('buy_price'),
                data.get('sell_price'),
                data.get('spot_price'),
                data.get('currency', 'TWD'),
                data['timestamp']
            ))
            self.conn.commit()
            # cursor.rowcount is -1 for SQLite INSERT OR IGNORE, so check changes via total_changes delta
            inserted = self.conn.total_changes
            # If this is the first insert, total_changes will be 1, otherwise unchanged
            # To determine if this specific insert succeeded, we compare before/after totals
            # Simpler approach: attempt to fetch the row just inserted and see if exists
            if inserted:
                # Verify that a row with these unique keys exists
                cur = self.conn.execute(
                    "SELECT 1 FROM prices WHERE metal_id=? AND source=? AND timestamp=?",
                    (metal_id, data['source'], data['timestamp'])
                )
                return cur.fetchone() is not None
            return False
        except Exception as e:
            logger.error(f"Failed to insert price: {e}")
            return False
    
    def insert_prices_batch(self, prices: List[Dict[str, Any]]) -> int:
        """
        批量插入價格數據
        
        Args:
            prices: 價格數據列表
        
        Returns:
            成功插入的記錄數
        """
        inserted = 0
        for price in prices:
            if self.insert_price(price):
                inserted += 1
        return inserted
    
    def log_collection(self, source: str, status: str, message: str = None,
                       records: int = 0, duration_ms: int = None):
        """記錄收集日誌"""
        self.conn.execute("""
            INSERT INTO collection_logs 
            (source, status, message, records_collected, duration_ms)
            VALUES (?, ?, ?, ?, ?)
        """, (source, status, message, records, duration_ms))
        self.conn.commit()
    
    def get_latest_prices(self, symbol: str = None, limit: int = 100) -> List[Dict]:
        """獲取最新價格數據"""
        if symbol:
            cursor = self.conn.execute("""
                SELECT p.*, m.symbol, m.name
                FROM prices p
                JOIN metals m ON p.metal_id = m.id
                WHERE m.symbol = ?
                ORDER BY p.timestamp DESC
                LIMIT ?
            """, (symbol, limit))
        else:
            cursor = self.conn.execute("""
                SELECT p.*, m.symbol, m.name
                FROM prices p
                JOIN metals m ON p.metal_id = m.id
                ORDER BY p.timestamp DESC
                LIMIT ?
            """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 單例
_db_instance: Optional[Database] = None

def get_database() -> Database:
    """獲取數據庫單例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
