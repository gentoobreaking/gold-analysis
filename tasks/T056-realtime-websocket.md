---
id: T056
project: gold-analysis
source_project: gold-analysis-core
title: 即時 WebSocket 推送與通知系統
assignee: "dsh"
priority: high
type: feature
status: pending
created: 2025-08-28
updated: 2025-08-28
estimate: 2-3週
depends_on: ["T053"]
github_issue: ""
---

## 目標
建立低延遲 WebSocket 即時推送系統，支援價格流、技術訊號、風險預警多頻道訂閱。

## 驗收標準
- [ ] FastAPI WebSocket 路由：`/ws/v1/stream`
- [ ] 訂閱模式：頻道式 (price, signals, alerts, news) + 標的過濾
- [ ] 連線管理：心跳、重連、背壓控制、連線池監控
- [ ] 消息格式：Protocol Buffers / JSON (可配置)，含序列號、時間戳
- [ ] Redis Pub/Sub 做橫向擴展：多實例消息廣播
- [ ] 多渠道通知整合：
    - [ ] Telegram Bot (Webhook + 長輪詢)
    - [ ] Discord Webhook
    - [ ] Email (SMTP + 模板引擎)
    - [ ] Line Notify / Push
- [ ] 規則引擎：DSL 定義警報條件 (價格突破、指標交叉、異常波動)
- [ ] 前端：React Hook `useWebSocket` + 訂閱管理 UI
- [ ] 壓測：萬級併發連線，P99 延遲 < 100ms

## 備註
- 使用 `redis-py` + `asyncio` 非阻塞
- 考慮 `Socket.io` 相容層 (自動降級 polling)
- 訊息去重與冪等性保證
- 速率限制：Token Bucket per connection