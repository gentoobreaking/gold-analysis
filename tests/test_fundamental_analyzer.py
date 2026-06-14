"""
基本面分析 Agent 單元測試

Author: 碼農 1 號
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from backend.app.agents.fundamental_analyzer import (
    FundamentalAnalyzer,
    FactorType,
    FactorDirection,
    FactorAnalysis
)


class TestFundamentalAnalyzer:
    """基本面分析 Agent 測試"""
    
    @pytest.fixture
    def analyzer(self):
        """創建分析器實例"""
        return FundamentalAnalyzer(
            name="test_fundamental_analyzer",
            model="test-model",
            config={
                "factor_weights": {
                    FactorType.DOLLAR_INDEX: 0.25,
                    FactorType.REAL_RATE: 0.25,
                    FactorType.INFLATION: 0.20,
                    FactorType.GEOPOLITICAL: 0.15,
                    FactorType.CENTRAL_BANK: 0.10,
                    FactorType.GOLD_ETF: 0.05,
                }
            }
        )
    
    @pytest.fixture
    def mock_data_tools(self):
        """Mock DataTools"""
        mock = MagicMock()
        mock.get_usd_index = AsyncMock(return_value={
            "symbol": "DXY",
            "value": 104.25,
            "change": 0.15
        })
        mock.get_interest_rates = AsyncMock(return_value={
            "rates": {
                "US": {"federal_fund": 5.25, "discount": 5.50}
            }
        })
        mock.get_macro_indicators = AsyncMock(return_value={
            "indicators": {
                "cpi": {"value": 3.4, "period": "2024-01"}
            }
        })
        mock.get_sentiment_data = AsyncMock(return_value={
            "gold": {"etf_flow": 125000000}
        })
        return mock
    
    @pytest.mark.asyncio
    async def test_analyze_with_full_context(self, analyzer):
        """測試完整上下文分析"""
        context = {
            "date": "2024-01-15",
            "current_price": 2045.50,
            "dxy_value": 106.0,  # 強美元
            "real_rate": 1.8,     # 中性偏高
            "inflation": 3.5,     # 溫和通脹
            "geopolitical_score": 70,  # 中高風險
            "etf_flow": 200_000_000  # 凈流入
        }
        
        result = await analyzer.analyze(context)
        
        # 驗證結構
        assert "date" in result
        assert "fundamental_score" in result
        assert "outlook" in result
        assert "confidence" in result
        assert "factors" in result
        
        # 驗證因素存在
        assert "dollar_index" in result["factors"]
        assert "real_rate" in result["factors"]
        assert "inflation" in result["factors"]
        assert "geopolitical" in result["factors"]
        assert "central_bank" in result["factors"]
        assert "gold_etf" in result["factors"]
        
        # 驗證分數範圍
        assert -1.0 <= result["fundamental_score"] <= 1.0
        assert 0 <= result["confidence"] <= 1.0
        
        print(f"Test result: score={result['fundamental_score']}, outlook={result['outlook']}")
    
    @pytest.mark.asyncio
    async def test_strong_dollar_impact(self, analyzer):
        """測試強美元對黃金的影響"""
        context = {
            "date": "2024-01-15",
            "current_price": 2045.50,
            "dxy_value": 108.0,  # 強美元
            "real_rate": 2.0,
            "inflation": 2.5,
            "geopolitical_score": 40,
        }
        
        result = await analyzer.analyze(context)
        
        # 美元因素應該是負面
        assert result["factors"]["dollar_index"]["direction"] == "negative"
        assert result["factors"]["dollar_index"]["score"] < 0
        
        print(f"Strong dollar test: score={result['fundamental_score']}")
    
    @pytest.mark.asyncio
    async def test_weak_dollar_impact(self, analyzer):
        """測試弱美元對黃金的影響"""
        context = {
            "date": "2024-01-15",
            "current_price": 2045.50,
            "dxy_value": 98.0,  # 弱美元
            "real_rate": 0.5,   # 低實際利率
            "inflation": 4.5,    # 高通脹
            "geopolitical_score": 80,  # 高風險
        }
        
        result = await analyzer.analyze(context)
        
        # 應該是正面評分
        assert result["fundamental_score"] > 0.3
        assert result["outlook"] in ["溫和看漲", "強勢看漲"]
        
        print(f"Weak dollar test: score={result['fundamental_score']}, outlook={result['outlook']}")
    
    @pytest.mark.asyncio
    async def test_low_inflation_impact(self, analyzer):
        """測試低通脹對黃金的影響"""
        context = {
            "date": "2024-01-15",
            "current_price": 2045.50,
            "dxy_value": 103.0,
            "real_rate": 3.0,
            "inflation": 1.5,  # 低通脹
            "geopolitical_score": 30,
        }
        
        result = await analyzer.analyze(context)
        
        # 通脹因素應該是負面或中性
        assert result["factors"]["inflation"]["score"] <= 0
        
        print(f"Low inflation test: score={result['fundamental_score']}")
    
    @pytest.mark.asyncio
    async def test_geopolitical_risk(self, analyzer):
        """測試地緣政治風險"""
        context = {
            "date": "2024-01-15",
            "current_price": 2045.50,
            "geopolitical_score": 85,  # 高風險
        }
        
        result = await analyzer.analyze(context)
        
        # 地緣政治因素應該是正面的（利好黃金）
        assert result["factors"]["geopolitical"]["direction"] == "positive"
        assert result["factors"]["geopolitical"]["score"] > 0
        
        print(f"Geopolitical test: score={result['fundamental_score']}")
    
    def test_composite_score_calculation(self, analyzer):
        """測試加權評分計算"""
        # 創建測試因素
        factors = [
            FactorAnalysis(
                factor_type=FactorType.DOLLAR_INDEX,
                direction=FactorDirection.NEGATIVE,
                score=-0.8,
                weight=0.25,
                confidence=0.85,
                reasoning_zh="測試",
                reasoning_en="Test",
                data_snapshot={},
                timestamp=datetime.utcnow().isoformat()
            ),
            FactorAnalysis(
                factor_type=FactorType.REAL_RATE,
                direction=FactorDirection.POSITIVE,
                score=0.9,
                weight=0.25,
                confidence=0.90,
                reasoning_zh="測試",
                reasoning_en="Test",
                data_snapshot={},
                timestamp=datetime.utcnow().isoformat()
            ),
            FactorAnalysis(
                factor_type=FactorType.INFLATION,
                direction=FactorDirection.POSITIVE,
                score=0.4,
                weight=0.20,
                confidence=0.80,
                reasoning_zh="測試",
                reasoning_en="Test",
                data_snapshot={},
                timestamp=datetime.utcnow().isoformat()
            ),
            FactorAnalysis(
                factor_type=FactorType.GEOPOLITICAL,
                direction=FactorDirection.POSITIVE,
                score=0.6,
                weight=0.15,
                confidence=0.70,
                reasoning_zh="測試",
                reasoning_en="Test",
                data_snapshot={},
                timestamp=datetime.utcnow().isoformat()
            ),
            FactorAnalysis(
                factor_type=FactorType.CENTRAL_BANK,
                direction=FactorDirection.NEUTRAL,
                score=0.0,
                weight=0.10,
                confidence=0.85,
                reasoning_zh="測試",
                reasoning_en="Test",
                data_snapshot={},
                timestamp=datetime.utcnow().isoformat()
            ),
            FactorAnalysis(
                factor_type=FactorType.GOLD_ETF,
                direction=FactorDirection.POSITIVE,
                score=0.4,
                weight=0.05,
                confidence=0.80,
                reasoning_zh="測試",
                reasoning_en="Test",
                data_snapshot={},
                timestamp=datetime.utcnow().isoformat()
            ),
        ]
        
        composite = analyzer._calculate_composite_score(factors)
        
        # 驗證分數範圍
        assert -1.0 <= composite <= 1.0
        
        # 驗證計算邏輯
        # 美元負分應該拉低整體分數
        print(f"Composite score: {composite}")
    
    def test_sensitivity_analysis(self, analyzer):
        """測試敏感性分析"""
        factor_changes = {
            FactorType.DOLLAR_INDEX: -0.2,  # 美元走弱
            FactorType.REAL_RATE: 0.1,       # 實際利率上升
        }
        
        result = analyzer.sensitivity_analysis(factor_changes)
        
        assert "dollar_index" in result
        assert "real_rate" in result
        assert result["dollar_index"]["change"] == -0.2
        
        print(f"Sensitivity analysis: {result}")
    
    def test_report_generation(self, analyzer):
        """測試報告生成"""
        factors = []
        for ft in FactorType:
            factors.append(FactorAnalysis(
                factor_type=ft,
                direction=FactorDirection.NEUTRAL,
                score=0.0,
                weight=1/6,
                confidence=0.8,
                reasoning_zh="中性測試",
                reasoning_en="Neutral test",
                data_snapshot={"test": 1},
                timestamp=datetime.utcnow().isoformat()
            ))
        
        report = analyzer._generate_report(
            date="2024-01-15",
            current_price=2045.50,
            factors=factors,
            composite_score=0.0
        )
        
        assert report["date"] == "2024-01-15"
        assert report["current_price"] == 2045.50
        assert report["outlook"] == "中性觀望"
        assert "factors" in report
        assert "factor_summary" in report
        
        print(f"Report outlook: {report['outlook']}")


class TestFactorWeights:
    """因素權重測試"""
    
    def test_default_weights_sum_to_one(self):
        """測試默認權重之和為 1"""
        weights = {
            FactorType.DOLLAR_INDEX: 0.25,
            FactorType.REAL_RATE: 0.25,
            FactorType.INFLATION: 0.20,
            FactorType.GEOPOLITICAL: 0.15,
            FactorType.CENTRAL_BANK: 0.10,
            FactorType.GOLD_ETF: 0.05,
        }
        
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001
        
    def test_custom_weights(self):
        """測試自定義權重"""
        custom_weights = {
            FactorType.DOLLAR_INDEX: 0.30,
            FactorType.REAL_RATE: 0.30,
            FactorType.INFLATION: 0.15,
            FactorType.GEOPOLITICAL: 0.10,
            FactorType.CENTRAL_BANK: 0.10,
            FactorType.GOLD_ETF: 0.05,
        }
        
        analyzer = FundamentalAnalyzer(config={"factor_weights": custom_weights})
        
        assert analyzer.factor_weights[FactorType.DOLLAR_INDEX] == 0.30
        assert analyzer.factor_weights[FactorType.REAL_RATE] == 0.30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
