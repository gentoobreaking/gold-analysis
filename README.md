# Gold Analysis

黃金價格多維度決策輔助系統 — 核心功能（FastAPI 後端 + React/TS 前端 + 多代理分析管線）

> **共享資料庫（方案 B）**：本專案已移除自建 PostgreSQL，`DATABASE_URL` 指向共享 `twquant_shared`
>（`tw-quant-db` 專案的 `tw-quant-db:5432/twquant_shared`）。GOLD 價格來自 `core.daily_prices`
>（`symbol='GOLD'`），不再自建 `gold_analysis.db` / 獨立 postgres。啟動前需先起 `tw-quant-db` 與
> 共享網路 `tw-quant-network`（見 Quick Start 與 共享資料庫 章節）。

## 專案簡介

Gold Analysis 是一個黃金價格多維度決策輔助系統，提供價格分析、趨勢預測、
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
## 共享資料庫（方案 B — tw-quant-db）

> **不再自建 postgres**：早期 `gold_analysis.db` / 獨立 PostgreSQL 已移除。所有持久化資料改由
> `tw-quant-db` 專案統一提供（`twquant_shared` 資料庫）。

### 連接方式

| 項目 | 值 |
|------|-----|
| `DATABASE_URL` | `postgresql+asyncpg://twquant:<password>@tw-quant-db:5432/twquant_shared`（容器內）/ `localhost:5432`（本機直連） |
| 共享網路 | `tw-quant-network`（`external: true`，與 `tw-quant-db` / `tw-quant-mcp` 共用） |
| 來源表 | `core.daily_prices (symbol='GOLD')`、`core.alerts`、`core.decisions`（`backend/app/models/*` 對應 `core` schema） |
| PriceService | `backend/app/services/price_service.py` 直接查詢 `core.daily_prices`，不再走 SQLite `price_history` |
| 健康檢查 | `GET /health` 回 `{"mode":"postgresql"}` 即表示已連上共享 DB |

`backend/app/db/config.py` 的 `Settings.database_url` 預設已指向
`postgresql+asyncpg://twquant:twquant-secret-password@localhost:5432/twquant_shared`，
容器內由 `docker-compose.yml` 覆蓋為 `@tw-quant-db:5432`。

### 為何是方案 B

- 單一真相：台股/黃金/衍生資料由 `tw-quant-db` 的 `core` schema 統一寫入（`CANONICAL`/`FALLBACK` lineage），避免多庫漂移。
- 維運簡化：`tw-quant-db` 一次 `docker compose up -d` 即完成自動種子 + 漸進回補（見下節），gold-analysis 只消費。
- 依賴圖見下方「依賴關係」。

### 自動種子 + 漸進回補（由 tw-quant-db 提供）

`tw-quant-db` 的 `docker compose up -d` 會自動觸發：

1. `tw-quant-init`（`scripts/progressive-init.py`）：若 `core.stocks` 為空，先 `seed_all_listed.py` 灌 3114 檔台股清單。
2. 依序 `POST /api/v1/backfill/trigger` 對 `tw-quant-backfill-api` 做 **兩階段** 漸進回補，每段 `--resume` 斷點續跑，`core.trading_calendar` 判定交易日，`ON CONFLICT DO UPDATE` 保冪等：
   - **階段一 — ETF 成分股先回補**：6 檔 ETF (0050/0056/00878/00919/00406A/00713) 本體 + 成分股 (60 檔去重)，`1d → 7d → 1m → 1y → 2y → 3y → 4y → 5y`
   - **階段二 — 全量回補**：3114 檔 `1d → 7d → 1m → 1y → 2y → 3y → 4y → 5y`
3. `tw-quant-backfill`（Go 服務）：MCP 多源 fallback（`local-mcp → twse-mcp → finmind-mcp → yfinance-mcp`，`coverage ≥0.7` 才寫入）補 `core.daily_prices` 的台股缺口（詳見 `tw-quant-db/docs/backfill.md`）。
> 註：上述自動回補目前覆蓋**台股**。GOLD 見下一節「GOLD 資料流與缺口處理」。

### 依賴關係

