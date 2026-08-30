"""
Risk Rules Engine - 風控規則引擎
在交易執行前進行全面的風險檢查，防止過度損失。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ─── 枚舉與數據類別 ─────────────────────────────────────────────────────────


class RiskLevel(str, Enum):
    """風險等級"""

    PASS = "pass"  # 通過
    WARNING = "warning"  # 警告（可選）
    BLOCK = "block"  # 阻斷


@dataclass
class RiskCheckResult:
    """風控檢查結果"""

    level: RiskLevel
    rule_name: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_blocked(self) -> bool:
        return self.level == RiskLevel.BLOCK

    def __bool__(self) -> bool:
        return self.level != RiskLevel.BLOCK

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "rule_name": self.rule_name,
            "message": self.message,
            "details": self.details,
            "is_blocked": self.is_blocked,
        }


@dataclass
class RiskRuleConfig:
    """風控規則配置"""

    # 倉位限制
    max_position_size: float = 1.0  # 最大持倉量（標的）
    max_position_value_pct: float = 0.20  # 最大持倉價值佔帳戶淨值比例
    max_total_positions: int = 5  # 最大持倉標的數量

    # 單筆交易限制
    max_order_value: float = 50000.0  # 單筆最大價值
    max_order_quantity: float = 10.0  # 單筆最大數量
    min_order_value: float = 10.0  # 單筆最小價值

    # 虧損控制
    max_daily_loss: float = 1000.0  # 每日最大虧損（USD）
    max_daily_loss_pct: float = 0.05  # 每日最大虧損比例（帳戶淨值）
    max_drawdown: float = 0.15  # 最大回撤限制
    stop_loss_required: bool = True  # 是否強制要求止損價
    default_stop_loss_pct: float = 0.02  # 預設止損比例（2%）

    # 杠桿限制
    max_leverage: float = 1.0  # 最大杠桿倍數

    # 交易頻率
    max_orders_per_minute: int = 5  # 每分鐘最大訂單數
    max_orders_per_day: int = 50  # 每日最大訂單數

    # 交易時段
    trading_hours_only: bool = False  # 是否只在交易時段允許交易


# ─── 風控規則 ───────────────────────────────────────────────────────────────


class RiskRule:
    """
    單一風控規則基類

    子類需實現 check() 方法。
    """

    name: str = "base_rule"
    description: str = ""

    def __init__(self, config: RiskRuleConfig | None = None):
        self.config = config or RiskRuleConfig()

    def check(
        self,
        order_value: float,
        order_quantity: float,
        position: Any,
        account: Any,
        existing_orders: list[Any],
        **kwargs,
    ) -> RiskCheckResult:
        """
        執行風控檢查

        Args:
            order_value: 訂單總價值
            order_quantity: 訂單數量
            position: 現有持倉（若無則 None）
            account: 帳戶餘額
            existing_orders: 待成交訂單列表

        Returns:
            RiskCheckResult
        """
        raise NotImplementedError

    def _warn(self, message: str, details: dict | None = None) -> RiskCheckResult:
        return RiskCheckResult(
            level=RiskLevel.WARNING,
            rule_name=self.name,
            message=message,
            details=details or {},
        )

    def _block(self, message: str, details: dict | None = None) -> RiskCheckResult:
        return RiskCheckResult(
            level=RiskLevel.BLOCK,
            rule_name=self.name,
            message=message,
            details=details or {},
        )

    def _pass(self) -> RiskCheckResult:
        return RiskCheckResult(
            level=RiskLevel.PASS,
            rule_name=self.name,
            message="OK",
        )


class MaxPositionValueRule(RiskRule):
    """持倉價值佔比限制"""

    name = "max_position_value"
    description = "持倉價值不得超過帳戶淨值的指定比例"

    def check(
        self,
        order_value: float,
        order_quantity: float,
        position: Any,
        account: Any,
        existing_orders: list[Any],
        **kwargs,
    ) -> RiskCheckResult:
        if position is None:
            new_position_value = order_value
        else:
            new_position_value = (position.quantity + order_quantity) * order_value / order_quantity

        pct = new_position_value / max(account.total_equity, 1)

        if pct > self.config.max_position_value_pct:
            return self._block(
                f"持倉價值佔比 {pct:.1%} 超過限制 {self.config.max_position_value_pct:.1%}",
                {"new_pct": pct, "limit": self.config.max_position_value_pct},
            )

        return self._pass()


class MaxOrderSizeRule(RiskRule):
    """單筆訂單大小限制"""

    name = "max_order_size"
    description = "單筆訂單價值和數量不得超過限制"

    def check(
        self,
        order_value: float,
        order_quantity: float,
        position: Any,
        account: Any,
        existing_orders: list[Any],
        **kwargs,
    ) -> RiskCheckResult:
        reasons = []

        if order_value > self.config.max_order_value:
            reasons.append(f"訂單價值 ${order_value:.2f} > 限制 ${self.config.max_order_value:.2f}")

        if order_quantity > self.config.max_order_quantity:
            reasons.append(f"訂單數量 {order_quantity} > 限制 {self.config.max_order_quantity}")

        if reasons:
            return self._block(
                "; ".join(reasons), {"order_value": order_value, "order_quantity": order_quantity}
            )

        if order_value < self.config.min_order_value:
            return self._warn(
                f"訂單價值 ${order_value:.2f} 低於最小限制 ${self.config.min_order_value:.2f}",
                {"order_value": order_value},
            )

        return self._pass()


class DailyLossLimitRule(RiskRule):
    """每日虧損限制"""

    name = "daily_loss_limit"
    description = "當日累計虧損不得超過閾值"

    def check(
        self,
        order_value: float,
        order_quantity: float,
        position: Any,
        account: Any,
        existing_orders: list[Any],
        **kwargs,
    ) -> RiskCheckResult:
        today_loss = account.realized_pnl_today

        if today_loss < -self.config.max_daily_loss:
            return self._block(
                f"今日累計虧損 ${today_loss:.2f} 已觸及限制 ${self.config.max_daily_loss:.2f}",
                {"today_loss": today_loss, "limit": self.config.max_daily_loss},
            )

        loss_pct = abs(today_loss) / max(account.total_equity, 1)
        if loss_pct > self.config.max_daily_loss_pct:
            return self._block(
                f"今日虧損 {loss_pct:.1%} 超過限制 {self.config.max_daily_loss_pct:.1%}",
                {"loss_pct": loss_pct, "limit": self.config.max_daily_loss_pct},
            )

        # 警告：即將觸發限制
        if loss_pct > self.config.max_daily_loss_pct * 0.8:
            return self._warn(
                f"今日虧損已達 {loss_pct:.1%}（限制的 80%），請注意風險",
                {"loss_pct": loss_pct},
            )

        return self._pass()


class StopLossRule(RiskRule):
    """止損保護規則"""

    name = "stop_loss_required"
    description = "持倉必須設定止損價"

    def check(
        self,
        order_value: float,
        order_quantity: float,
        position: Any,
        account: Any,
        existing_orders: list[Any],
        stop_loss_price: float | None = None,
        entry_price: float | None = None,
    ) -> RiskCheckResult:
        if not self.config.stop_loss_required:
            return self._pass()

        # 新倉位必須有止損價
        if position is None and stop_loss_price is None:
            # 提供預設止損價（建議）
            return self._warn(
                f"新倉位未設定止損價，建議使用 {self.config.default_stop_loss_pct:.1%} 止損",
                {"default_stop_loss_pct": self.config.default_stop_loss_pct},
            )

        # 止損比例合理性檢查
        if stop_loss_price and entry_price:
            loss_pct = abs(entry_price - stop_loss_price) / entry_price
            if loss_pct > 0.20:  # 止損超過 20% 視為不合理
                return self._warn(
                    f"止損比例 {loss_pct:.1%} 過大，建議控制在 20% 以內",
                    {"loss_pct": loss_pct},
                )

        return self._pass()


class BuyingPowerRule(RiskRule):
    """購買力限制"""

    name = "buying_power"
    description = "訂單價值不得超過帳戶可用購買力"

    def check(
        self,
        order_value: float,
        order_quantity: float,
        position: Any,
        account: Any,
        existing_orders: list[Any],
        **kwargs,
    ) -> RiskCheckResult:
        # 計算待成交訂單佔用的資金
        pending_value = sum(o.get("value", 0) for o in existing_orders)
        available = account.buying_power - pending_value

        if order_value > available:
            return self._block(
                f"訂單價值 ${order_value:.2f} 超過可用購買力 ${available:.2f}",
                {"order_value": order_value, "available": available},
            )

        return self._pass()


class TradingFrequencyRule(RiskRule):
    """交易頻率限制"""

    name = "trading_frequency"
    description = "控制交易頻率，防止過度交易"

    def __init__(self, config: RiskRuleConfig | None = None):
        super().__init__(config)
        self._order_times: list[datetime] = []

    def check(
        self,
        order_value: float,
        order_quantity: float,
        position: Any,
        account: Any,
        existing_orders: list[Any],
        **kwargs,
    ) -> RiskCheckResult:
        now = datetime.now(timezone.utc)
        minute_orders = sum(1 for t in self._order_times if (now - t).seconds < 60)

        if minute_orders >= self.config.max_orders_per_minute:
            return self._block(
                f"過去 1 分鐘已下 {minute_orders} 個訂單，超過限制 {self.config.max_orders_per_minute}",  # noqa: E501
                {"minute_orders": minute_orders},
            )

        today_orders = sum(1 for t in self._order_times if t.date() == now.date())
        if today_orders >= self.config.max_orders_per_day:
            return self._block(
                f"今日已下 {today_orders} 個訂單，超過限制 {self.config.max_orders_per_day}",
                {"today_orders": today_orders},
            )

        # 記錄本次訂單時間
        self._order_times.append(now)
        # 清理舊記錄
        cutoff = datetime.now(timezone.utc)
        self._order_times = [t for t in self._order_times if (cutoff - t).total_seconds() < 3600]

        return self._pass()

    def record_order(self, timestamp: datetime | None = None) -> None:
        """記錄已成交訂單時間"""
        self._order_times.append(timestamp or datetime.now(timezone.utc))


# ─── 風控引擎 ───────────────────────────────────────────────────────────────


class RiskRuleEngine:
    """
    風控規則引擎 - 組合多條規則，統一執行風控檢查

    使用方式:
        engine = RiskRuleEngine()
        engine.add_rule(MaxOrderSizeRule())
        result = engine.check(order=order, account=account)
        if result.is_blocked:
            raise RiskViolationError(result.message)
    """

    def __init__(self, config: RiskRuleConfig | None = None):
        self.config = config or RiskRuleConfig()
        self.rules: list[RiskRule] = []
        self.logger = logging.getLogger(__name__)
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """註冊預設風控規則"""
        self.add_rule(BuyingPowerRule(self.config))
        self.add_rule(MaxOrderSizeRule(self.config))
        self.add_rule(MaxPositionValueRule(self.config))
        self.add_rule(DailyLossLimitRule(self.config))
        self.add_rule(TradingFrequencyRule(self.config))

    def add_rule(self, rule: RiskRule) -> RiskRuleEngine:
        """添加風控規則"""
        self.rules.append(rule)
        self.logger.info(f"已添加風控規則: {rule.name}")
        return self

    def remove_rule(self, rule_name: str) -> bool:
        """移除指定名稱的規則"""
        self.rules = [r for r in self.rules if r.name != rule_name]
        return rule_name not in [r.name for r in self.rules]

    def check(
        self,
        order_side: str,
        symbol: str,
        quantity: float,
        price: float,
        position: Any | None = None,
        account: Any | None = None,
        existing_orders: list[Any] | None = None,
        **kwargs,
    ) -> tuple[bool, list[RiskCheckResult]]:
        """
        執行所有風控規則檢查

        Args:
            order_side: 買入或賣出
            symbol: 標的代碼
            quantity: 數量
            price: 價格
            position: 現有持倉
            account: 帳戶餘額
            existing_orders: 待成交訂單
            **kwargs: 額外參數（如 stop_loss_price, entry_price）

        Returns:
            (是否通過, 檢查結果列表)
        """
        account = account or self._mock_account()
        existing_orders = existing_orders or []
        order_value = quantity * price

        all_results: list[RiskCheckResult] = []

        for rule in self.rules:
            try:
                result = rule.check(
                    order_value=order_value,
                    order_quantity=quantity,
                    position=position,
                    account=account,
                    existing_orders=existing_orders,
                    stop_loss_price=kwargs.get("stop_loss_price"),
                    entry_price=kwargs.get("entry_price"),
                )
                all_results.append(result)

                if result.is_blocked:
                    self.logger.warning(f"風控阻斷 [{rule.name}]: {result.message}")

            except Exception as e:
                self.logger.error(f"風控規則 {rule.name} 執行錯誤: {e}")
                all_results.append(
                    RiskCheckResult(
                        level=RiskLevel.BLOCK,
                        rule_name=rule.name,
                        message=f"規則執行異常: {e}",
                    )
                )

        blocked = [r for r in all_results if r.is_blocked]
        passed = len(blocked) == 0

        if passed:
            self.logger.debug(f"風控檢查通過，共執行 {len(all_results)} 條規則")

        return passed, all_results

    def get_summary(
        self,
        results: list[RiskCheckResult],
    ) -> dict[str, Any]:
        """
        生成風控結果摘要

        Args:
            results: 檢查結果列表

        Returns:
            摘要字典
        """
        blocked = [r for r in results if r.level == RiskLevel.BLOCK]
        warnings = [r for r in results if r.level == RiskLevel.WARNING]

        return {
            "passed": len(blocked) == 0,
            "total_rules": len(results),
            "blocked_count": len(blocked),
            "warning_count": len(warnings),
            "blocked_rules": [{"name": r.rule_name, "message": r.message} for r in blocked],
            "warnings": [{"name": r.rule_name, "message": r.message} for r in warnings],
        }

    @staticmethod
    def _mock_account() -> Any:
        """返回一個默認模擬帳戶"""
        from dataclasses import dataclass

        @dataclass
        class MockAccount:
            total_equity: float = 100000.0
            cash: float = 100000.0
            buying_power: float = 100000.0
            realized_pnl_today: float = 0.0

        return MockAccount()
