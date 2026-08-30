---
id: T057
project: gold-analysis
source_project: gold-analysis-core
title: 風險管理模組化重構
assignee: "dsh"
priority: high
type: refactor
status: pending
created: 2025-08-28
updated: 2025-08-28
estimate: 2-3週
depends_on: ["T053"]
github_issue: ""
---

## 目標
將風險管理功能模組化，提供完整的風險度量、倉位建議、壓力測試能力。

## 驗收標準
- [ ] 風險度量核心 (`risk/metrics.py`)：
    - [ ] VaR (歷史/參數/蒙地卡羅) / CVaR
    - [ ] 最大回撤、平均回撤、回撤持續期
    - [ ] 下偏差、Sortino、Calmar、Omega Ratio
    - [ ] 尾部風險：Expected Shortfall, Extreme Value Theory (GPD fitting)
- [ ] 倉位管理 (`risk/position.py`)：
    - [ ] Kelly Criterion (全/半 Kelly)
    - [ ] Volatility Targeting
    - [ ] Risk Parity / Hierarchical Risk Parity (HRP)
    - [ ] 最大單筆/總風險限額
- [ ] 相關性監控 (`risk/correlation.py`)：
    - [ ] 動態相關性矩陣 (EWMA, DCC-GARCH)
    - [ ] 滾動相關性熱力圖 API
    - [ ] 異常相關性突變檢測
- [ ] 壓力測試 (`risk/stress.py`)：
    - [ ] 歷史情境回放 (2008, 2020, 2022 等)
    - [ ] 假設情境 (利率衝擊、美元指數暴漲、地緣政治)
    - [ ] 蒙地卡羅情境生成
- [ ] API 端點：`/api/v1/risk/*` 完整 CRUD
- [ ] 前端：風險儀表板組件 (VaR Gauge, 相關性熱力圖, 回撤瀑布圖)

## 備註
- 依賴 `arch`, `empyrical`, `cvxpy` (HRP)
- 所有計算需支援向量化批次處理
- 參數可配置化 (YAML/DB)，支援熱更新