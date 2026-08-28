# Gold Analysis Agents - 使用文檔

> 本文件描述 **規範來源** `backend/app/agents/` 內建的多代理協作管線。
> 根目錄舊版 `agents/`（OpenClaw 編排）已標記 `@deprecated`，請勿在新開發中使用。

本系統在 `backend/app` 內實作多 Agent 協作的黃金分析決策管線。

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
from app.agents import AgentCoordinator
from app.agents.base import GoldAnalysisAgent
from app.tools import DataTools, AnalysisTools
from app.core.config import get_core_settings

# 透過 pydantic-settings 讀取配置（環境變數 > .env > 預設值）
settings = get_core_settings()

# 初始化工具
data_tools = DataTools()
analysis_tools = AnalysisTools()

# 初始化協調器
coordinator = AgentCoordinator()
```

> 注意：本專案**沒有** `load_config()`，也沒有 `backend.app.config` 模組；
> 配置統一由 `app.core.config.get_core_settings()`（pydantic-settings）提供。
> Agent 的 YAML 設定在 `backend/app/config/agents.yaml`。

### 2. 執行完整分析流程

```python
import asyncio

async def analyze_gold():
    input_data = {
        "symbol": "XAUUSD",
        "date": "2024-01-15",
        "period": "1d",
    }
    result = await coordinator.run_pipeline(input_data)
    return result

result = asyncio.run(analyze_gold())
```

## 核心模塊

### Agent 基類 (`app/agents/base.py`)

所有專業 Agent 的基類，提供：

- 標準化接口 `analyze()`
- 預處理/後處理鉤子
- 配置管理
- 日誌記錄

```python
class MyAgent(GoldAnalysisAgent):
    async def analyze(self, context):
        return {"result": "analysis output"}
```

### 協調器 (`app/agents/coordinator.py`)

管理多個 Agent 的協作：

- 註冊/註銷 Agent
- 按順序執行 Pipeline
- 結果彙總
- 中間件支持

```python
coordinator.register_agent(data_collector_agent)
coordinator.register_agent(technical_analyst_agent)
result = await coordinator.run_stage(PipelineStage.TECHNICAL_ANALYSIS, input_data)
result = await coordinator.run_pipeline(data)
```

### 工具模塊 (`app/tools/`)

#### DataTools - 數據獲取 (`app/tools/data_tools.py`)

```python
price = await data_tools.get_gold_price("2024-01-15")
market_data = await data_tools.get_market_data("XAUUSD", "1d")
history = await data_tools.get_historical_prices("XAUUSD", "2024-01-01", "2024-01-15")
macro = await data_tools.get_macro_indicators("US")
# 情緒：真實 alternative.me 恐貪指數（失敗降級 available=False）
sentiment = await data_tools.get_sentiment_data()
```

#### AnalysisTools - 技術分析 (`app/tools/analysis_tools.py`)

```python
ma_20 = await analysis_tools.calculate_ma(prices, 20)
rsi = await analysis_tools.calculate_rsi(prices, 14)
macd = await analysis_tools.calculate_macd(prices)
bb = await analysis_tools.calculate_bollinger_bands(prices, 20, 2.0)
sr = await analysis_tools.find_support_resistance(prices)
trend = await analysis_tools.analyze_trend(prices)
```

## 配置管理

### 環境變量覆蓋

`app.core.config` 使用 pydantic-settings，自動從環境變數與 `.env` 載入：

```bash
export DATABASE_URL=postgresql://user:pass@localhost:5432/db
export ENVIRONMENT=development
```

### YAML 配置

Agent 管線設定位於 `backend/app/config/agents.yaml`：

```yaml
agents:
  technical_analyst:
    model: ${OPENCLAW_MODEL:-qclaw/modelroute}
    temperature: 0.5
```

## Pipeline 階段

| 階段 | Agent 角色 | 輸出 |
| ------ | ----------- | ------ |
| 數據收集 | data_collector | 原始市場數據 |
| 技術分析 | technical_analyst | 技術指標、信號 |
| 基本面分析 | fundamental_analyst | 宏觀影響、價值評估 |
| 風險評估 | risk_assessor | 風險等級、預警 |
| 決策推薦 | decision_maker | 買/賣/持有建議 |

## 擴展開發

### 添加新的 Agent

```python
from app.agents.base import GoldAnalysisAgent

class MyCustomAgent(GoldAnalysisAgent):
    def __init__(self):
        super().__init__(name="my_custom_agent", role="custom_role", temperature=0.5)

    async def analyze(self, context):
        return {"custom_result": "..."}

coordinator.register_agent(MyCustomAgent())
```

### 添加新的工具

```python
from app.tools import AnalysisTools

class CustomAnalysisTools(AnalysisTools):
    async def calculate_my_indicator(self, data):
        pass
```

## 常見問題

### Q: 如何只執行特定階段？

```python
result = await coordinator.run_pipeline(
    data, stages=[PipelineStage.DATA_COLLECTION, PipelineStage.TECHNICAL_ANALYSIS]
)
```

### Q: 如何跳過某些階段？

```python
result = await coordinator.run_pipeline(
    data, skip_stages=[PipelineStage.FUNDAMENTAL_ANALYSIS]
)
```

### Q: 如何添加日誌的中間件？

```python
async def logging_middleware(stage, context, result):
    print(f"Stage {stage} completed")

coordinator.add_middleware(logging_middleware)
```

## 目錄結構（規範來源）

```
backend/app/
├── agents/
│   ├── __init__.py
│   ├── base.py              # GoldAnalysisAgent 基類
│   ├── coordinator.py       # AgentCoordinator 協調器
│   ├── decision_recommender.py
│   ├── fundamental_analyzer.py
│   ├── risk_assessment.py
│   └── technical_analysis.py
├── tools/
│   ├── __init__.py
│   ├── data_tools.py        # 數據獲取工具
│   └── analysis_tools.py    # 技術分析工具
├── config/
│   └── agents.yaml          # Agent 配置文件
└── core/
    └── config.py            # get_core_settings()（取代舊 load_config）
```

## 認證

受保護的 API 使用 JWT（見 `app/api/middleware/auth.py` 與 `app/core/security.py`），
由 `app/api/routes/auth.py` 的登入端點核發 token。
