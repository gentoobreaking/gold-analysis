"""
Position Sync - 持倉同步與帳戶對帳模組
負責將交易所的持倉資訊同步至本地資料庫或緩存，
並提供統計與風險檢查的入口。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .exchange_client import ExchangeClient
from .order_types import Position, AccountBalance

logger = logging.getLogger(__name__)


class PositionSync:
    """持倉同步管理器"""

    def __init__(self, client: Optional[ExchangeClient] = None, use_mock: bool = True, **client_kwargs):
        self.client = client or ExchangeClient(use_mock=use_mock, **client_kwargs)
        self.logger = logging.getLogger(__name__)
        self._cache: Dict[str, Position] = {}
        self._account: Optional[AccountBalance] = None

    # ─── 同步方法 ────────────────────────────────────────
    def sync_positions(self) -> List[Position]:
        """從交易所拉取最新持倉，更新本地快取並返回列表"""
        positions = self.client.get_positions()
        self._cache = {p.symbol: p for p in positions}
        self.logger.info(f"持倉同步完成，總計 {len(positions)} 個持倉")
        return positions

    def get_position(self, symbol: str) -> Optional[Position]:
        return self._cache.get(symbol)

    def list_positions(self) -> List[Position]:
        return list(self._cache.values())

    # ─── 帳戶資訊 ────────────────────────────────────────
    def refresh_account(self) -> AccountBalance:
        self._account = self.client.get_account_balance()
        self.logger.debug("帳戶資訊已刷新")
        return self._account

    def get_account(self) -> Optional[AccountBalance]:
        return self._account

    # ─── 報告與統計 ────────────────────────────────────────
    def summary(self) -> Dict[str, Any]:
        """返回簡易持倉概況（總持倉、市值、未平盈虧）"""
        total_value = sum(p.market_value for p in self._cache.values())
        total_unrealized = sum(p.unrealized_pnl for p in self._cache.values())
        return {
            "total_positions": len(self._cache),
            "total_market_value": total_value,
            "total_unrealized_pnl": total_unrealized,
        }

    # ─── 清理資源 ────────────────────────────────────────
    def close(self) -> None:
        self.client.close()
        self.logger.info("PositionSync 已關閉")