```
tw-quant-network (external: true, 先 docker network create tw-quant-network)
        │
        ├── tw-quant-mcp  ───────────── 提供 fetchers（TwseOpenAPI / FinMind）
        │         │
        │         ▼
        ├── tw-quant-db  ───────────── 擁有 twquant_shared（core.*）
        │    ├── tw-quant-db (postgres:5432)
        │    ├── tw-quant-backfill-api (8080)
        │    ├── tw-quant-init (自動 種子 3114 + 漸進 1d→5y)
        │    ├── tw-quant-backfill (7d 全市場)
        │    └── pgAdmin (8001)
        │
        └── gold-analysis  ──────────── 消費 core.daily_prices (GOLD)
             ├── gold-analysis-backend (8000, DATABASE_URL → tw-quant-db:5432)
             ├── gold-analysis-frontend (5173)
             ├── gold-analysis-redis (6379, rate limit / cache)
             └── gold-analysis-influxdb (8086, 時序資料)
```

啟動順序：`tw-quant-network` → `tw-quant-mcp` → `tw-quant-db` → `gold-analysis`（見 Quick Start）。


## Quick Start（一鍵起）

> **前置依賴**：`gold-analysis` 不再自帶 postgres，必須先起共享網路與 `tw-quant-db`，
> 否則 `DATABASE_URL` 連不上 `tw-quant-db:5432`。

```bash
# 0. 共享網路（只需一次；已存在可忽略）
docker network create tw-quant-network

# 1. 起 tw-quant-mcp（選用，但 tw-quant-db 的台股回補需要它在同一網路）
cd ~/Projects/tw-quant-mcp && docker compose up -d

# 2. 起 tw-quant-db（自動 種子 3114 + 漸進回補 1d→5y + 7d 全市場 + pgAdmin）
cd ~/Projects/tw-quant-db && docker compose up -d
# 確認健康
docker exec tw-quant-db pg_isready -U twquant -d twquant_shared
curl http://localhost:8080/health  # tw-quant-backfill-api

# 3. 起 gold-analysis（消費 twquant_shared 的 core.daily_prices GOLD）
cd ~/Projects/gold-analysis && docker compose up -d
# 或僅後端/前端
# docker compose up -d gold-analysis-backend gold-analysis-frontend

# 4. 驗證
curl http://localhost:8000/health  # → {"status":"healthy","mode":"postgresql"}
curl http://localhost:8000/docs    # Swagger
```

本機直連驗證（不經容器）：

```bash
psql "postgresql://twquant:$(cat ~/Projects/tw-quant-db/secrets/postgres_password.txt)@localhost:5432/twquant_shared" \
  -c "SELECT count(*) FROM core.daily_prices WHERE symbol='GOLD';"
# 已回補則 >0；若為 0 見「GOLD 資料流與缺口處理」
```

`docker compose down` 不會刪除 `twquant_shared` 資料；`pg_data` 留在 `tw-quant-db/pg_data`。

## 本機開發（不走 Docker）

### 環境需求

- Python 3.11+（以 `uv` 管理，見 `.python-version`）
- Node.js 18+
- `uv`（`brew install uv` 或 `pipx install uv`）
- 共享 DB 已起：`tw-quant-db` 在 `localhost:5432` 可連（見 Quick Start 步驟 0–2）

### 後端設置（uv）

```bash
cd backend
uv sync                       # 建立 .venv 並安裝 pyproject.toml 鎖定依賴
cp .env.example .env         # 已預設 DATABASE_URL → twquant_shared，無需自建 DB
# 若 tw-quant-db 在本機，.env 預設即可；容器內由 compose 覆蓋為 @tw-quant-db
uv run uvicorn app.main:app --reload
```

後端服務將在 <http://localhost:8000> 啟動（需 `tw-quant-db:5432` 可連）。

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

## GOLD 資料流與缺口處理

### 完整資料流

