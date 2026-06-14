# Gold Analysis Core

黃金價格多維度決策輔助系統 - 核心功能

## 專案簡介

Gold Analysis Core 是一個黃金價格多維度決策輔助系統，提供價格分析、趨勢預測、技術指標計算等功能，幫助投資者做出更明智的決策。

## 技術棧

### 後端
- **框架**: Python 3.9+ / FastAPI
- **數據處理**: Pandas, NumPy
- **HTTP 客戶端**: httpx, aiohttp

### 前端
- **框架**: React 18+ / TypeScript
- **構建工具**: Vite
- **圖表庫**: TradingView Lightweight Charts
- **HTTP 客戶端**: Axios

### Agent
- **語言**: Python
- **平台**: OpenClaw

## 專案結構

```
gold-analysis/
├── backend/                 # Python FastAPI 後端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py         # FastAPI 主程式
│   │   ├── api/            # API 路由
│   │   ├── models/         # 數據模型
│   │   ├── services/       # 業務邏輯
│   │   └── agents/         # OpenClaw Agent
│   ├── requirements.txt    # Python 依賴
│   └── .env.example        # 環境變數範例
├── frontend/               # React + Vite 前端
│   ├── src/
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── docs/                   # 文檔
├── scripts/                # 工具腳本
├── .gitignore
└── README.md
```

## 快速開始

### 環境需求

- Python 3.9+
- Node.js 18+
- npm 或 yarn

### 後端設置

1. 創建虛擬環境：
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或 venv\Scripts\activate  # Windows
```

2. 安裝依賴：
```bash
pip install -r requirements.txt
```

3. 配置環境變數：
```bash
cp .env.example .env
# 編輯 .env 文件，填入實際配置
```

4. 啟動開發服務器：
```bash
uvicorn app.main:app --reload
```

後端服務將在 http://localhost:8000 啟動

### 前端設置

1. 安裝依賴：
```bash
cd frontend
npm install
```

2. 啟動開發服務器：
```bash
npm run dev
```

前端服務將在 http://localhost:5173 啟動

## 開發指南

### 後端開發

- API 文檔：http://localhost:8000/docs (Swagger UI)
- 健康檢查：http://localhost:8000/health

### 前端開發

- 開發服務器：http://localhost:5173
- 構建生產版本：`npm run build`
- 預覽生產版本：`npm run preview`

## API 端點

### 基礎端點
- `GET /` - 根端點，返回服務信息
- `GET /health` - 健康檢查

### API 路由
- `GET /api/status` - 系統狀態

（更多端點將在後續開發中添加）

## 環境變數

| 變數名 | 描述 | 預設值 |
|--------|------|--------|
| DATABASE_URL | 數據庫連接 URL | - |
| GOLD_API_KEY | 黃金數據 API 密鑰 | - |
| ENVIRONMENT | 運行環境 | development |
| DEBUG | 調試模式 | true |
| CORS_ORIGINS | CORS 允許的來源 | http://localhost:5173 |
| HOST | 服務器主機 | 0.0.0.0 |
| PORT | 服務器端口 | 8000 |

## Git 工作流程

1. 創建功能分支：`git checkout -b feature/功能名稱`
2. 提交變更：`git commit -m "feat: 描述"`
3. 推送分支：`git push origin feature/功能名稱`
4. 創建 Pull Request

## 授權

MIT License

## 貢獻指南

歡迎提交 Issue 和 Pull Request。

## 聯繫方式

如有問題或建議，請創建 Issue。
