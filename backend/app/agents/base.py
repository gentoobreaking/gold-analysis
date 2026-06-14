"""
GoldAnalysisAgent 基類 - OpenClaw Agent 框架集成

提供黃金分析系統的基礎 Agent 抽象類，
所有專業分析 Agent（數據收集、技術分析、基本面分析等）都應繼承此類。
"""

from typing import Optional, Any, Dict
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class GoldAnalysisAgent(ABC):
    """
    黃金分析基礎 Agent
    
    定義所有專業 Agent 的通用接口和行為模式。
    
    Attributes:
        name: Agent 名稱
        role: Agent 角色（如 data_collector, technical_analyst 等）
        model: 使用的模型
        temperature: 生成溫度參數
        max_tokens: 最大 token 數
    """
    
    def __init__(
        self,
        name: str,
        role: str,
        model: str = "qclaw/modelroute",
        temperature: float = 0.5,
        max_tokens: int = 2000,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化 GoldAnalysisAgent
        
        Args:
            name: Agent 名稱
            role: Agent 角色
            model: 模型名稱
            temperature: 生成溫度 (0.0-1.0)
            max_tokens: 最大 token 數
            config: 額外配置
        """
        self.name = name
        self.role = role
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.config = config or {}
        self._initialized = False
        
        logger.info(f"Agent [{name}] initialized with role [{role}]")
    
    async def initialize(self) -> None:
        """初始化 Agent（可被子類重寫）"""
        self._initialized = True
        logger.debug(f"Agent [{self.name}] initialized")
    
    @abstractmethod
    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        核心分析接口（子類必須實現）
        
        Args:
            context: 分析上下文，包含輸入數據
            
        Returns:
            分析結果字典
        """
        pass
    
    async def preprocess(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        預處理鉤子（可被子類重寫）
        
        Args:
            data: 原始輸入數據
            
        Returns:
            處理後的數據
        """
        return data
    
    async def postprocess(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        後處理鉤子（可被子類重寫）
        
        Args:
            result: 原始分析結果
            
        Returns:
            處理後的結果
        """
        return result
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        完整執行流程：預處理 -> 分析 -> 後處理
        
        Args:
            input_data: 輸入數據
            
        Returns:
            最終分析結果
        """
        if not self._initialized:
            await self.initialize()
        
        logger.info(f"Agent [{self.name}] executing with role [{self.role}]")
        
        processed = await self.preprocess(input_data)
        result = await self.analyze(processed)
        final = await self.postprocess(result)
        
        return final
    
    def to_dict(self) -> Dict[str, Any]:
        """將 Agent 配置轉換為字典"""
        return {
            "name": self.name,
            "role": self.role,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "config": self.config
        }
    
    def __repr__(self) -> str:
        return f"<GoldAnalysisAgent(name={self.name}, role={self.role})>"
