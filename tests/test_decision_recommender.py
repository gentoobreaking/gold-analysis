"""
決策推薦 Agent 單元測試

Author: 碼農 1 號
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from backend.app.agents.decision_recommender import (
    DecisionRecommendationAgent,
    DecisionType,
    PositionSize,
    TradingRecommendation
)


class TestDecisionRecommendationAgent:
    """決策推薦 Agent 測試"""
    
    @pytest.fixture
    def agent(self):
        """創建 Agent 實例"""
        return DecisionRecommendationAgent(
            name="test_decision_agent",
            model="test-model",
            config={
                "dimension_weights": {
                    "technical": 0.35,
                    "fundamental": 0.30,
                    "risk": 0.35
                }
            }
        )
    
    @pytest.fixture
    def bullish_context(self):
        """多頭上下文"""
        return {
            "date": "2024-01-15",
            "current_price": 2050.00,
            "technical_analysis": {
                "technical_score": 0.7,
                "trend": "bullish",
                "atr": 15.0,
                "confidence": 0.85,
                "signal_strength": 0.8
            },
            "fundamental_analysis": {
                "fundamental_score": 0.5,
                "confidence": 0.80
            },
            "risk_assessment": {
                "risk_score": 0.2,
                "risk_level": "low",
                "max_loss_percent": 2.0,
                "confidence": 0.85
            }
        }
    
    @pytest.fixture
    def bearish_context(self):
        """空頭上下文"""
        return {
            "date": "2024-01-15",
            "current_price": 2050.00,
            "technical_analysis": {
                "technical_score": -0.6,
                "trend": "bearish",
                "atr": 15.0,
                "confidence": 0.80
            },
            "fundamental_analysis": {
                "fundamental_score": -0.4,
                "confidence": 0.75
            },
            "risk_assessment": {
                "risk_score": 0.6,
                "risk_level": "high",
                "max_loss_percent": 2.5,
                "confidence": 0.80
            }
        }
    
    @pytest.fixture
    def neutral_context(self):
        """中性上下文"""
        return {
            "date": "2024-01-15",
            "current_price": 2050.00,
            "technical_analysis": {
                "technical_score": 0.1,
                "trend": "neutral",
                "atr": 12.0,
                "confidence": 0.60
            },
            "fundamental_analysis": {
                "fundamental_score": 0.0,
                "confidence": 0.70
            },
            "risk_assessment": {
                "risk_score": 0.4,
                "risk_level": "medium",
                "max_loss_percent": 2.0,
                "confidence": 0.75
            }
        }
    
    @pytest.mark.asyncio
    async def test_bullish_decision(self, agent, bullish_context):
        """測試多頭決策"""
        result = await agent.analyze(bullish_context)
        
        # 驗證結構
        assert "date" in result
        assert "current_price" in result
        assert "decision" in result
        assert "entry" in result
        assert "scores" in result
        
        # 驗證決策類型
        assert result["decision"]["type"] in [
            DecisionType.STRONG_BUY.value,
            DecisionType.BUY.value
        ]
        
        # 驗證評分
        assert result["scores"]["composite"] > 0
        assert result["decision"]["confidence"] > 0.7
        
        # 驗證止損止盈
        assert result["entry"]["stop_loss"] < result["current_price"]
        assert result["entry"]["take_profit"] > result["current_price"]
        
        print(f"Bullish decision: {result['decision']['type']}, "
              f"composite={result['scores']['composite']}")
    
    @pytest.mark.asyncio
    async def test_bearish_decision(self, agent, bearish_context):
        """測試空頭決策"""
        result = await agent.analyze(bearish_context)
        
        # 驗證決策類型
        assert result["decision"]["type"] in [
            DecisionType.STRONG_SELL.value,
            DecisionType.SELL.value,
            DecisionType.HOLD.value  # 高風險可能調整為 HOLD
        ]
        
        print(f"Bearish decision: {result['decision']['type']}, "
              f"composite={result['scores']['composite']}")
    
    @pytest.mark.asyncio
    async def test_neutral_decision(self, agent, neutral_context):
        """測試中性決策"""
        result = await agent.analyze(neutral_context)
        
        # 驗證決策類型
        assert result["decision"]["type"] == DecisionType.HOLD.value
        
        print(f"Neutral decision: {result['decision']['type']}")
    
    @pytest.mark.asyncio
    async def test_low_confidence_adjustment(self, agent):
        """測試低置信度調整"""
        context = {
            "date": "2024-01-15",
            "current_price": 2050.00,
            "technical_analysis": {
                "technical_score": 0.55,
                "confidence": 0.4  # 低置信度
            },
            "fundamental_analysis": {
                "fundamental_score": 0.5,
                "confidence": 0.4
            },
            "risk_assessment": {
                "risk_score": 0.2,
                "confidence": 0.4
            }
        }
        
        result = await agent.analyze(context)
        
        # 低置信度不應產生強烈買入信號
        assert result["decision"]["type"] in [
            DecisionType.BUY.value,
            DecisionType.HOLD.value
        ]
        
        print(f"Low confidence decision: {result['decision']['type']}")
    
    def test_composite_score_calculation(self, agent):
        """測試綜合評分計算"""
        # 測試多頭
        score = agent._calculate_composite_score(0.7, 0.5, 0.2)
        assert score > 0.3
        
        # 測試空頭
        score = agent._calculate_composite_score(-0.6, -0.4, 0.6)
        assert score < -0.3
        
        # 測試中性
        score = agent._calculate_composite_score(0.1, 0.0, 0.4)
        assert -0.2 < score < 0.2
        
        print(f"Composite score tests passed")
    
    def test_decision_determination(self, agent):
        """測試決策類型判定"""
        # 強買入
        assert agent._determine_decision(0.6, 0.8) == DecisionType.STRONG_BUY
        
        # 買入
        assert agent._determine_decision(0.3, 0.7) == DecisionType.BUY
        
        # 持有
        assert agent._determine_decision(0.0, 0.6) == DecisionType.HOLD
        
        # 賣出
        assert agent._determine_decision(-0.3, 0.7) == DecisionType.SELL
        
        # 強賣出
        assert agent._determine_decision(-0.6, 0.8) == DecisionType.STRONG_SELL
        
        print("Decision determination tests passed")
    
    def test_position_size_calculation(self, agent):
        """測試倉位計算"""
        # 高評分高置信度 -> 大倉位
        position = agent._calculate_position_size(0.6, 0.85, {"risk_level": "low"})
        assert position in [PositionSize.LARGE, PositionSize.MEDIUM]
        
        # 中性評分 -> 中等倉位
        position = agent._calculate_position_size(0.2, 0.7, {"risk_level": "medium"})
        assert position == PositionSize.SMALL
        
        # 負評分 -> 無倉位
        position = agent._calculate_position_size(-0.4, 0.6, {"risk_level": "high"})
        assert position in [PositionSize.NONE, PositionSize.MINIMUM]
        
        print("Position size calculation tests passed")
    
    def test_stop_loss_calculation(self, agent):
        """測試止損計算"""
        current_price = 2050.0
        atr = 15.0
        
        # 測試止損
        stop_loss, take_profit = agent._calculate_stops(
            current_price,
            {"atr": atr, "trend": "bullish"},
            {"max_loss_percent": 2.0}
        )
        
        # 止損低於進場價
        assert stop_loss < current_price
        
        # 止盈高於進場價
        assert take_profit > current_price
        
        # 止損幅度合理
        stop_distance = current_price - stop_loss
        assert stop_distance < current_price * 0.05  # 小於 5%
        
        print(f"Stop loss: {stop_loss}, Take profit: {take_profit}")
    
    def test_price_target_calculation(self, agent):
        """測試目標價計算"""
        current_price = 2050.0
        
        # 多頭目標
        targets = agent._calculate_price_target(
            current_price,
            DecisionType.BUY,
            {"atr": 15.0},
            {}
        )
        
        assert targets["short_term"] > current_price
        assert targets["medium_term"] > current_price
        assert targets["long_term"] > current_price
        
        print(f"Targets: {targets}")
    
    def test_risk_reward_ratio(self, agent):
        """測試風險回報比"""
        # 理想情況：止損小，止盈大
        entry = 100.0
        stop = 98.0   # 2% 止損
        target = 106.0  # 6% 止盈
        
        risk = abs(entry - stop)
        reward = abs(target - entry)
        ratio = reward / risk
        
        assert ratio == 3.0  # 3:1
        
        print(f"Risk/Reward ratio: {ratio}:1")
    
    @pytest.mark.asyncio
    async def test_report_structure(self, agent, bullish_context):
        """測試報告結構"""
        result = await agent.analyze(bullish_context)
        
        # 驗證必填字段
        required_fields = [
            "date", "current_price", "decision", "entry", 
            "targets", "scores", "weights", "reasoning", "risk_warning"
        ]
        
        for field in required_fields:
            assert field in result, f"Missing field: {field}"
        
        # 驗證決策結構
        decision_fields = ["type", "position_size", "confidence"]
        for field in decision_fields:
            assert field in result["decision"], f"Missing decision field: {field}"
        
        # 驗證進場結構
        entry_fields = ["entry_price", "stop_loss", "take_profit", "risk_reward_ratio"]
        for field in entry_fields:
            assert field in result["entry"], f"Missing entry field: {field}"
        
        print("Report structure tests passed")


class TestRiskWarning:
    """風險提示測試"""
    
    @pytest.fixture
    def agent(self):
        return DecisionRecommendationAgent()
    
    def test_low_confidence_warning(self, agent):
        """測試低置信度警告"""
        recommendation = TradingRecommendation(
            decision_type=DecisionType.BUY,
            position_size=PositionSize.MEDIUM,
            entry_price=2050.0,
            stop_loss=2020.0,
            take_profit=2100.0,
            risk_reward_ratio=1.7,
            confidence=0.5,  # 低置信度
            reasoning_zh="測試",
            reasoning_en="Test",
            timestamp=datetime.utcnow().isoformat()
        )
        
        warnings = agent._generate_risk_warning(recommendation)
        
        assert len(warnings["zh"]) > 0
        assert "置信度" in warnings["zh"][0]
        
    def test_large_stop_loss_warning(self, agent):
        """測試大止損警告"""
        recommendation = TradingRecommendation(
            decision_type=DecisionType.BUY,
            position_size=PositionSize.SMALL,
            entry_price=2000.0,
            stop_loss=1900.0,  # 5% 止損
            take_profit=2100.0,
            risk_reward_ratio=2.0,
            confidence=0.75,
            reasoning_zh="測試",
            reasoning_en="Test",
            timestamp=datetime.utcnow().isoformat()
        )
        
        warnings = agent._generate_risk_warning(recommendation)
        
        # 止損大於 3% 應該有警告
        assert len(warnings["zh"]) > 0
        
    def test_low_risk_reward_warning(self, agent):
        """測試低風險回報比警告"""
        recommendation = TradingRecommendation(
            decision_type=DecisionType.BUY,
            position_size=PositionSize.SMALL,
            entry_price=2000.0,
            stop_loss=1980.0,
            take_profit=2020.0,  # 小止盈
            risk_reward_ratio=1.0,  # 低風險回報比
            confidence=0.75,
            reasoning_zh="測試",
            reasoning_en="Test",
            timestamp=datetime.utcnow().isoformat()
        )
        
        warnings = agent._generate_risk_warning(recommendation)
        
        assert any("風險回報比" in w for w in warnings["zh"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
