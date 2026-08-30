"""
Price data access (T063) - 從 SQLite price_history 取真實收盤價序列

與 T054 scheduler 共用同一張 price_history 表（local_buy 欄位），
讓回測 / 比較視圖能直接吃真實歷史資料（而非隨機漫步）。
"""

from __future__ import annotations

import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

_DB_PATH = os.getenv("PRICE_HISTORY_DB", "gold_prices.db")


def fetch_price_series(asset: str = "GOLD", limit: int = 400) -> tuple[list[str], list[float]]:
    """
    從 SQLite price_history 取 (dates, closes)（舊→新）。

    Returns:
        (dates_iso, closes)
    """
    if not os.path.exists(_DB_PATH):
        logger.warning("price_history DB 不存在: %s", _DB_PATH)
        return [], []

    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT date, local_buy FROM price_history
            WHERE asset = ? OR asset IS NULL
            ORDER BY date ASC
            LIMIT ?
            """,
            (asset, limit),
        )
        rows = cur.fetchall()
        conn.close()
    except sqlite3.Error as exc:
        logger.warning("讀取 price_history 失敗: %s", exc)
        return [], []

    dates = [r[0] for r in rows]
    closes = [float(r[1]) for r in rows if r[1] is not None]
    return dates, closes


def fetch_latest_date(asset: str = "GOLD") -> str | None:
    """回傳 price_history 中該資產最後一筆資料的日期 (ISO, 舊→新排序的最大 date)；無資料回 None。"""
    if not os.path.exists(_DB_PATH):
        return None
    try:
        conn = sqlite3.connect(_DB_PATH)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT MAX(date) FROM price_history
            WHERE asset = ? OR asset IS NULL
            """,
            (asset,),
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row and row[0] else None
    except sqlite3.Error as exc:
        logger.warning("讀取 price_history 最新日期失敗: %s", exc)
        return None