```
yfinance GC=F (COMEX 黃金期貨) ──► tw-quant-db/scripts/backfill_gold_yfinance.py
                                     │  (GC=F → core.daily_prices symbol='GOLD', source_role='FALLBACK')
                                     ▼
                              core.daily_prices (GOLD, PK: symbol+trade_date)
                                     │
                                     ▼
                              gold-analysis PriceService ──► /api/prices/*, /api/technicals, /health
                                     │                              ▲
                                     ▼                              │
                              indicators / ML / backtest / 前端圖表 ──┘
```

- **讀取端（gold-analysis）**：`app/services/price_service.py` → `select(DailyPrice).where(symbol='GOLD')`，
  `models/daily_price.py` 映射 `core.daily_prices`（`__table_args__={"schema":"core"}`），
  技術指標（MA/RSI/MACD/Bollinger）、回測、風控皆由此表驅動。
- **寫入端（tw-quant-db）**：黃金不屬於台股，**不在** `tw-quant-backfill` 的台股自動回補範圍；需額外執行
  `backfill_gold_yfinance.py` 以 `yfinance` 的 `GC=F` 寫入 `symbol='GOLD'`（`source='yfinance_gc_futures'`, `source_role='FALLBACK'`）。

### 現狀：core.daily_prices 有 GOLD 嗎？

> **目前 `twquant_shared` 的 `core.daily_prices` 已有 GOLD**（`SELECT count(*) WHERE symbol='GOLD'` > 6000），`backfill_gold_yfinance.py` 已執行完成；台股 3114 檔也已開始漸進回補（ETF 成分股 60 檔優先）。
> `gold-analysis` 前端/技術線圖/ML 排程已改走共享 DB `core.daily_prices`，不再依賴 `~/.qclaw/gold_monitor_pro.db` 的 SQLite `price_history`。

### 如何從 tw-quant-db 回補 GOLD 的 daily_prices（使資料流完整）

在 `tw-quant-db` 專案執行（需 `DATABASE_URL` 可連 `twquant_shared`）：

```bash
cd ~/Projects/tw-quant-db
# 方式 A：直接跑腳本（本機，period=max 全歷史）
DATABASE_URL="postgresql://twquant:$(cat secrets/postgres_password.txt)@localhost:5432/twquant_shared" \
  python scripts/backfill_gold_yfinance.py
# → Fetching GC=F, 寫入 core.daily_prices (symbol=GOLD), ON CONFLICT DO UPDATE, 批次 500

# 驗證
psql "postgresql://twquant:$(cat secrets/postgres_password.txt)@localhost:5432/twquant_shared" \
  -c "SELECT count(*), min(trade_date), max(trade_date) FROM core.daily_prices WHERE symbol='GOLD';"
# 預期：數千筆（GC=F 自 2000 年起），min ~2000-08, max 為最近交易日
```

> `source_role='FALLBACK'` 是預期值：`tw-quant-mcp` 為台股 CANONICAL 來源，不含 GOLD，故黃金標為 FALLBACK 不影響查詢。
> 後續可在 `tw-quant-db` 加 cron 每日增量（`gold.history(period="1d")` 或重跑全量冪等），或將此腳本納入 `tw-quant-init`。

### 缺口未補時的行為

- `GET /api/prices/current?symbol=GOLD` / `GET /api/technicals` 回 `ValueError: 無 GOLD 價格數據`（HTTP 404/500，視路由）。
- `main.py` 的 `run_monitor` / `run_retrain` 排程已改為 graceful skip（資料不足時不崩潰，見 T054）。
- 前端圖表無資料：請先完成上述 GOLD 回補再驗收。


## 開發指南

- API 文件：<http://localhost:8000/docs>（Swagger UI）
- 健康檢查：<http://localhost:8000/health>（回 `mode: postgresql` 即已接共享 DB）
- 排程（`run_monitor` / `run_retrain`）使用 `core.daily_prices (GOLD)` 真實資料，
  資料不足時自動跳過（graceful skip，見 T054；缺口處理見上節）。

## 認證與速率限制

- **JWT 中介層**：`app/api/middleware/auth.py` + `app/core/security.py`
  （`create_access_token` / `HTTPBearer`）。登入端點在 `app/api/routes/auth.py`。
