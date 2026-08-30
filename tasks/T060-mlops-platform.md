---
id: T060
project: gold-analysis
source_project: gold-analysis-core
title: ML 模型訓練與推理平台 (MLOps)
assignee: "dsh"
priority: medium
type: feature
status: pending
created: 2025-08-28
updated: 2025-08-28
estimate: 4-6週
depends_on: ["T054", "T055"]
github_issue: ""
---

## 目標
建立端到端 MLOps 平台：特徵工程、模型訓練、實驗追蹤、模型註冊、線上推理、監控回環。

## 驗收標準
- [ ] 特徵工程 (`ml/features/`)：
    - [ ] 技術指標特徵 (100+)、基本面特徵、宏觀特徵、另類數據特徵
    - [ ] 特徵存儲：Feast / 自建 (Parquet + SQLite/PostgreSQL 元數據)
    - [ ] 特徵版本控制、血緣追蹤
- [ ] 實驗追蹤：MLflow 整合 (自動記錄參數、指標、藝術品、模型)
- [ ] 模型訓練：
    - [ ] 任務類型：分類(漲跌)、回歸(價格/收益率)、排序(標的選優)
    - [ ] 演算法：LightGBM/XGBoost/CatBoost, TabNet, Transformer (Time Series)
    - [ ] AutoML：Optuna 搜尋空間 (架構 + 超參數)
    - [ ] 交叉驗證：Purged K-Fold / Combinatorial Purged CV (避免洩漏)
- [ ] 模型註冊：Staging → Production 推廣流程、簽名驗證、A/B Test 配置
- [ ] 線上推理：
    - [ ] FastAPI `/api/v1/ml/predict` 端點 (批次/流式)
    - [ ] 模型服務：ONNX Runtime / Triton Inference Server / 本地載入
    - [ ] 特徵即時計算 + 快取 (Redis)
    - [ ] P99 延遲 < 50ms
- [ ] 監控回環：
    - [ ] 數據漂移：PSI, KS-test, 特徵分布監控
    - [ ] 概念漂移：性能指標衰減檢測
    - [ ] 自動重訓練觸發器
- [ ] 前端：實驗比較儀表板、模型績效追蹤、特徵重要性視覺化

## 備註
- 避免前視偏差：嚴格時間序列分割、無未來數據洩漏
- 模型解釋性：SHAP 值 API、部分依賴圖
- 硬體：CPU 推理為主，GPU 訓練 (可選)