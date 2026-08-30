---
id: T061
project: gold-analysis
source_project: gold-analysis-core
title: Docker 化與 CI/CD 部署管線
assignee: "dsh"
priority: high
type: feature
status: pending
created: 2025-08-28
updated: 2025-08-28
estimate: 2-3週
depends_on: ["T053", "T054"]
github_issue: ""
---

## 目標
建立生產級容器化部署管線，支援開發/測試/生產環境一致性部署。

## 驗收標準
- [ ] Dockerfile 多階段構建：
    - [ ] 後端：`python:3.11-slim` → builder (deps) → runtime (gunicorn + uvicorn workers)
    - [ ] 前端：`node:20-alpine` → builder (npm ci + build) → nginx:alpine (靜態服務 + SPA fallback + gzip/brotli)
    - [ ] 非 root user、最小權限、健康檢查端點
- [ ] docker-compose.yml：
    - [ ] `dev`：熱重載、本地 DB、Mock 服務
    - [ ] `test`：CI 專用、測試 DB、並行測試
    - [ ] `prod`：多副本、資源限制、日誌驅動、Secrets 管理
- [ ] 服務編排：
    - [ ] PostgreSQL + TimescaleDB (時序數據)
    - [ ] Redis (快取、Session、Celery Broker、Pub/Sub)
    - [ ] Celery Worker (回測、報告、數據同步) + Celery Beat
    - [ ] Nginx 反向代理 (SSL 終止、Rate Limit、WebSocket 升級)
    - [ ] Prometheus + Grafana + Alertmanager (監控堆疊)
    - [ ] Loki + Promtail (日誌聚合)
- [ ] GitHub Actions / GitLab CI：
    - [ ] `lint` → `test` → `build` → `security-scan` → `deploy-staging` → `deploy-prod` (manual approval)
    - [ ] 矩陣測試：Python 3.10/3.11, Node 18/20
    - [ ] 依賴快取、Docker layer cache
    - [ ] Trivy/Gruyve 掃描鏡像漏洞
- [ ] 環境變數管理：`.env.*` + `direnv` / `doppler` / `1password-cli`
- [ ] 資料庫遷移：Alembic 自動生成 + CI 檢查 + 部署前運行
- [ ] 零停機部署：藍綠 / 滾動更新、健康檢查就緒後切流量

## 備註
- 生產環境建議 Kubernetes (K3s / EKS / GKE) 或 Docker Swarm
- Secret 管理：SOPS + age / HashiCorp Vault / Cloud 秘密管理
- 備份策略：PG_dump 定時 + WAL-G (PITR)