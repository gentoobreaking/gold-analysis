# Gold Analysis Core

黃金價格多維度決策輔助系統 — 核心功能（FastAPI 後端 + React/TS 前端 + 多代理分析管線）

> **規範來源（canonical source）**：所有啟動/運作的程式碼都在 `backend/app/`。
> 倉庫根目錄的 `agents/`、`data_adapters/`、`db/`、`schedulers/`、`scripts/`、`backend_mvp/`
> 與 `ml_train_test.py` 是**舊版/實驗性**模組，僅 `ml_train_test.py` 會引用 `backend.app`。
> 詳見 [`docs/CODEBASE_CONSOLIDATION.md`](docs/CODEBASE_CONSOLIDATION.md)。

## 專案簡介

Gold Analysis Core 是一個黃金價格多維度決策輔助系統，提供價格分析、趨勢預測、
技術指標計算、多代理協作分析、ML 模型訓練/監控、以及（預設關閉的）交易介面卡，
協助投資者做出更明智的決策。

## 技術棧

### 後端（`backend/app`）

- **框架**：Python 3.11+ / FastAPI（非同步）
- **排程**：APScheduler `AsyncIOScheduler`
- **資料處理**：Pandas, NumPy, SciPy, scikit-learn
- **ORM / DB**：SQLAlchemy 2.x（async）、asyncpg、InfluxDB client、Redis
- **HTTP 客戶端**：httpx, aiohttp, requests（交易介面卡用）
- **認證**：JWT（passlib / PyJWT）+ SlowAPI 速率限制
- **依賴管理**：`uv` + `pyproject.toml` + `uv.lock`（可重現環境，見 T060）

### 前端（`frontend`）

- **框架**：React 18+ / TypeScript
- **建構**：Vite
- **圖表**：TradingView Lightweight Charts
- **HTTP**：Axios

### Agent

- **語言**：Python（`backend/app/agents/` 內建多代理協調器）
- 外部編排平台（OpenClaw）由根目錄舊版 `agents/` 處理，已標記 `@deprecated`。

## 專案結構（規範來源 `backend/app`）

```
gold-analysis/
├── backend/
│   ├── app/                    # ★ 唯一規範來源
│   │   ├── main.py             # FastAPI 主程式 + APScheduler 排程
│   │   ├── api/                # API 路由 / 中介層 (auth, rate_limit)
│   │   ├── agents/             # 多代理管線 (base, coordinator, 5 個分析 agent)
│   │   ├── analysis/           # 績效分析
│   │   ├── ml/                 # 特徵工程 / 訓練 / 監控 / 再訓練 / ops
│   │   ├── models/             # SQLAlchemy / Pydantic 模型
│   │   ├── services/           # 業務邏輯 (price, decision, backtest, notify ...)
│   │   ├── trading/            # 交易介面卡 (alpaca/exchange) + 風控 + 執行
│   │   ├── risk/               # 風險指標 / 部位
│   │   ├── tools/              # DataTools / AnalysisTools
│   │   ├── realtime/           # WebSocket
│   │   ├── core/               # config (pydantic-settings) + security (JWT)
│   │   ├── db/                 # postgres / influxdb / redis
│   │   └── indicators/         # 技術指標 (MA, RSI, MACD, Bollinger ...)
│   ├── pyproject.toml          # uv 依賴來源（取代 requirements.txt）
│   ├── uv.lock                 # 可重現鎖定檔
│   ├── .python-version         # 3.12
│   ├── requirements.txt        # 舊版清單（僅供參考）
│   └── .env.example
├── frontend/                   # React + Vite
├── docs/                       # 文件
├── tasks/                      # 任務書（本機，未納版控）
└── README.md
```

## 快速開始

### 環境需求

- Python 3.11+（以 `uv` 管理，見 `.python-version`）
- Node.js 18+
- `uv`（`brew install uv` 或 `pipx install uv`）

### 後端設置（uv）

```bash
cd backend
uv sync                       # 建立 .venv 並安裝 pyproject.toml 鎖定依賴
cp .env.example .env         # 編輯 .env 填入實際配置
uv run uvicorn app.main:app --reload
```

後端服務將在 <http://localhost:8000> 啟動。

### 執行測試

