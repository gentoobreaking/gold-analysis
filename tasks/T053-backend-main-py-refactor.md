---
id: T053
project: gold-analysis
source_project: gold-analysis-core
title: 重構 backend/app/main.py - 拆分為模組化架構
assignee: "dsh"
priority: high
type: refactor
status: pending
created: 2025-08-28
updated: 2025-08-28
estimate: 3-4週
depends_on: []
github_issue: ""
---

## 目標
將 22,687 行的單一 `main.py` 拆分為清晰的模組化架構，採用 Clean Architecture 分層，提升可維護性與測試性。

## 驗收標準
- [ ] 建立 `app/api/v1/` 路由版本控制結構
- [ ] 拆分核心模組：`app/core/` (config, security, database, exceptions)
- [ ] 建立 `app/schemas/` 統一 Pydantic 模型定義
- [ ] 建立 `app/services/` 業務邏輯層（依賴注入模式）
- [ ] 建立 `app/repositories/` 資料存取層
- [ ] `main.py` 精簡為 < 200 行，僅含應用啟動、中介軟體註冊、路由掛載
- [ ] 所有現有 API 端點功能不變，通過完整測試套件
- [ ] 加入 `pre-commit` hooks (ruff, mypy, black)

## 備註
- 風險：大規模重構可能引入回歸 Bug，需先建立完整測試基線
- 建議採用 **Strangler Fig Pattern** 漸進式重構，而非一次性重寫
- 參考結構：
  ```
  app/
  ├── main.py                 # < 200 行，啟動入口
  ├── core/
  │   ├── config.py          # Settings (pydantic-settings)
  │   ├── security.py        # JWT, password hashing
  │   ├── database.py        # SQLAlchemy engine/session
  │   └── exceptions.py      # 自訂例外 + 全域處理器
  ├── api/
  │   └── v1/
  │       ├── router.py      # APIRouter 聚合
  │       ├── endpoints/     # 各資源端點
  │       └── deps.py        # 依賴注入 (get_db, get_current_user)
  ├── schemas/               # Pydantic models (request/response)
  ├── services/              # Business logic (可測試、可注入)
  ├── repositories/          # Data access (SQLAlchemy/Raw SQL)
  ├── models/                # ORM models
  └── tasks/                 # Celery 異步任務
  ```
- 先建立測試覆蓋率基線（目標 ≥ 80%），再開始重構
