---
id: T055
project: gold-analysis
source_project: gold-analysis-core
title: 開發向量化回測引擎
assignee: "dsh"
priority: high
type: feature
status: pending
created: 2025-08-28
updated: 2025-08-28
estimate: 3-4週
depends_on: ["T054"]
github_issue: ""
---

## 目標
建立高效能向量化回測引擎，支援策略快速驗證、參數優化、走向前分析。

## 驗收標準
- [ ] 核心引擎：基於 `vectorbt` 或 `numba` 加速的向量化回測
- [ ] 資料介面：統一 `BacktestDataFeed` 抽象層 (支援 OHLCV、基本面、另類數據)
- [ ] 策略 DSL：聲明式策略定義 (entry/exit/sizing/risk rules)
- [ ] 績效指標：完整指標集 (Sharpe, Sortino, Calmar, MaxDD, Win Rate, Profit Factor, Expectancy, Tail Ratio)
- [ ] 走向前分析：Anchored/Rolling Walk-Forward Optimization
- [ ] 蒙地卡羅模擬：路徑依賴性分析、信心區間
- [ ] 參數優化：Optuna 整合 (TPE/CMA-ES)，支援多目標優化
- [ ] 視覺化：權益曲線、回撤瀑布、逐筆交易標記、月度/年度績效熱力圖
- [ ] 報告輸出：HTML/PDF 完整回測報告 (含參數敏感度、穩健性分析)

## 備註
- 架構分層：Engine → Strategy → DataFeed → Analyzer → Reporter
- 避免前視偏差：嚴格分離 in-sample / out-of-sample
- 交易成本建模：spread + commission + slippage (固定/動態)
- 並行化：多策略/多參數/多標的並行回測 (joblib / ray)