```bash
cd backend
uv sync --extra dev          # 安裝 pytest / pytest-asyncio / aiosqlite
uv run pytest                # 或：.venv/bin/python -m pytest
```

> 注意：請直接用 `uv run` / `.venv/bin/python`，避免沿用外部 `VIRTUAL_ENV`
> 而載入到錯誤的直譯器（見 T060）。

### 前端設置

```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

## 開發指南

- API 文件：<http://localhost:8000/docs（Swagger> UI）
- 健康檢查：<http://localhost:8000/health>
- 排程（`run_monitor` / `run_retrain`）使用 `price_history.local_buy` 真實資料，
  資料不足時自動跳過（graceful skip）。

## 認證與速率限制

- **JWT 中介層**：`app/api/middleware/auth.py` + `app/core/security.py`
  （`create_access_token` / `HTTPBearer`）。登入端點在 `app/api/routes/auth.py`。
- **速率限制**：`app/api/middleware/rate_limit.py`（SlowAPI）。
- 受保護的路由需要 `Authorization: Bearer <token>`。

## API 端點（部分）

- `GET /` — 服務資訊
- `GET /health` — 健康檢查
- `POST /api/auth/login` — 取得 JWT
- `GET /api/status` — 系統狀態
- `GET /api/prices/...` — 價格資料
- `GET /api/decisions/...` — 決策建議
- `GET /api/alerts/...` — 告警
- `POST /api/backtest/...` — 回測（見 `app/api/routes/backtest.py`）
- （更多端點見 `app/api/routes/`）

## 交易介面卡（預設關閉）

交易功能預設**完全關閉**，需顯式啟用：

- `trading_enabled=false`（預設）→ 任何下單直接回傳 `trading_disabled`。
- `trading_dry_run=true`（預設）→ 下單僅模擬，不真正送出。
- 實單模式另有 `RiskRuleEngine` 斷路器把關（見 `app/trading/execution.py`、`risk_rules.py`）。
- 風控阻擋 / 監控異常會透過 `app/services/notify.py` 推送通知（SMTP / Webhook，需配置啟用）。

## 環境變數（選要）

| 變數名 | 描述 | 預設值 |
| -------- | ------ | -------- |
| `DATABASE_URL` | 資料庫連接 URL | — |
| `GOLD_API_KEY` | 黃金數據 API 密鑰 | — |
| `ENVIRONMENT` | 運行環境 | `development` |
| `DEBUG` | 調試模式 | `true` |
| `CORS_ORIGINS` | CORS 允許來源 | `http://localhost:5173` |
| `HOST` / `PORT` | 服務主機 / 埠 | `0.0.0.0` / `8000` |
| `TRADING_ENABLED` | 啟用交易（危險） | `false` |
| `TRADING_DRY_RUN` | 模擬下單（不真正送出） | `true` |
| `NOTIFY_ENABLED` | 啟用異常通知 | `false` |
| `NOTIFY_EMAIL_TO` / `SMTP_*` | 郵件通知設定 | — |
| `NOTIFY_WEBHOOK_URL` | Webhook 通知 URL | — |
| `JWT_SECRET_KEY` / `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | JWT 設定 | — |

## 近期重點修復（任務編號）

- **T053** `ml/model_monitor.py`：`_load_latest_model()` 回傳 `(model, latest)` 元組修正。
- **T054** `main.py` 排程：改用 `price_history.local_buy` 真實資料，不足時 skip。
- **T055** `trading/execution.py` + `core/config.py`：雙重交易開關（enabled + dry_run）+ 風控斷路器。
- **T056** 通知：`services/notify.py`（SMTP/Webhook，env-gated）；`data_tools.get_sentiment_data`
  改抓真實 alternative.me 恐貪指數，失敗降級為 `available=False`。
- **T057** 雙程式碼庫收斂：根目錄舊模組標記 `@deprecated`，規範來源 = `backend/app`。
- **T060** 可重現環境：`uv` + `pyproject.toml` + `uv.lock`（Python 3.12）。

## Git 工作流程

1. 功能分支：`git checkout -b feature/功能名稱`
2. 提交：`git commit -m "feat: 描述"`
3. 推送並建立 PR

---

## License

本專案採用 **Apache License 2.0** 授權。僅供個人量化研究與教育用途，不構成投資建議。

## 貢獻指南

歡迎提交 Issue 和 Pull Request。
