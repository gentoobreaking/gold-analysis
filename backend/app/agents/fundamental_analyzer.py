"""
基本面分析 Agent - Fundamental Analysis Agent

評估宏觀經濟因素對黃金價格的影響：
- 美元指數因素
- 實際利率因素
- 通脹預期因素
- 地緣政治風險
- 央行政策影響
- 因素權重模型

Author: 碼農 1 號
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging

from .base import GoldAnalysisAgent

logger = logging.getLogger(__name__)


class FactorType(str, Enum):
    """因素類型枚舉"""
    DOLLAR_INDEX = "dollar_index"
    REAL_RATE = "real_rate"
    INFLATION = "inflation"
    GEOPOLITICAL = "geopolitical"
    CENTRAL_BANK = "central_bank"
    GOLD_ETF = "gold_etf"


class FactorDirection(str, Enum):
    """因素方向枚舉"""
    POSITIVE = "positive"   # 利好黃金
    NEGATIVE = "negative"  # 利空黃金
    NEUTRAL = "neutral"    # 中性


@dataclass
class FactorAnalysis:
    """單一因素分析結果"""
    factor_type: FactorType
    direction: FactorDirection
    score: float          # -1.0 到 1.0
    weight: float         # 權重 (0.0 到 1.0)
    confidence: float     # 分析置信度 (0.0 到 1.0)
    reasoning_zh: str     # 中文分析理由
    reasoning_en: str     # English reasoning
    data_snapshot: Dict[str, Any]  # 數據快照
    timestamp: str


class FundamentalAnalyzer(GoldAnalysisAgent):
    """
    基本面分析 Agent
    
    分析宏觀經濟因素對黃金價格的影響，輸出綜合基本面評分。
    
    Example:
        analyzer = FundamentalAnalyzer()
        result = await analyzer.analyze({
            "date": "2024-01-15",
            "current_price": 2045.50
        })
    """
    
    def __init__(
        self,
        name: str = "fundamental_analyzer",
        model: str = "qclaw/modelroute",
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化基本面分析 Agent
        
        Args:
            name: Agent 名稱
            model: 模型名稱
            config: 額外配置
        """
        super().__init__(
            name=name,
            role="fundamental_analyst",
            model=model,
            temperature=0.3,  #基本面分析較確定，使用較低溫度
            max_tokens=3000,
            config=config
        )
        
        # 預設因素權重（可配置）
        self.factor_weights = config.get("factor_weights", {
            FactorType.DOLLAR_INDEX: 0.25,
            FactorType.REAL_RATE: 0.25,
            FactorType.INFLATION: 0.20,
            FactorType.GEOPOLITICAL: 0.15,
            FactorType.CENTRAL_BANK: 0.10,
            FactorType.GOLD_ETF: 0.05,
        }) if config else {
            FactorType.DOLLAR_INDEX: 0.25,
            FactorType.REAL_RATE: 0.25,
            FactorType.INFLATION: 0.20,
            FactorType.GEOPOLITICAL: 0.15,
            FactorType.CENTRAL_BANK: 0.10,
            FactorType.GOLD_ETF: 0.05,
        }
        
        # 美元指數分析參數
        self.dxy_thresholds = config.get("dxy_thresholds", {
            "strong": 105,   # DXY > 105 為強美元
            "weak": 100,     # DXY < 100 為弱美元
        }) if config else {
            "strong": 105,
            "weak": 100,
        }
        
        # 實際利率分析參數
        self.real_rate_thresholds = config.get("real_rate_thresholds", {
            "positive": 1.0,   # 實際利率 < 1% 利好黃金
            "negative": 2.5,   # 實際利率 > 2.5% 利空黃金
        }) if config else {
            "positive": 1.0,
            "negative": 2.5,
        }
    
    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        執行基本面分析
        
        Args:
            context: 包含以下字段的字典:
                - date: 分析日期 (YYYY-MM-DD)
                - current_price: 當前金價
                - dxy_value: 美元指數值（可選）
                - real_rate: 實際利率（可選）
                - inflation: 通脹率（可選）
                - geopolitical_score: 地緣政治風險指數（可選）
                - cb_policy: 央行政策信息（可選）
                
        Returns:
            基本面分析結果
        """
        logger.info(f"Starting fundamental analysis for {context.get('date', 'unknown')}")
        
        date = context.get("date", datetime.now().strftime("%Y-%m-%d"))
        current_price = context.get("current_price", 0)
        
        # 1. 分析美元指數因素
        dxy_analysis = await self._analyze_dollar_index(context)
        
        # 2. 分析實際利率因素
        real_rate_analysis = await self._analyze_real_rate(context)
        
        # 3. 分析通脹預期因素
        inflation_analysis = await self._analyze_inflation(context)
        
        # 4. 分析地緣政治風險
        geopolitical_analysis = await self._analyze_geopolitical(context)
        
        # 5. 分析央行政策影響
        central_bank_analysis = await self._analyze_central_bank(context)
        
        # 6. 分析黃金 ETF 持倉變化
        etf_analysis = await self._analyze_gold_etf(context)
        
        # 收集所有因素分析
        all_factors = [
            dxy_analysis,
            real_rate_analysis,
            inflation_analysis,
            geopolitical_analysis,
            central_bank_analysis,
            etf_analysis,
        ]
        
        # 7. 計算加權綜合評分
        composite_score = self._calculate_composite_score(all_factors)
        
        # 8. 生成分析報告
        report = self._generate_report(
            date=date,
            current_price=current_price,
            factors=all_factors,
            composite_score=composite_score
        )
        
        return report
    
    async def _analyze_dollar_index(self, context: Dict[str, Any]) -> FactorAnalysis:
        """分析美元指數因素"""
        dxy_value = context.get("dxy_value")
        
        if dxy_value is None:
            # 嘗試從數據工具獲取
            from ..tools.data_tools import DataTools
            data_tools = DataTools()
            dxy_data = await data_tools.get_usd_index()
            dxy_value = dxy_data.get("value", 104.0)
        
        # 根據美元指數判斷方向
        if dxy_value > self.dxy_thresholds["strong"]:
            direction = FactorDirection.NEGATIVE
            score = -0.8  # 強美元顯著利空黃金
            reasoning = f"美元指數 DXY={dxy_value:.2f} 處於高位（>{self.dxy_thresholds['strong']}），"
            reasoning += "美元走強通常導致黃金承壓。"
        elif dxy_value < self.dxy_thresholds["weak"]:
            direction = FactorDirection.POSITIVE
            score = 0.8   # 弱美元顯著利好黃金
            reasoning = f"美元指數 DXY={dxy_value:.2f} 處於低位（<{self.dxy_thresholds['weak']}），"
            reasoning += "美元走弱通常支撐黃金上漲。"
        else:
            direction = FactorDirection.NEUTRAL
            score = 0.0   # 中性
            reasoning = f"美元指數 DXY={dxy_value:.2f} 處於中性區間。"
        
        return FactorAnalysis(
            factor_type=FactorType.DOLLAR_INDEX,
            direction=direction,
            score=score,
            weight=self.factor_weights[FactorType.DOLLAR_INDEX],
            confidence=0.85,
            reasoning_zh=reasoning,
            reasoning_en=f"DXY={dxy_value:.2f}. {'Strong USD weighs on gold.' if score < 0 else 'Weak USD supports gold.' if score > 0 else 'Neutral USD impact.'}",
            data_snapshot={"dxy_value": dxy_value},
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def _analyze_real_rate(self, context: Dict[str, Any]) -> FactorAnalysis:
        """分析實際利率因素"""
        real_rate = context.get("real_rate")
        
        if real_rate is None:
            # 嘗試從數據工具獲取
            from ..tools.data_tools import DataTools
            data_tools = DataTools()
            rates_data = await data_tools.get_interest_rates()
            nominal_rate = rates_data.get("rates", {}).get("US", {}).get("federal_fund", 5.25)
            inflation = context.get("inflation", 3.4)
            real_rate = nominal_rate - inflation
        
        # 實際利率與黃金的負相關關係
        if real_rate < self.real_rate_thresholds["positive"]:
            direction = FactorDirection.POSITIVE
            score = 0.9  # 低實際利率利好黃金
            reasoning = f"實際利率={real_rate:.2f}% 處於低位（<{self.real_rate_thresholds['positive']}%），"
            reasoning += "持有黃金的機會成本低，黃金吸引力增強。"
        elif real_rate > self.real_rate_thresholds["negative"]:
            direction = FactorDirection.NEGATIVE
            score = -0.9  # 高實際利率利空黃金
            reasoning = f"實際利率={real_rate:.2f}% 處於高位（>{self.real_rate_thresholds['negative']}%），"
            reasoning += "持有黃金的機會成本高，黃金承壓。"
        else:
            direction = FactorDirection.NEUTRAL
            score = 0.0
            reasoning = f"實際利率={real_rate:.2f}% 處於中性區間。"
        
        return FactorAnalysis(
            factor_type=FactorType.REAL_RATE,
            direction=direction,
            score=score,
            weight=self.factor_weights[FactorType.REAL_RATE],
            confidence=0.90,
            reasoning_zh=reasoning,
            reasoning_en=f"Real rate={real_rate:.2f}%. {'Low real rates support gold.' if score > 0 else 'High real rates weigh on gold.' if score < 0 else 'Neutral.'}",
            data_snapshot={"real_rate": real_rate},
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def _analyze_inflation(self, context: Dict[str, Any]) -> FactorAnalysis:
        """分析通脹預期因素"""
        inflation = context.get("inflation")
        
        if inflation is None:
            from ..tools.data_tools import DataTools
            data_tools = DataTools()
            macro_data = await data_tools.get_macro_indicators()
            inflation = macro_data.get("indicators", {}).get("cpi", {}).get("value", 3.4)
        
        # 通脹對黃金的影響
        if inflation > 4.0:
            direction = FactorDirection.POSITIVE
            score = 0.7  # 高通脹利好黃金（保值需求）
            reasoning = f"通脹率={inflation:.1f}% 高於目標，黃金作為通脹對冲工具需求增加。"
        elif inflation > 3.0:
            direction = FactorDirection.POSITIVE
            score = 0.4
            reasoning = f"通脹率={inflation:.1f}% 溫和上升，對黃金形成支撐。"
        elif inflation > 2.0:
            direction = FactorDirection.NEUTRAL
            score = 0.0
            reasoning = f"通脹率={inflation:.1f}% 接近央行目標（2%），影響中性。"
        else:
            direction = FactorDirection.NEGATIVE
            score = -0.3
            reasoning = f"通脹率={inflation:.1f}% 低於目標，存在通縮風險，黃金吸引力下降。"
        
        return FactorAnalysis(
            factor_type=FactorType.INFLATION,
            direction=direction,
            score=score,
            weight=self.factor_weights[FactorType.INFLATION],
            confidence=0.80,
            reasoning_zh=reasoning,
            reasoning_en=f"Inflation={inflation:.1f}%. {'High inflation supports gold.' if score > 0 else 'Low inflation weighs on gold.' if score < 0 else 'Neutral.'}",
            data_snapshot={"inflation": inflation},
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def _analyze_geopolitical(self, context: Dict[str, Any]) -> FactorAnalysis:
        """分析地緣政治風險"""
        geo_score = context.get("geopolitical_score")
        
        if geo_score is None:
            # 使用默認值（可從情緒數據獲取）
            from ..tools.data_tools import DataTools
            data_tools = DataTools()
            sentiment = await data_tools.get_sentiment_data()
            geo_score = 50  # 中性默認
        
        # 地緣政治風險評分（0-100）
        if geo_score >= 75:
            direction = FactorDirection.POSITIVE
            score = 0.9  # 高風險利好黃金（避險需求）
            reasoning = f"地緣政治風險指數={geo_score}（高位），市場避險情緒強烈，黃金需求大增。"
        elif geo_score >= 60:
            direction = FactorDirection.POSITIVE
            score = 0.6
            reasoning = f"地緣政治風險指數={geo_score}（中高），避險需求對黃金形成支撐。"
        elif geo_score >= 40:
            direction = FactorDirection.NEUTRAL
            score = 0.0
            reasoning = f"地緣政治風險指數={geo_score}（中性），黃金避險需求一般。"
        else:
            direction = FactorDirection.NEGATIVE
            score = -0.2
            reasoning = f"地緣政治風險指數={geo_score}（低位），風險偏好回升，避險需求減弱。"
        
        return FactorAnalysis(
            factor_type=FactorType.GEOPOLITICAL,
            direction=direction,
            score=score,
            weight=self.factor_weights[FactorType.GEOPOLITICAL],
            confidence=0.70,
            reasoning_zh=reasoning,
            reasoning_en=f"Geopolitical risk={geo_score}. {'High risk boosts gold.' if score > 0 else 'Low risk reduces safe-haven demand.' if score < 0 else 'Neutral.'}",
            data_snapshot={"geopolitical_score": geo_score},
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def _analyze_central_bank(self, context: Dict[str, Any]) -> FactorAnalysis:
        """分析央行政策影響"""
        cb_policy = context.get("cb_policy")
        
        if cb_policy is None:
            from ..tools.data_tools import DataTools
            data_tools = DataTools()
            rates_data = await data_tools.get_interest_rates()
            cb_policy = rates_data.get("rates", {}).get("US", {})
        
        fed_rate = cb_policy.get("federal_fund", 5.25) if isinstance(cb_policy, dict) else 5.25
        
        # 央行利率政策分析
        if fed_rate >= 5.0:
            direction = FactorDirection.NEGATIVE
            score = -0.5
            reasoning = f"美聯儲利率={fed_rate:.2f}% 高位，紧缩政策對黃金形成壓力。"
        elif fed_rate >= 4.0:
            direction = FactorDirection.NEUTRAL
            score = 0.0
            reasoning = f"美聯儲利率={fed_rate:.2f}% 中性，利率政策影響平衡。"
        else:
            direction = FactorDirection.POSITIVE
            score = 0.5
            reasoning = f"美聯儲利率={fed_rate:.2f}% 低位，寬鬆政策利好黃金。"
        
        return FactorAnalysis(
            factor_type=FactorType.CENTRAL_BANK,
            direction=direction,
            score=score,
            weight=self.factor_weights[FactorType.CENTRAL_BANK],
            confidence=0.85,
            reasoning_zh=reasoning,
            reasoning_en=f"Fed rate={fed_rate:.2f}%. {'High rates weigh on gold.' if score < 0 else 'Low rates support gold.' if score > 0 else 'Neutral.'}",
            data_snapshot={"fed_rate": fed_rate, "cb_policy": cb_policy},
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def _analyze_gold_etf(self, context: Dict[str, Any]) -> FactorAnalysis:
        """分析黃金 ETF 持倉變化"""
        etf_flow = context.get("etf_flow")
        
        if etf_flow is None:
            from ..tools.data_tools import DataTools
            data_tools = DataTools()
            sentiment = await data_tools.get_sentiment_data()
            etf_flow = sentiment.get("gold", {}).get("etf_flow", 0)
        
        # ETF 資金流向（正數=凈流入，負數=凈流出）
        if etf_flow > 200_000_000:  # 超過 2 億美元流入
            direction = FactorDirection.POSITIVE
            score = 0.8
            reasoning = f"黃金 ETF 凈流入 ${etf_flow/1e6:.0f}M，機構投資者增持黃金。"
        elif etf_flow > 0:
            direction = FactorDirection.POSITIVE
            score = 0.4
            reasoning = f"黃金 ETF 凈流入 ${etf_flow/1e6:.0f}M，顯示溫和增持。"
        elif etf_flow > -100_000_000:
            direction = FactorDirection.NEUTRAL
            score = 0.0
            reasoning = f"黃金 ETF 資金變動不大（${etf_flow/1e6:.0f}M）。"
        else:
            direction = FactorDirection.NEGATIVE
            score = -0.6
            reasoning = f"黃金 ETF 凈流出 ${etf_flow/1e6:.0f}M，機構投資者減持。"
        
        return FactorAnalysis(
            factor_type=FactorType.GOLD_ETF,
            direction=direction,
            score=score,
            weight=self.factor_weights[FactorType.GOLD_ETF],
            confidence=0.80,
            reasoning_zh=reasoning,
            reasoning_en=f"ETF flow=${etf_flow/1e6:.0f}M. {'Inflow supports gold.' if score > 0 else 'Outflow pressures gold.' if score < 0 else 'Neutral.'}",
            data_snapshot={"etf_flow": etf_flow},
            timestamp=datetime.utcnow().isoformat()
        )
    
    def _calculate_composite_score(self, factors: List[FactorAnalysis]) -> float:
        """
        計算加權綜合評分
        
        Args:
            factors: 所有因素分析結果列表
            
        Returns:
            加權評分 (-1.0 到 1.0)
        """
        total_weighted_score = 0.0
        total_weight = 0.0
        
        for factor in factors:
            weighted_score = factor.score * factor.weight * factor.confidence
            effective_weight = factor.weight * factor.confidence
            total_weighted_score += weighted_score
            total_weight += effective_weight
        
        if total_weight > 0:
            composite = total_weighted_score / total_weight
        else:
            composite = 0.0
        
        # 標準化到 [-1, 1]
        composite = max(-1.0, min(1.0, composite))
        
        return round(composite, 4)
    
    def _generate_report(
        self,
        date: str,
        current_price: float,
        factors: List[FactorAnalysis],
        composite_score: float
    ) -> Dict[str, Any]:
        """生成基本面分析報告"""
        
        # 判斷基本面方向
        if composite_score > 0.3:
            outlook = "強勢看漲"
            outlook_en = "Strong Bullish"
            signal = "STRONG_BUY"
        elif composite_score > 0.1:
            outlook = "溫和看漲"
            outlook_en = "Moderate Bullish"
            signal = "BUY"
        elif composite_score > -0.1:
            outlook = "中性觀望"
            outlook_en = "Neutral"
            signal = "HOLD"
        elif composite_score > -0.3:
            outlook = "溫和看跌"
            outlook_en = "Moderate Bearish"
            signal = "SELL"
        else:
            outlook = "強勢看跌"
            outlook_en = "Strong Bearish"
            signal = "STRONG_SELL"
        
        # 計算加權平均置信度
        avg_confidence = sum(f.confidence * f.weight for f in factors) / sum(f.weight for f in factors)
        
        # 構建因素摘要
        factor_summary = []
        for f in factors:
            direction_emoji = "📈" if f.direction == FactorDirection.POSITIVE else "📉" if f.direction == FactorDirection.NEGATIVE else "➡️"
            factor_summary.append({
                "factor": f.factor_type.value,
                "direction": f.direction.value,
                "score": f.score,
                "weight": f.weight,
                "summary": f"{direction_emoji} {f.reasoning_zh[:50]}..."
            })
        
        report = {
            "date": date,
            "current_price": current_price,
            "fundamental_score": composite_score,  # -1.0 到 1.0
            "outlook": outlook,
            "outlook_en": outlook_en,
            "signal": signal,
            "confidence": round(avg_confidence, 3),
            "factors": {
                "dollar_index": {
                    "score": factors[0].score,
                    "direction": factors[0].direction.value,
                    "reasoning_zh": factors[0].reasoning_zh,
                    "reasoning_en": factors[0].reasoning_en,
                    "data": factors[0].data_snapshot
                },
                "real_rate": {
                    "score": factors[1].score,
                    "direction": factors[1].direction.value,
                    "reasoning_zh": factors[1].reasoning_zh,
                    "reasoning_en": factors[1].reasoning_en,
                    "data": factors[1].data_snapshot
                },
                "inflation": {
                    "score": factors[2].score,
                    "direction": factors[2].direction.value,
                    "reasoning_zh": factors[2].reasoning_zh,
                    "reasoning_en": factors[2].reasoning_en,
                    "data": factors[2].data_snapshot
                },
                "geopolitical": {
                    "score": factors[3].score,
                    "direction": factors[3].direction.value,
                    "reasoning_zh": factors[3].reasoning_zh,
                    "reasoning_en": factors[3].reasoning_en,
                    "data": factors[3].data_snapshot
                },
                "central_bank": {
                    "score": factors[4].score,
                    "direction": factors[4].direction.value,
                    "reasoning_zh": factors[4].reasoning_zh,
                    "reasoning_en": factors[4].reasoning_en,
                    "data": factors[4].data_snapshot
                },
                "gold_etf": {
                    "score": factors[5].score,
                    "direction": factors[5].direction.value,
                    "reasoning_zh": factors[5].reasoning_zh,
                    "reasoning_en": factors[5].reasoning_en,
                    "data": factors[5].data_snapshot
                }
            },
            "factor_summary": factor_summary,
            "weights": {k.value: v for k, v in self.factor_weights.items()},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Fundamental analysis complete: score={composite_score}, outlook={outlook}")
        
        return report
    
    def sensitivity_analysis(
        self,
        factor_changes: Dict[FactorType, float]
    ) -> Dict[str, Any]:
        """
        敏感性分析：評估因素變化對最終評分的影響
        
        Args:
            factor_changes: 因素變化字典，key 為因素類型，value 為分數變化
            
        Returns:
            敏感性分析結果
        """
        results = {}
        
        for factor_type, delta in factor_changes.items():
            if factor_type not in self.factor_weights:
                continue
            
            weight = self.factor_weights[factor_type]
            impact = delta * weight
            results[factor_type.value] = {
                "original_score": 0.0,  # 假設原始分數為 0
                "change": delta,
                "weight": weight,
                "impact_on_composite": impact
            }
        
        return results
