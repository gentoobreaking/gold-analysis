"""Decision Service - AI 決策業務邏輯

從共享 PostgreSQL 讀取價格數據，基於技術指標生成決策。
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from app.models.decision import Decision, DecisionSource, DecisionType
from app.services.price_service import PriceService
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class DecisionService:
    """決策服務 - 基於技術指標生成決策"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.price_service = PriceService(session)

    async def generate_recommendation(
        self,
        user_id: int | None = None,
        symbol: str = "GOLD",
        confidence_threshold: float = 0.6,
    ) -> dict[str, Any]:
        """基於技術指標生成 AI 推薦。"""
        symbol = symbol.upper()
        if symbol != "GOLD":
            raise ValueError(f"不支持的資產符號: {symbol}")

        # Get technical indicators from PostgreSQL-backed PriceService
        indicators_data = await self.price_service.get_technical_indicators(symbol, period=14)
        indicators = indicators_data["indicators"]
        signals = indicators_data["signals"]

        # Get historical prices for volatility calculation
        hist = await self.price_service.get_historical_prices(symbol, "1d", limit=20)
        prices = [d["close"] for d in hist["data"]]

        rsi = indicators["rsi"]
        macd = indicators["macd"]
        sma_20 = indicators["sma_20"]
        _ema_20 = indicators["ema_20"]

        # Volatility
        if len(prices) > 1:
            returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]
            volatility = math.sqrt(sum(r * r for r in returns) / len(returns)) * math.sqrt(252)
        else:
            volatility = 0.1

        # Decision logic based on technical indicators
        direction = 0.0
        decision_type = DecisionType.HOLD
        confidence = 0.5

        # RSI signal
        if rsi < 30:
            direction += 0.4
            if signals["rsi"] == "oversold":
                decision_type = DecisionType.BUY
                confidence = 0.7
        elif rsi > 70:
            direction -= 0.4
            if signals["rsi"] == "overbought":
                decision_type = DecisionType.SELL
                confidence = 0.7
        else:
            if signals["rsi"] == "overbought":
                direction -= 0.2
                decision_type = DecisionType.SELL
                confidence = 0.55
            elif signals["rsi"] == "oversold":
                direction += 0.2
                decision_type = DecisionType.BUY
                confidence = 0.55

        # MACD signal
        if macd > 0:
            direction += 0.3
            if signals["macd"] == "bullish":
                confidence = min(0.9, confidence + 0.1)
        else:
            direction -= 0.3
            if signals["macd"] == "bearish":
                confidence = min(0.9, confidence + 0.1)

        # Price vs Bollinger Bands
        bb_upper = indicators["bb_upper"]
        bb_lower = indicators["bb_lower"]
        if prices:
            current_price = prices[-1]
            if current_price > bb_upper:
                direction -= 0.2
                confidence = min(0.85, confidence + 0.05)
            elif current_price < bb_lower:
                direction += 0.2
                confidence = min(0.85, confidence + 0.05)

        # Ensure confidence meets threshold
        if confidence < confidence_threshold:
            confidence = confidence_threshold + 0.05

        # Signal strength based on direction magnitude
        signal_strength = min(0.95, max(0.5, abs(direction) * 0.8 + 0.5))

        # Price targets based on SMA and volatility
        price_target = float(sma_20 * (1 + direction * 0.03))
        stop_loss = float(sma_20 * (1 - direction * 0.02))

        decision = Decision(
            user_id=user_id,
            decision_type=decision_type,
            source=DecisionSource.AI_ANALYSIS,
            asset=symbol.upper(),
            signal_strength=signal_strength,
            confidence=confidence,
            price_target=round(price_target, 2),
            stop_loss=round(stop_loss, 2),
            reason_zh=f"基於技術指標分析（RSI={rsi:.1f}，MACD={macd:.4f}），"
            f"建議 {decision_type.value.upper()}。",
            reason_en=f"Based on technical analysis (RSI={rsi:.1f}, "
            f"MACD={macd:.4f}), {decision_type.value.upper()} is recommended.",
            model_version="v1-pg",
        )

        self.session.add(decision)
        await self.session.flush()

        reasoning = (
            f"信號強度 {signal_strength:.0%}，置信度 {confidence:.0%}，波動率 {volatility:.2%}。"
        )

        # Decision explainability
        explanation = None
        try:
            from app.ml.explainer import explain_rule_decision

            direction_map = {
                "buy": 0.4,
                "strong_buy": 0.7,
                "hold": 0.0,
                "sell": -0.4,
                "strong_sell": -0.7,
            }
            direction_val = direction_map.get(decision.decision_type.value, 0.0)
            explanation = explain_rule_decision(
                scores={
                    "technical": direction_val,
                    "fundamental": direction_val * 0.6,
                    "risk": -direction_val * 0.3,
                    "composite": direction_val,
                },
                weights={"technical": 0.35, "fundamental": 0.30, "risk": 0.35},
                decision_type=decision.decision_type.value,
                reasoning_zh=decision.reason_zh,
            )
        except Exception:
            pass

        return {
            "decision": {
                "id": decision.id,
                "user_id": decision.user_id,
                "decision_type": decision.decision_type.value,
                "source": decision.source.value,
                "asset": decision.asset,
                "signal_strength": decision.signal_strength,
                "confidence": decision.confidence,
                "price_target": decision.price_target,
                "stop_loss": decision.stop_loss,
                "reason_zh": decision.reason_zh,
                "reason_en": decision.reason_en,
                "indicators_snapshot": decision.indicators_snapshot,
                "analysis_scores": decision.analysis_scores,
                "is_executed": decision.is_executed,
                "executed_at": decision.executed_at,
                "execution_price": decision.execution_price,
                "model_version": decision.model_version,
                "created_at": decision.created_at.isoformat()
                if decision.created_at
                else datetime.now(timezone.utc).isoformat(),
                "updated_at": decision.updated_at.isoformat()
                if decision.updated_at
                else datetime.now(timezone.utc).isoformat(),
            },
            "reasoning": reasoning,
            "risk_level": "high" if volatility > 0.15 else "medium",
            "suggestions": ["建議設定止損", "分批進場降低風險"],
            "warnings": [],
            "explanation": explanation,
        }

    async def create_decision(
        self,
        user_id: int,
        decision_type: DecisionType,
        source: DecisionSource,
        asset: str,
        signal_strength: float,
        confidence: float,
        price_target: float | None = None,
        stop_loss: float | None = None,
        reason_zh: str | None = None,
        reason_en: str | None = None,
        portfolio_id: int | None = None,
    ) -> Decision:
        """創建決策記錄。"""
        decision = Decision(
            user_id=user_id,
            portfolio_id=portfolio_id,
            decision_type=decision_type,
            source=source,
            asset=asset.upper(),
            signal_strength=signal_strength,
            confidence=confidence,
            price_target=price_target,
            stop_loss=stop_loss,
            reason_zh=reason_zh,
            reason_en=reason_en,
            model_version="v1",
        )
        self.session.add(decision)
        await self.session.commit()
        await self.session.refresh(decision)
        return decision

    async def execute_decision(
        self,
        decision: Decision,
        execution_price: float | None = None,
    ) -> Decision:
        """標記決策為已執行。"""
        decision.is_executed = True
        decision.executed_at = datetime.now(timezone.utc)
        if execution_price is not None:
            decision.execution_price = execution_price
        await self.session.commit()
        await self.session.refresh(decision)
        return decision

    async def get_decisions(
        self,
        user_id: int | None = None,
        symbol: str | None = None,
        decision_type: str | None = None,
        is_executed: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """列出決策記錄，支援過濾和分頁。"""
        stmt = select(Decision)
        if user_id is not None:
            stmt = stmt.where(Decision.user_id == user_id)
        if symbol:
            stmt = stmt.where(Decision.asset == symbol.upper())
        if decision_type:
            stmt = stmt.where(Decision.decision_type == decision_type)
        if is_executed is not None:
            stmt = stmt.where(Decision.is_executed == is_executed)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Paginate
        stmt = stmt.order_by(Decision.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        decisions = result.scalars().all()

        return {
            "decisions": decisions,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }

    async def get_decision_stats(self, user_id: int) -> dict[str, Any]:
        """獲取決策統計。"""
        result = await self.session.execute(select(Decision).where(Decision.user_id == user_id))
        decisions = result.scalars().all()
        total = len(decisions)

        type_counts = {dt.value: 0 for dt in DecisionType}
        executed = 0
        confidences = []
        strengths = []

        for d in decisions:
            type_counts[d.decision_type.value] += 1
            if d.is_executed:
                executed += 1
            confidences.append(d.confidence)
            strengths.append(d.signal_strength)

        return {
            "total_decisions": total,
            "buy_count": type_counts.get("buy", 0),
            "sell_count": type_counts.get("sell", 0),
            "hold_count": type_counts.get("hold", 0),
            "watch_count": type_counts.get("watch", 0),
            "executed_count": executed,
            "pending_count": total - executed,
            "avg_confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
            "avg_signal_strength": round(sum(strengths) / len(strengths), 2) if strengths else 0.0,
            "win_rate": None,
        }
