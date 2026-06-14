"""
Agent 協作管理器 - 協調多個專業 Agent 完成完整分析流程

負責：
1. 註冊和管理各類專業 Agent
2. 協調執行分析流程（數據收集 -> 技術分析 -> 基本面分析 -> 風險評估 -> 決策推薦）
3. 結果彙總和傳遞
"""

from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import logging
import asyncio
from datetime import datetime

from .base import GoldAnalysisAgent

logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    """分析流程階段枚舉"""
    DATA_COLLECTION = "data_collection"
    TECHNICAL_ANALYSIS = "technical_analysis"
    FUNDAMENTAL_ANALYSIS = "fundamental_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    DECISION_RECOMMENDATION = "decision_recommendation"
    
    @property
    def order(self) -> int:
        """獲取階段順序"""
        order_map = {
            PipelineStage.DATA_COLLECTION: 1,
            PipelineStage.TECHNICAL_ANALYSIS: 2,
            PipelineStage.FUNDAMENTAL_ANALYSIS: 3,
            PipelineStage.RISK_ASSESSMENT: 4,
            PipelineStage.DECISION_RECOMMENDATION: 5,
        }
        return order_map[self]
    
    @property
    def required_role(self) -> str:
        """獲取對應的 Agent 角色"""
        role_map = {
            PipelineStage.DATA_COLLECTION: "data_collector",
            PipelineStage.TECHNICAL_ANALYSIS: "technical_analyst",
            PipelineStage.FUNDAMENTAL_ANALYSIS: "fundamental_analyst",
            PipelineStage.RISK_ASSESSMENT: "risk_assessor",
            PipelineStage.DECISION_RECOMMENDATION: "decision_maker",
        }
        return role_map[self]


