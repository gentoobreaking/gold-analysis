# 程式碼庫統一（Codebase Consolidation）

> **規範來源（single source of truth）= `backend/app/`**

本專案曾同時存在兩套平行程式碼：根目錄的 legacy 模組與規範化的
`backend/app/`。為避免重複 bug 與維護混亂，確立 **`backend/app` 為唯一規範來源**，
根目錄 legacy 模組已標記 `@deprecated`，不應用於新開發。

## 盤點與對應表

| 根目錄 legacy 模組 | 能力 | `backend/app` 對應 | 狀態 |
| --- | --- | --- | --- |
| `agents/data_collector.py` (`DataCollectorAgent`) | 數據聚合/收集 | `app/services/data_sources/*` + `app/agents/*` | 已涵蓋（結構不同） |
| `data_adapters/bot_adapter.py` (`BotBankAdapter`) | 台銀黃金存摺資料 | `app/services/data_sources/*` | 部分（需確認） |
| `data_adapters/yahoo_finance_adapter.py` (`YahooFinanceAdapter`) | Yahoo 行情 | `app/services/data_sources/*` (finnhub/fred/alpha_vantage) | 已涵蓋 |
| `db/database.py` (`Database`) | SQLite DB helper | `app/db/*` (postgres/influxdb/redis) | 已涵蓋 |
| `schedulers/price_scheduler.py` (`PriceScheduler`) | cron 排程 | `app/main.py` `AsyncIOScheduler` | 已涵蓋 |
| `scripts/gold_monitor.py` | Telegram 黃金監控腳本 | `app/main.py` + `app/services` | 已被取代（獨立腳本） |
| `backend_mvp/server.py` | FastAPI MVP | `app/main.py` | 已涵蓋 |
| `ml_train_test.py` | ML 訓練冒煙測試 | 直接 import `backend.app.ml.*` | 使用規範來源（保留） |

## 依賴確認

- `backend/app` **不** import 任何根目錄 legacy 模組（已 grep 確認）。
- 唯一引用 `backend.app` 的根目錄檔案是 `ml_train_test.py`，且其為「使用」規範來源，
  並非重複實作，故保留。
- 根目錄 `tests/`（test_data_collector.py、test_alpaca_adapter.py 等）仍測試 legacy 模組；
  屬舊測試套件，標記 deprecated 後不強制遷移，但新測試應以 `backend/tests/` 為主。

## 後續動作（建議，非本任務強制）

- 若確認 `BotBankAdapter` 仍有獨占能力，應遷入 `app/services/data_sources/`。
- 可視情況將 legacy 模組移入 `legacy/` 目錄，進一步與啟動路徑隔離。
- T058/T059 清理時可一併移除根目錄 `tests/` 中對已棄用模組的測試。
