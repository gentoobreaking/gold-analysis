"""
決策推薦 Agent - Decision Recommendation Agent

綜合技術面、基本面、風險評估的分析結果，生成最終投資建議。

Author: 碼農 1 號
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging
import math

from .base import GoldAnalysisAgent

logger = logging.getLogger(__name__)


class DecisionType(str, Enum):
    """決策類型枚舉"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class PositionSize(str, Enum):
    """倉位大小枚舉"""
    MAXIMUM = "maximum"    # 80-100% 倉位
    LARGE = "large"        # 60-80% 倉位
    MEDIUM = "medium"      # 40-60% 倉位
    SMALL = "small"        # 20-40% 倉位
    MINIMUM = "minimum"    # 10-20% 倉位
    NONE = "none"          # 0% 倉位（不建議进场）


@dataclass
class TradingRecommendation:
    """交易建議"""
    decision_type: DecisionType
    position_size: PositionSize
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    confidence: float
    reasoning_zh: str
    reasoning_en: str
    timestamp: str


class DecisionRecommendationAgent(GoldAnalysisAgent):
    """
    決策推薦 Agent
    
    整合技術分析、基本面分析、風險評估的結果，
    生成最終的黃金投資建議。
    
    Example:
        agent = DecisionRecommendationAgent()
        result = await agent.analyze({
            "date": "2024-01-15",
            "current_price": 2045.50,
            "technical_analysis": {...},  # 技術分析結果
            "fundamental_analysis": {...}, # 基本面分析結果
            "risk_assessment": {...}       # 風險評估結果
        })
    """
    
    def __init__(
        self,
        name: str = "decision_recommender",
        model: str = "qclaw/modelroute",
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化決策推薦 Agent
        
        Args:
            name: Agent 名稱
            model: 模型名稱
            config: 額外配置
        """
        super().__init__(
            name=name,
            role="decision_maker",
            model=model,
            temperature=0.4,
            max_tokens=3000,
            config=config
        )
        
        # 維度權重配置
        self.dimension_weights = config.get("dimension_weights", {
            "technical": 0.35,
            "fundamental": 0.30,
            "risk": 0.35
        }) if config else {
            "technical": 0.35,
            "fundamental": 0.30,
            "risk": 0.35
        }
        
        # 止損止盈配置
        self.stop_loss_config = config.get("stop_loss", {
            "atr_multiplier": 2.0,      # ATR 倍數
            "max_loss_percent": 3.0,    # 最大虧損百分比
            "support_resistance_distance": 0.015  # 支撐阻力位距離
        }) if config else {
            "atr_multiplier": 2.0,
            "max_loss_percent": 3.0,
            "support_resistance_distance": 0.015
        }
        
        # 倉位配置
        self.position_config = config.get("position", {
            "max_position": 1.0,        # 最大倉位 (100%)
            "min_confidence": 0.5,     # 最低置信度
            "high_confidence": 0.8,     # 高置信度閾值
        }) if config else {
            "max_position": 1.0,
            "min_confidence": 0.5,
            "high_confidence": 0.8,
        }
    
    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成交易決策建議
        
        Args:
            context: 包含以下字段的字典:
                - date: 分析日期
                - current_price: 當前價格
                - technical_analysis: 技術分析結果（可選）
                - fundamental_analysis: 基本面分析結果（可選）
                - risk_assessment: 風險評估結果（可選）
                
        Returns:
            交易決策建議
        """
        logger.info(f"Generating trading decision for {context.get('date', 'unknown')}")
        
        date = context.get("date", datetime.now().strftime("%Y-%m-%d"))
        current_price = context.get("current_price", 0)
        
        # 1. 提取各維度分析結果
        technical = context.get("technical_analysis", {})
        fundamental = context.get("fundamental_analysis", {})
        risk_assessment = context.get("risk_assessment", {})
        
        # 2. 提取各維度評分
        tech_score = self._extract_score(technical, "technical_score", "trend_score")
        fund_score = self._extract_score(fundamental, "fundamental_score")
        risk_score = self._extract_score(risk_assessment, "risk_score", "risk_level_score")
        
        # 3. 計算加權綜合評分
        composite_score = self._calculate_composite_score(
            tech_score, fund_score, risk_score
        )
        
        # 4. 計算置信度
        confidence = self._calculate_confidence(
            technical, fundamental, risk_assessment
        )
        
        # 5. 確定決策類型
        decision = self._determine_decision(
            composite_score, confidence
        )
        
        # 6. 計算止損止盈位
        stop_loss, take_profit = self._calculate_stops(
            current_price, technical, risk_assessment
        )
        
        # 7. 計算風險回報比
        risk = abs(current_price - stop_loss)
        reward = abs(take_profit - current_price)
        risk_reward_ratio = round(reward / risk, 2) if risk > 0 else 0
        
        # 8. 計算建議倉位
        position_size = self._calculate_position_size(
            composite_score, confidence, risk_assessment
        )
        
        # 9. 計算目標價位
        price_target = self._calculate_price_target(
            current_price, decision, technical, fundamental
        )
        
        # 10. 生成完整理由
        reasoning = self._generate_reasoning(
            decision, composite_score, tech_score, 
            fund_score, risk_score, confidence
        )
        
        # 11. 構建最終建議
        recommendation = TradingRecommendation(
            decision_type=decision,
            position_size=position_size,
            entry_price=current_price,
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            risk_reward_ratio=risk_reward_ratio,
            confidence=round(confidence, 3),
            reasoning_zh=reasoning["zh"],
            reasoning_en=reasoning["en"],
            timestamp=datetime.utcnow().isoformat()
        )
        
        # 12. 生成完整報告
        report = self._generate_report(
            date=date,
            current_price=current_price,
            recommendation=recommendation,
            composite_score=composite_score,
            dimension_scores={
                "technical": tech_score,
                "fundamental": fund_score,
                "risk": risk_score
            },
            price_target=price_target,
            reasoning=reasoning
        )
        
        return report
    
    def _extract_score(
        self, 
        data: Dict[str, Any], 
        *keys: str
    ) -> float:
        """從數據中提取評分"""
        for key in keys:
            if key in data:
                value = data[key]
                # 如果是字符串（枚舉），轉換
                if isinstance(value, str):
                    return 0.0  # 默認值
                return float(value)
        return 0.0  # 默認中性分數
    
    def _calculate_composite_score(
        self,
        tech_score: float,
        fund_score: float,
        risk_score: float
    ) -> float:
        """
        計算加權綜合評分
        
        Args:
            tech_score: 技術分析評分 (-1 到 1)
            fund_score: 基本面分析評分 (-1 到 1)
            risk_score: 風險評估評分 (-1 到 1)
            
        Returns:
            加權評分 (-1 到 1)
        """
        # 技術分數標準化到 0-1（0=中性，1=完全多頭）
        tech_normalized = (tech_score + 1) / 2
        
        # 基本面分數標準化
        fund_normalized = (fund_score + 1) / 2
        
        # 風險分數標準化（風險低=1，風險高=0）
        risk_normalized = 1 - (risk_score + 1) / 2 if risk_score != 0 else 0.5
        
        # 加權計算
        composite = (
            tech_normalized * self.dimension_weights["technical"] +
            fund_normalized * self.dimension_weights["fundamental"] +
            risk_normalized * self.dimension_weights["risk"]
        )
        
        # 轉換回 -1 到 1 的範圍
        composite = (composite - 0.5) * 2
        
        return round(composite, 4)
    
    def _calculate_confidence(
        self,
        technical: Dict[str, Any],
        fundamental: Dict[str, Any],
        risk_assessment: Dict[str, Any]
    ) -> float:
        """計算決策置信度"""
        confidences = []
        
        # 技術分析置信度
        if "confidence" in technical:
            confidences.append(float(technical["confidence"]))
        elif "signal_strength" in technical:
            confidences.append(float(technical["signal_strength"]))
        
        # 基本面分析置信度
        if "confidence" in fundamental:
            confidences.append(float(fundamental["confidence"]))
        
        # 風險評估置信度
        if "confidence" in risk_assessment:
            confidences.append(float(risk_assessment["confidence"]))
        
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
        else:
            avg_confidence = 0.5  # 默認置信度
        
        return avg_confidence
    
    def _determine_decision(
        self,
        composite_score: float,
        confidence: float
    ) -> DecisionType:
        """根據綜合評分和置信度確定決策"""
        # 基礎決策（基於評分）
        if composite_score > 0.5:
            base_decision = DecisionType.STRONG_BUY
        elif composite_score > 0.2:
            base_decision = DecisionType.BUY
        elif composite_score > -0.2:
            base_decision = DecisionType.HOLD
        elif composite_score > -0.5:
            base_decision = DecisionType.SELL
        else:
            base_decision = DecisionType.STRONG_SELL
        
        # 置信度調整
        if confidence < self.position_config["min_confidence"]:
            # 低置信度，提高門檻
            if composite_score > 0.6:
                return DecisionType.BUY
            elif composite_score < -0.6:
                return DecisionType.SELL
            else:
                return DecisionType.HOLD
        
        return base_decision
    
    def _calculate_stops(
        self,
        current_price: float,
        technical: Dict[str, Any],
        risk_assessment: Dict[str, Any]
    ) -> tuple:
        """計算止損止盈位"""
        # 從技術分析獲取 ATR 或波動率
        atr = technical.get("atr", current_price * 0.008)  # 默認 0.8%
        
        # 從風險評估獲取最大虧損
        max_loss_pct = risk_assessment.get("max_loss_percent", 
                                           self.stop_loss_config["max_loss_percent"])
        
        # 止損位計算
        atr_stop = current_price - (atr * self.stop_loss_config["atr_multiplier"])
        percent_stop = current_price * (1 - max_loss_pct / 100)
        
        # 取更保守的止損
        stop_loss = min(atr_stop, percent_stop)
        
        # 止盈位計算
        atr_multiplier = self.stop_loss_config["atr_multiplier"]
        
        # 根據趨勢方向調整止盈
        trend = technical.get("trend", "neutral")
        if trend == "bullish":
            # 多頭：止盈設在 ATR 倍數上方
            take_profit = current_price + (atr * atr_multiplier * 2)
        elif trend == "bearish":
            # 空頭：止盈設在 ATR 倍數下方
            take_profit = current_price - (atr * atr_multiplier * 2)
        else:
            # 中性：止盈設在 1.5 倍
            take_profit = current_price + (atr * atr_multiplier * 1.5)
        
        return stop_loss, take_profit
    
    def _calculate_position_size(
        self,
        composite_score: float,
        confidence: float,
        risk_assessment: Dict[str, Any]
    ) -> PositionSize:
        """計算建議倉位"""
        # 基礎倉位（基於評分）
        if composite_score > 0.5 and confidence > self.position_config["high_confidence"]:
            base_position = PositionSize.LARGE
        elif composite_score > 0.3:
            base_position = PositionSize.MEDIUM
        elif composite_score > 0.1:
            base_position = PositionSize.SMALL
        elif composite_score > -0.1:
            base_position = PositionSize.NONE
        elif composite_score > -0.3:
            base_position = PositionSize.MINIMUM
        else:
            base_position = PositionSize.NONE
        
        # 風險調整
        risk_level = risk_assessment.get("risk_level", "medium")
        if risk_level == "high":
            # 高風險，降低倉位
            if base_position == PositionSize.LARGE:
                base_position = PositionSize.MEDIUM
            elif base_position == PositionSize.MEDIUM:
                base_position = PositionSize.SMALL
        elif risk_level == "low":
            # 低風險，可以提高倉位
            if base_position == PositionSize.SMALL:
                base_position = PositionSize.MEDIUM
        
        return base_position
    
    def _calculate_price_target(
        self,
        current_price: float,
        decision: DecisionType,
        technical: Dict[str, Any],
        fundamental: Dict[str, Any]
    ) -> Dict[str, float]:
        """計算目標價位"""
        targets = {}
        
        # 短期目標（1-2週）
        if decision in [DecisionType.STRONG_BUY, DecisionType.BUY]:
            # 多頭：目標 = 當前 + ATR * 倍數
            atr = technical.get("atr", current_price * 0.008)
            targets["short_term"] = round(current_price + atr * 3, 2)
            targets["medium_term"] = round(current_price * 1.03, 2)  # 3%
            targets["long_term"] = round(current_price * 1.05, 2)   # 5%
        elif decision in [DecisionType.STRONG_SELL, DecisionType.SELL]:
            # 空頭：目標 = 當前 - ATR * 倍數
            atr = technical.get("atr", current_price * 0.008)
            targets["short_term"] = round(current_price - atr * 3, 2)
            targets["medium_term"] = round(current_price * 0.97, 2)  # -3%
            targets["long_term"] = round(current_price * 0.95, 2)     # -5%
        else:
            # 持有：區間震蕩
            targets["short_term"] = round(current_price * 1.01, 2)
            targets["medium_term"] = current_price
            targets["long_term"] = round(current_price * 1.02, 2)
        
        return targets
    
    def _generate_reasoning(
        self,
        decision: DecisionType,
        composite_score: float,
        tech_score: float,
        fund_score: float,
        risk_score: float,
        confidence: float
    ) -> Dict[str, str]:
        """生成決策理由"""
        # 中文理由
        zh_parts = []
        
        if decision in [DecisionType.STRONG_BUY, DecisionType.BUY]:
            zh_parts.append("技術面與基本面形成共振")
            if tech_score > 0.3:
                zh_parts.append("技術指標顯示明確多頭趨勢")
            if fund_score > 0.2:
                zh_parts.append("基本面因素支撐金價")
            if risk_score < 0.3:
                zh_parts.append("風險回報比具吸引力")
        elif decision == DecisionType.HOLD:
            zh_parts.append("多空因素膠著")
            zh_parts.append("建議觀望等待明確方向")
        else:
            zh_parts.append("風險因素大于機會")
            if tech_score < -0.3:
                zh_parts.append("技術形態偏弱")
            if fund_score < 0:
                zh_parts.append("基本面支撐不足")
        
        zh_parts.append(f"綜合評分: {composite_score:.2f}，置信度: {confidence:.1%}")
        
        zh_reasoning = "。".join(zh_parts)
        
        # 英文理由
        en_parts = []
        
        if decision in [DecisionType.STRONG_BUY, DecisionType.BUY]:
            en_parts.append("Technical and fundamental factors are aligned")
            if confidence > 0.7:
                en_parts.append("High confidence in the bullish outlook")
            en_parts.append(f"Composite score: {composite_score:.2f}")
        elif decision == DecisionType.HOLD:
            en_parts.append("Mixed signals warrant caution")
            en_parts.append("Holding recommended until trend clarifies")
        else:
            en_parts.append("Risk factors outweigh opportunities")
            en_parts.append(f"Composite score: {composite_score:.2f}")
        
        en_reasoning = ". ".join(en_parts)
        
        return {
            "zh": zh_reasoning,
            "en": en_reasoning
        }
    
    def _generate_report(
        self,
        date: str,
        current_price: float,
        recommendation: TradingRecommendation,
        composite_score: float,
        dimension_scores: Dict[str, float],
        price_target: Dict[str, float],
        reasoning: Dict[str, str]
    ) -> Dict[str, Any]:
        """生成完整分析報告"""
        
        # 決策翻譯
        decision_map = {
            DecisionType.STRONG_BUY: ("強烈買入", "Strong Buy"),
            DecisionType.BUY: ("買入", "Buy"),
            DecisionType.HOLD: ("持有", "Hold"),
            DecisionType.SELL: ("賣出", "Sell"),
            DecisionType.STRONG_SELL: ("強烈賣出", "Strong Sell"),
        }
        
        # 倉位翻譯
        position_map = {
            PositionSize.MAXIMUM: ("極重倉 (80-100%)", "Maximum (80-100%)"),
            PositionSize.LARGE: ("重倉 (60-80%)", "Large (60-80%)"),
            PositionSize.MEDIUM: ("中等倉位 (40-60%)", "Medium (40-60%)"),
            PositionSize.SMALL: ("輕倉 (20-40%)", "Small (20-40%)"),
            PositionSize.MINIMUM: ("試探性倉位 (10-20%)", "Minimum (10-20%)"),
            PositionSize.NONE: ("不建議进场", "No Position"),
        }
        
        report = {
            "date": date,
            "current_price": current_price,
            
            # 決策摘要
            "decision": {
                "type": recommendation.decision_type.value,
                "type_zh": decision_map[recommendation.decision_type][0],
                "type_en": decision_map[recommendation.decision_type][1],
                "position_size": recommendation.position_size.value,
                "position_size_zh": position_map[recommendation.position_size][0],
                "position_size_en": position_map[recommendation.position_size][1],
                "confidence": recommendation.confidence,
            },
            
            # 進場與風險控制
            "entry": {
                "entry_price": recommendation.entry_price,
                "stop_loss": recommendation.stop_loss,
                "stop_loss_percent": round(
                    (recommendation.entry_price - recommendation.stop_loss) / 
                    recommendation.entry_price * 100, 2
                ),
                "take_profit": recommendation.take_profit,
                "take_profit_percent": round(
                    (recommendation.take_profit - recommendation.entry_price) / 
                    recommendation.entry_price * 100, 2
                ),
                "risk_reward_ratio": recommendation.risk_reward_ratio,
            },
            
            # 目標價位
            "targets": {
                "short_term": price_target["short_term"],
                "medium_term": price_target["medium_term"],
                "long_term": price_target["long_term"],
            },
            
            # 分項評分
            "scores": {
                "composite": composite_score,
                "technical": round(dimension_scores["technical"], 4),
                "fundamental": round(dimension_scores["fundamental"], 4),
                "risk": round(dimension_scores["risk"], 4),
            },
            
            # 維度權重
            "weights": self.dimension_weights,
            
            # 理由
            "reasoning": {
                "zh": recommendation.reasoning_zh,
                "en": recommendation.reasoning_en,
            },
            
            # 風險提示
            "risk_warning": self._generate_risk_warning(recommendation),
            
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(
            f"Decision generated: {recommendation.decision_type.value} "
            f"at {current_price}, confidence: {recommendation.confidence:.1%}"
        )
        
        return report
    
    def _generate_risk_warning(
        self,
        recommendation: TradingRecommendation
    ) -> Dict[str, str]:
        """生成風險提示"""
        warnings_zh = []
        warnings_en = []
        
        # 置信度風險
        if recommendation.confidence < 0.6:
            warnings_zh.append("置信度中等，建議控制倉位")
            warnings_en.append("Moderate confidence - consider position sizing")
        
        # 止損風險
        stop_pct = abs(recommendation.entry_price - recommendation.stop_loss) / recommendation.entry_price
        if stop_pct > 0.03:
            warnings_zh.append(f"止損幅度較大 ({stop_pct:.1%})，需注意資金管理")
            warnings_en.append(f"Large stop loss ({stop_pct:.1%}) - manage position carefully")
        
        # 風險回報比風險
        if recommendation.risk_reward_ratio < 1.5:
            warnings_zh.append(f"風險回報比 ({recommendation.risk_reward_ratio}:1) 偏低")
            warnings_en.append(f"Risk/reward ratio ({recommendation.risk_reward_ratio}:1) is below optimal")
        
        # 倉位風險
        if recommendation.position_size in [PositionSize.MAXIMUM, PositionSize.LARGE]:
            warnings_zh.append("重倉操作，務必設置止損")
            warnings_en.append("Large position - always use stop loss")
        
        return {
            "zh": warnings_zh,
            "en": warnings_en
        }