- **JWT `sub` 型別修正**：`create_access_token` 會將 `sub` 的整數型別轉為
  字串（JWT 規範要求 `sub` 為字串），`get_current_user` 會再轉回 `int` 作為用戶 ID 查詢；
  否則 PyJWT `verify_token` 會因 `InvalidSubjectError` 直接回傳 `None` 導致 401。
- **速率限制**：`app/api/middleware/rate_limit.py`（SlowAPI）。
- 受保護的路由需要 `Authorization: Bearer <token>`。

## API 端點（部分）

- `GET /` — 服務資訊
- `GET /health` — 健康檢查
- `POST /api/auth/login` — 取得 JWT
- `GET /api/status` — 系統狀態
- `GET /api/prices/...` — 價格資料（來源 `core.daily_prices GOLD`）
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

| 變數名 | 描述 | 預設值（本機） | 容器內覆蓋 |
| -------- | ------ | -------- | -------- |
| `DATABASE_URL` | 共享 PostgreSQL（tw-quant-db）| `postgresql+asyncpg://twquant:twquant-secret-password@localhost:5432/twquant_shared` | `postgresql+asyncpg://twquant:twquant-secret-password@tw-quant-db:5432/twquant_shared`（`docker-compose.yml` 注入） |
| `GOLD_API_KEY` | 黃金數據 API 密鑰（選用，補充外部金價） | — | — |
| `ENVIRONMENT` | 運行環境 | `development` | — |
| `DEBUG` | 調試模式 | `true` | — |
| `CORS_ORIGINS` | CORS 允許來源 | `http://localhost:5173` | — |
| `HOST` / `PORT` | 服務主機 / 埠 | `0.0.0.0` / `8000` | — |
| `TRADING_ENABLED` | 啟用交易（危險） | `false` | — |
| `TRADING_DRY_RUN` | 模擬下單（不真正送出） | `true` | — |
| `NOTIFY_ENABLED` | 啟用異常通知 | `false` | — |
| `NOTIFY_EMAIL_TO` / `SMTP_*` | 郵件通知設定 | — | — |
| `NOTIFY_WEBHOOK_URL` | Webhook 通知 URL | — | — |
| `JWT_SECRET_KEY` / `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | JWT 設定 | — | — |

> `DATABASE_URL` 不再指向自建庫，密碼見 `tw-quant-db/secrets/postgres_password.txt`，`backend/.env.example` 已預設共享庫。

## 近期重點修復（任務編號）

- **T012/T014 共享 DB 切換（方案 B）**：移除自建 postgres，`DATABASE_URL` 改指 `twquant_shared`，GOLD 價格改讀 `core.daily_prices (symbol='GOLD')`；`docker-compose.yml` 改 `external: tw-quant-network`，需先起 `tw-quant-db`。GOLD 缺口由 `tw-quant-db/scripts/backfill_gold_yfinance.py`（`GC=F` → `FALLBACK`）一次性回補（`ON CONFLICT DO UPDATE`）。
- **T053** `ml/model_monitor.py`：`_load_latest_model()` 回傳 `(model, latest)` 元組修正。
- **T054** `main.py` 排程：改用 `core.daily_prices (GOLD)` 真實資料，不足時 graceful skip（原 `price_history.local_buy` 已替換）。
- **T055** `trading/execution.py` + `core/config.py`：雙重交易開關（enabled + dry_run）+ 風控斷路器。
- **T056** 通知：`services/notify.py`（SMTP/Webhook，env-gated）；`data_tools.get_sentiment_data`
  改抓真實 alternative.me 恐貪指數，失敗降級為 `available=False`。
- **T057** 雙程式碼庫收斂：根目錄舊模組標記 `@deprecated`，規範來源 = `backend/app`。
- **T060** 可重現環境：`uv` + `pyproject.toml` + `uv.lock`（Python 3.12）。

## Git 工作流程

1. 功能分支：`git checkout -b feature/功能名稱`
2. 提交：`git commit -m "feat: 描述"`

---

## License

本專案採用 **Apache License 2.0** 授權。僅供個人量化研究與教育用途，不構成投資建議。

## 貢獻指南

歡迎提交 Issue 和 Pull Request。
