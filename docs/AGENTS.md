# Gold Analysis Agents - 使用文檔

本系統採用 OpenClaw Agent Framework，實現多 Agent 協作的黃金分析決策系統。

## 架構概述

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentCoordinator                         │
│                  (協作管理器)                                │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ DataCollector │   │TechnicalAnalyst│   │Fundamental...│
│   Agent       │   │    Agent      │   │    Agent     │
└───────────────┘   └───────────────┘   └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               Analysis Pipeline                             │
│  數據收集 → 技術分析 → 基本面分析 → 風險評估 → 決策推薦      │
└─────────────────────────────────────────────────────────────┘
```

## 快速開始

### 1. 初始化 Agent 系統

```python
from backend.app.agents import AgentCoordinator
from backend.app.agents.base import GoldAnalysisAgent
from backend.app.tools import DataTools, AnalysisTools
from backend.app.config import load_config

# 載入配置
config = load_config("backend/app/config/agents.yaml")

# 初始化工具
data_tools = DataTools()
analysis_tools = AnalysisTools()

# 初始化協調器
coordinator = AgentCoordinator()
```

### 2. 執行完整分析流程

```python
import asyncio

async def analyze_gold():
    # 準備輸入數據
    input_data = {
        "symbol": "XAUUSD",
        "date": "2024-01-15",
        "period": "1d"
    }
    
    # 執行 pipeline
    result = await coordinator.run_pipeline(input_data)
    
    return result

# 運行
result = asyncio.run(analyze_gold())
```

## 核心模塊

### Agent 基類 (`agents/base.py`)

所有專業 Agent 的基類，提供：
- 標準化接口 `analyze()`
- 預處理/後處理鉤子
- 配置管理
- 日誌記錄

```python
class MyAgent(GoldAnalysisAgent):
    async def analyze(self, context):
        # 實現具體邏輯
        return {"result": "analysis output"}
```

### 協調器 (`agents/coordinator.py`)

管理多個 Agent 的協作：
- 註冊/註銷 Agent
- 按順序執行 Pipeline
- 結果彙總
- 中間件支持

```python
# 註冊 Agent
coordinator.register_agent(data_collector_agent)
coordinator.register_agent(technical_analyst_agent)

# 執行特定階段
result = await coordinator.run_stage(
    PipelineStage.TECHNICAL_ANALYSIS,
    input_data
)

# 執行完整流程
result = await coordinator.run_pipeline(data)
```

### 工具模塊 (`tools/`)

#### DataTools - 數據獲取

```python
# 獲取黃金價格
price = await data_tools.get_gold_price("2024-01-15")

# 獲取市場數據
market_data = await data_tools.get_market_data("XAUUSD", "1d")

# 獲取歷史數據
history = await data_tools.get_historical_prices(
    "XAUUSD", "2024-01-01", "2024-01-15"
)

# 獲取宏觀數據
macro = await data_tools.get_macro_indicators("US")
```

#### AnalysisTools - 技術分析

```python
# 移動平均線
ma_20 = await analysis_tools.calculate_ma(prices, 20)
ma_50 = await analysis_tools.calculate_ma(prices, 50)

# RSI
rsi = await analysis_tools.calculate_rsi(prices, 14)

# MACD
macd = await analysis_tools.calculate_macd(prices)

# 布林帶
bb = await analysis_tools.calculate_bollinger_bands(prices, 20, 2.0)

# 支撐/阻力位
sr = await analysis_tools.find_support_resistance(prices)

# 趨勢分析
trend = await analysis_tools.analyze_trend(prices)
```

## 配置管理

### 環境變量覆蓋

配置文件支持環境變量：

```bash
export OPENCLAW_MODEL=qclaw/modelroute
export OPENCLAW_TEMPERATURE=0.5
```

### YAML 配置

```yaml
agents:
  technical_analyst:
    model: ${OPENCLAW_MODEL:-qclaw/modelroute}
    temperature: 0.5
```

## Pipeline 階段

| 階段 | Agent 角色 | 輸出 |
|------|-----------|------|
| 數據收集 | data_collector | 原始市場數據 |
| 技術分析 | technical_analyst | 技術指標、信號 |
| 基本面分析 | fundamental_analyst | 宏觀影響、價值評估 |
| 風險評估 | risk_assessor | 風險等級、預警 |
| 決策推薦 | decision_maker | 買/賣/持有建議 |

## 擴展開發

### 添加新的 Agent

```python
from backend.app.agents.base import GoldAnalysisAgent

class MyCustomAgent(GoldAnalysisAgent):
    def __init__(self):
        super().__init__(
            name="my_custom_agent",
            role="custom_role",
            temperature=0.5
        )
    
    async def analyze(self, context):
        # 自定義邏輯
        return {"custom_result": "..."}

# 註冊到協調器
coordinator.register_agent(MyCustomAgent())
```

### 添加新的工具

```python
from backend.app.tools import AnalysisTools

class CustomAnalysisTools(AnalysisTools):
    async def calculate_my_indicator(self, data):
        # 自定義指標計算
        pass
```

## 常見問題

### Q: 如何只執行特定階段？

```python
result = await coordinator.run_pipeline(
    data,
    stages=[PipelineStage.DATA_COLLECTION, PipelineStage.TECHNICAL_ANALYSIS]
)
```

### Q: 如何跳過某些階段？

```python
result = await coordinator.run_pipeline(
    data,
    skip_stages=[PipelineStage.FUNDAMENTAL_ANALYSIS]
)
```

### Q: 如何添加日誌的中間件？

```python
async def logging_middleware(stage, context, result):
    print(f"Stage {stage} completed")
    
coordinator.add_middleware(logging_middleware)
```

## 目錄結構

```
backend/app/
├── agents/
│   ├── __init__.py
│   ├── base.py          # GoldAnalysisAgent 基類
│   └── coordinator.py   # AgentCoordinator 協調器
│
├── tools/
│   ├── __init__.py
│   ├── data_tools.py    # 數據獲取工具
│   └── analysis_tools.py # 技術分析工具
│
└── config/
    └── agents.yaml      # Agent 配置文件
```