class AgentCoordinator:
    """
    Agent 協作管理器
    
    統一協調多個專業 Agent，按順序執行完整分析流程。
    
    Example:
        coordinator = AgentCoordinator()
        coordinator.register_agent(data_collector)
        coordinator.register_agent(technical_analyst)
        
        result = await coordinator.run_pipeline({"symbol": "GC", "date": "2024-01-15"})
    """
    
    def __init__(self):
        """初始化協調器"""
        self.agents: Dict[str, GoldAnalysisAgent] = {}
        self._execution_history: List[Dict[str, Any]] = []
        self._middleware: List[Callable] = []
        
        logger.info("AgentCoordinator initialized")
    
    def register_agent(self, agent: GoldAnalysisAgent) -> None:
        """
        註冊 Agent
        
        Args:
            agent: GoldAnalysisAgent 實例
            
        Raises:
            ValueError: 如果 Agent 名稱已存在
        """
        if agent.name in self.agents:
            raise ValueError(f"Agent with name '{agent.name}' already registered")
        
        self.agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name} (role: {agent.role})")
    
    def unregister_agent(self, name: str) -> bool:
        """
        註銷 Agent
        
        Args:
            name: Agent 名稱
            
        Returns:
            是否成功註銷
        """
        if name in self.agents:
            del self.agents[name]
            logger.info(f"Unregistered agent: {name}")
            return True
        return False
    
    def get_agent(self, name: str) -> Optional[GoldAnalysisAgent]:
        """根據名稱獲取 Agent"""
        return self.agents.get(name)
    
    def get_agents_by_role(self, role: str) -> List[GoldAnalysisAgent]:
        """根據角色獲取所有匹配的 Agent"""
        return [agent for agent in self.agents.values() if agent.role == role]
    
    def add_middleware(self, middleware: Callable) -> None:
        """
        添加中間件（在每個階段執行前後調用）
        
        Args:
            middleware: 中間件函數，簽名: async def mw(stage, context, result)
        """
        self._middleware.append(middleware)
        logger.debug(f"Added middleware: {middleware.__name__}")
    
    async def _run_middleware(
        self, 
        stage: PipelineStage, 
        context: Dict[str, Any], 
        result: Optional[Dict[str, Any]] = None,
        is_pre: bool = True
    ) -> None:
        """執行所有中間件"""
        for mw in self._middleware:
            try:
                if is_pre:
                    await mw(stage, context, None)
                else:
                    await mw(stage, context, result)
            except Exception as e:
                logger.warning(f"Middleware {mw.__name__} error: {e}")
    
    async def run_stage(
        self, 
        stage: PipelineStage, 
        input_data: Dict[str, Any],
        agent_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        執行指定階段
        
        Args:
            stage: 流程階段
            input_data: 輸入數據
            agent_name: 指定使用的 Agent 名稱（可選）
            
        Returns:
            階段執行結果
            
        Raises:
            ValueError: 找不到對應的 Agent
        """
        # 查找 Agent
        if agent_name:
            agent = self.get_agent(agent_name)
            if not agent:
                raise ValueError(f"Agent '{agent_name}' not found")
        else:
            agents = self.get_agents_by_role(stage.required_role)
            if not agents:
                raise ValueError(f"No agent found for role '{stage.required_role}'")
            agent = agents[0]  # 使用第一個匹配的 Agent
        
        logger.info(f"Running stage [{stage.value}] with agent [{agent.name}]")
        
        # 執行預處理鉤子
        processed_input = await agent.preprocess(input_data)
        
        # 執行分析
        result = await agent.analyze(processed_input)
        
        # 執行後處理鉤子
        final_result = await agent.postprocess(result)
        
        return {
            "stage": stage.value,
            "agent": agent.name,
            "result": final_result,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def run_pipeline(
        self, 
        data: Dict[str, Any],
        stages: Optional[List[PipelineStage]] = None,
        skip_stages: Optional[List[PipelineStage]] = None
    ) -> Dict[str, Any]:
        """
        執行完整分析流程
        
        按順序執行：數據收集 -> 技術分析 -> 基本面分析 -> 風險評估 -> 決策推薦
        
        Args:
            data: 初始輸入數據
            stages: 指定要執行的階段順序（可選）
            skip_stages: 跳過的階段（可選）
            
        Returns:
            完整分析結果
        """
        # 默認執行所有階段
        if stages is None:
            stages = list(PipelineStage)
        
        # 處理跳過的階段
        if skip_stages:
            stages = [s for s in stages if s not in skip_stages]
        
        # 按順序排序
        stages = sorted(stages, key=lambda s: s.order)
        
        logger.info(f"Starting pipeline with {len(stages)} stages: {[s.value for s in stages]}")
        
        results = {}
        context = {"initial_data": data, "pipeline_results": {}}
        
        for stage in stages:
            try:
                # 執行預處理中間件
                await self._run_middleware(stage, context, is_pre=True)
                
                # 執行階段
                stage_result = await self.run_stage(stage, context)
                results[stage.value] = stage_result
                
                # 更新上下文（供後續階段使用）
                context["pipeline_results"][stage.value] = stage_result["result"]
                
                # 執行後處理中間件
                await self._run_middleware(stage, context, stage_result["result"], is_pre=False)
                
            except Exception as e:
                logger.error(f"Stage [{stage.value}] failed: {e}")
                results[stage.value] = {
                    "stage": stage.value,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        # 記錄執行歷史
        self._execution_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "stages": list(results.keys()),
            "success": all("error" not in r for r in results.values())
        })
        
        return {
            "pipeline_status": "completed",
            "stages": results,
            "summary": self._generate_summary(results)
        }
    
    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """生成結果摘要"""
        return {
            "total_stages": len(results),
            "successful_stages": sum(1 for r in results.values() if "error" not in r),
            "failed_stages": sum(1 for r in results.values() if "error" in r)
        }
    
    def get_execution_history(self) -> List[Dict[str, Any]]:
        """獲取執行歷史"""
        return self._execution_history.copy()
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有已註冊的 Agent"""
        return [agent.to_dict() for agent in self.agents.values()]
    
    def __repr__(self) -> str:
        return f"<AgentCoordinator(agents={len(self.agents)})>"
