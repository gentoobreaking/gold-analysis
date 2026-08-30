---
id: T054
project: gold-analysis
source_project: gold-analysis-core
title: 建立測試基礎設施與覆蓋率基線
assignee: "dsh"
priority: high
type: feature
status: pending
created: 2025-08-28
updated: 2025-08-28
estimate: 1-2週
depends_on: []
github_issue: ""
---

## 目標
建立完整的測試基礎設施，達到 ≥ 80% 覆蓋率基線，為後續重構提供安全網。

## 驗收標準
- [ ] 配置 pytest + pytest-asyncio + pytest-cov
- [ ] 建立 `tests/conftest.py` 共享 fixtures (db_session, client, mock_data)
- [ ] 建立單元測試：services/, indicators/, models/, validators/
- [ ] 建立整合測試：API endpoints, database operations
- [ ] 覆蓋率門檻：`--cov-fail-under=80` 在 CI 中強制
- [ ] 加入 mutation testing (mutmut) 基線
- [ ] 產出測試報告 (HTML + XML for CI)

## 備註
- 優先測試核心業務邏輯：技術指標計算、風險指標、訊號生成
- 使用 `factory_boy` / `faker` 生成測試數據
- Mock 外部 API (yahoo finance, 金價 API) 避免測試不穩定
