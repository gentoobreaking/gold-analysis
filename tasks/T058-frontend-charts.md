---
id: T058
project: gold-analysis
source_project: gold-analysis-core
title: 前端圖表深度優化 - TradingView 級體驗
assignee: "dsh"
priority: high
type: feature
status: pending
created: 2025-08-28
updated: 2025-08-28
estimate: 3-4週
depends_on: []
github_issue: ""
---

## 目標
將前端圖表升級至 TradingView 專業級體驗，支援多圖表聯動、繪圖工具、指標模板、自定義佈局。

## 驗收標準
- [ ] 核心圖表庫：`lightweight-charts` 進階用法
    - [ ] 多 pane 聯動 (主圖 + 成交量 + 指標子圖)
    - [ ] 同步十字光標、時間軸縮放、滾動
    - [ ] 多時間框架快速切換 (1m, 5m, 15m, 1h, 4h, 1d, 1w, 1M)
- [ ] 繪圖工具面板：
    - [ ] 趨勢線、水平線、垂直線、射線、平行通道
    - [ ] 斐波那契回撤/延伸、黃金分割
    - [ ] 文字標註、箭頭、圖形
    - [ ] 繪圖持久化 (localStorage / 後端同步)
- [ ] 指標系統：
    - [ ] 內建 30+ 指標 (MA, EMA, MACD, RSI, BB, KD, MACD, Ichimoku, VWAP 等)
    - [ ] 指標參數面板即時調整
    - [ ] 自定義指標編輯器 (TypeScript/Pine Script-like DSL)
    - [ ] 指標模板儲存/匯入/匯出/分享
- [ ] 佈局管理：
    - [ ] 拖拽調整面板大小、分割
    - [ ] 工作區儲存/載入/分享 (URL state encoding)
    - [ ] 多標的同屏對比 (同步/非同步模式)
- [ ] 效能優化：
    - [ ] 虛擬化渲染 (大數據集 > 10k bars)
    - [ ] WebWorker 計算指標不阻塞主執行緒
    - [ ] 按需載入數據 (懶加載歷史 K 線)
- [ ] 鍵盤快捷鍵 / 命令面板 (⌘K)

## 備註
- 狀態管理：Zustand / Jotai (輕量、原子化)
- 圖表配置序列化：JSON Schema 驗證
- 考慮整合 `trading-vue-js` 作為備選 (功能更豐富但體積大)