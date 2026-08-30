"""Decision Service - AI 決策業務邏輯

Mock 實作供測試/開發環境使用。正式環境可接入真實 AI 模型服務。
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from app.models.decision import Decision, DecisionSource, DecisionType
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class DecisionService:
    """決策服務"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_recommendation(
        self,
        user_id: int,
        symbol: str = "GOLD",
        confidence_threshold: float = 0.6,
    ) -> dict[str, Any]:
        """生成 AI 推薦（mock）。"""
        if symbol.upper() != "GOLD":
            raise ValueError(f"不支持的資產符號: {symbol}")

        # 模擬決策邏輯
        decision_type = random.choice([DecisionType.BUY, DecisionType.SELL, DecisionType.HOLD])
        signal_strength = round(random.uniform(0.5, 0.95), 2)
        confidence = round(random.uniform(0.55, 0.9), 2)

        # 確保滿足閾值
        if confidence < confidence_threshold:
            confidence = confidence_threshold + 0.05

        decision = Decision(
            user_id=user_id,
            decision_type=decision_type,
            source=DecisionSource.AI_ANALYSIS,
            asset=symbol.upper(),
            signal_strength=signal_strength,
            confidence=confidence,
            price_target=round(2000 + random.uniform(-50, 50), 2),
            stop_loss=round(2000 - random.uniform(20, 100), 2),
            reason_zh=f"基於技術指標分析，建議 {decision_type.value.upper()}。",
            reason_en=f"Based on technical analysis, {decision_type.value.upper()} is recommended.",
            model_version="v1-mock",
        )

        self.session.add(decision)
        await self.session.flush()

        # 更新 is_executed 為 False（預設）
        reasoning = f"信號強度 {signal_strength:.0%}，置信度 {confidence:.0%}。"

        # 決策可解釋性（規則決策：由決策方向合成維度評分）— T062
        try:
            from app.ml.explainer import explain_rule_decision

            direction = {
                "buy": 0.4,
                "strong_buy": 0.7,
                "hold": 0.0,
                "sell": -0.4,
                "strong_sell": -0.7,
            }.get(decision.decision_type.value, 0.0)
            explanation = explain_rule_decision(
                scores={
                    "technical": direction,
                    "fundamental": direction * 0.6,
                    "risk": -direction * 0.3,
                    "composite": direction,
                },
                weights={"technical": 0.35, "fundamental": 0.30, "risk": 0.35},
                decision_type=decision.decision_type.value,
                reasoning_zh=decision.reason_zh,
            )
        except Exception:
            explanation = None

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
            "risk_level": "medium",
            "suggestions": ["建議設定止損", "分批進場降低風險"],
            "warnings": ["模擬環境數據，實盤請謹慎"],
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

    async def get_decision_stats(self, user_id: int) -> dict[str, Any]:
        """獲取決策統計（mock）。"""
        # 查詢實際數據
        total_result = await self.session.execute(
            select(func.count()).select_from(
                select(Decision).where(Decision.user_id == user_id).subquery()
            )
        )
        total = total_result.scalar() or 0

        # 簡單統計
        type_counts = {dt.value: 0 for dt in DecisionType}
        executed = 0
        confidences = []
        strengths = []

        if total > 0:
            result = await self.session.execute(select(Decision).where(Decision.user_id == user_id))
            decisions = result.scalars().all()
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
