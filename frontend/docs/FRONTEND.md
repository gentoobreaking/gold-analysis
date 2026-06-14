# Frontend Architecture - Gold Analysis System

## Overview

前端架構基於 React + Vite + TypeScript，採用組件化開發模式。

## Tech Stack

| Category | Technology | Version |
|----------|------------|---------|
| Framework | React | ^18.2.0 |
| Build Tool | Vite | ^5.0.8 |
| Language | TypeScript | ^5.3.3 |
| State Management | Zustand | ^4.4.7 |
| Routing | React Router | ^6.21.0 |
| HTTP Client | Axios | ^1.6.2 |
| Chart Library | TradingView Lightweight Charts | ^4.1.0 |
| Date Utils | date-fns | ^3.0.0 |
| Styling | Tailwind CSS | ^3.4.0 |

## Directory Structure

```
frontend/
├── src/
│   ├── components/          # 組件目錄
│   │   ├── charts/          # 圖表組件
│   │   │   └── PriceChart.tsx
│   │   ├── common/          # 通用組件（預留）
│   │   ├── layout/          # 佈局組件
│   │   │   ├── MainLayout.tsx
│   │   │   ├── Header.tsx
│   │   │   └── Sidebar.tsx
│   │   ├── pages/           # 頁面組件
│   │   │   └── Dashboard.tsx
│   │   └── trading/         # 交易相關組件（預留）
│   ├── hooks/               # 自定義 Hooks
│   │   └── index.ts
│   ├── services/            # API 服務
│   │   └── index.ts
│   ├── stores/               # 狀態管理（Zustand）
│   │   └── useGoldStore.ts
│   ├── types/               # TypeScript 類型定義
│   │   └── index.ts
│   ├── utils/               # 工具函數
│   │   └── index.ts
│   ├── styles/              # 樣式文件
│   │   └── index.css
│   ├── App.tsx              # 根組件
│   └── main.tsx             # 入口文件
├── public/
├── index.html
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
└── package.json
```

## Path Aliases

使用路徑別名簡化導入：

| Alias | Path |
|-------|------|
| `@` | `src/` |
| `@components` | `src/components` |
| `@hooks` | `src/hooks` |
| `@services` | `src/services` |
| `@stores` | `src/stores` |
| `@types` | `src/types` |
| `@utils` | `src/utils` |

## Core Components

### Layout Components

- **MainLayout**: 主佈局容器，包含 Header + Sidebar + Main Content
- **Header**: 頂部導航欄，顯示系統名稱和當前金價
- **Sidebar**: 側邊欄導航菜單

### State Management

**useGoldStore** - Zustand Store:

```typescript
interface GoldState {
  currentPrice: number;
  priceHistory: PricePoint[];
  marketData: MarketData;
  currentDecision: Decision | null;
  decisionHistory: Decision[];
  isLoading: boolean;
  error: string | null;
}
```

### Type Definitions

核心類型定義於 `src/types/index.ts`:

- `PricePoint` - 價格數據點
- `MarketData` - 市場數據結構
- `CandlestickData` - K線數據
- `Decision` - 交易決策
- `ChartConfig` - 圖表配置

## API Integration

後端 API 代理配置在 `vite.config.ts`:

```
/api/* → http://localhost:8000/*
```

主要 API 端點：
- `GET /api/market` - 獲取市場數據
- `GET /api/price` - 獲取實時價格
- `GET /api/decision` - 獲取交易決策

## Styling

使用 Tailwind CSS 配合自定義配色：

```css
/* 自定義顏色 */
gold-*  - 金色系 (#eab308 為主)
dark-*  - 深色背景 (#1e293b, #0f172a)
```

## Development

```bash
# 安裝依賴
npm install

# 開發模式
npm run dev      # http://localhost:3000

# 建構生產版本
npm run build

# 預覽生產版本
npm run preview
```

## Task Dependencies

- **T013** (Current): 前端架構設計 ✅
- **T014**: 核心頁面開發 (依賴 T013)
- **T015**: API 整合 (依賴 T013)

## TODO

- [ ] 實現完整的圖表組件（PriceChart）
- [ ] 添加更多頁面路由
- [ ] 實現實時數據 WebSocket 連接
- [ ] 添加單元測試
- [ ] 添加 E2E 測試
