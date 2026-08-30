---
id: T059
project: gold-analysis
source_project: gold-analysis-core
title: 數據管線重構 - 增量 ETL 與品質監控
assignee: "dsh"
priority: medium
type: refactor
status: pending
created: 2025-08-28
updated: 2025-08-28
estimate: 2-3週
depends_on: ["T053"]
github_issue: ""
---

## 目標
重構數據收集管線，實現增量式 ETL、多源融合、自動化品質監控與告警。

## 驗收標準
- [ ] 抽象層：`DataAdapter` 介面 (fetch, validate, transform, upsert)
- [ ] 內建適配器：Yahoo Finance, Alpha Vantage, Twelve Data, FRED, CFTC COT
- [ ] 增量同步：CDC 模式 (依據 `updated_at` / `last_synced` watermark)
- [ ] 多源融合：優先級解析、衝突檢測、缺口填補 (前向/後向/插值)
- [ ] 品質規則 (Great Expectations / 自建)：
    - [ ] 完整性：缺失值比率、時間序列連續性
    - [ ] 一致性：OHLC 邏輯 (H≥O,C,L; L≤O,C,H)、價格跳變閾值
    - [ ] 時效性：數據延遲 SLA 監控
    - [ ] 異常值：Z-score, IQR, Isolation Forest
- [ ] 監控儀表板：數據鮮度、品質分數趨勢、異常事件時間線
- [ ] 告警：品質分數跌破閾值 → Webhook/Email/Telegram
- [ ] 重跑機制：手動/排程觸發歷史區間重算
- [ ] 調度：APScheduler / Celery Beat 管理 cron 任務

## 備註
- 時序數據庫建議遷移至 **TimescaleDB** (PostgreSQL extension)
- 考慮 `dbt` 做下游轉換層 (若分析邏輯複雜)
- 適配器插件化：新增數據源無需修改核心管線