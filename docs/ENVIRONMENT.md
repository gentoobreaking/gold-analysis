# Gold Analysis Core - 開發環境文檔

## 環境概覽

本專案開發環境已配置完成，包含以下組件：

### 1. Python 後端環境

#### 版本要求
- Python 3.9+
- pip (Python 包管理器)

#### 已配置內容
- ✅ 虛擬環境目錄結構（backend/venv）
- ✅ requirements.txt（包含核心依賴）
- ✅ .env.example（環境變數範例）
- ✅ FastAPI 主程式（backend/app/main.py）
- ✅ API 路由模組（backend/app/api/）
- ✅ 數據模型模組（backend/app/models/）
- ✅ 業務邏輯模組（backend/app/services/）
- ✅ OpenClaw Agent 模組（backend/app/agents/）

#### 核心依賴
```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
httpx>=0.26.0
aiohttp>=3.9.0
pandas>=2.1.0
numpy>=1.26.0
python-multipart>=0.0.6
```

### 2. Node.js 前端環境

#### 版本要求
- Node.js 18+
- npm 或 yarn

#### 已配置內容
- ✅ Vite + React + TypeScript 專案結構
- ✅ package.json（包含核心依賴）
- ✅ vite.config.ts（Vite 配置）
- ✅ tsconfig.json（TypeScript 配置）
- ✅ 入口文件（index.html, main.tsx）
- ✅ React 主組件（App.tsx）
- ✅ 樣式文件（index.css, App.css）

#### 核心依賴
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "lightweight-charts": "^4.1.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.2.2",
    "vite": "^5.0.8"
  }
}
```

### 3. Git 版本控制

#### 已配置內容
- ✅ Git 倉庫初始化
- ✅ .gitignore（包含常見排除項）

#### .gitignore 包含項
- Python 字節碼和虛擬環境
- Node.js node_modules
- IDE 配置文件
- 環境變數文件
- 構建輸出
- 日誌文件

### 4. 專案目錄結構

```
/Users/claw/Projects/gold-analysis/
├── backend/                     # Python FastAPI 後端
│   ├── app/
│   │   ├── __init__.py         # 應用初始化
│   │   ├── main.py             # FastAPI 主程式
│   │   ├── api/                # API 路由
│   │   │   ├── __init__.py
│   │   │   └── routes.py
│   │   ├── models/             # 數據模型
│   │   │   └── __init__.py
│   │   ├── services/           # 業務邏輯
│   │   │   └── __init__.py
│   │   └── agents/             # OpenClaw Agent
│   │       └── __init__.py
│   ├── requirements.txt        # Python 依賴
│   └── .env.example            # 環境變數範例
├── frontend/                   # React + Vite 前端
│   ├── src/
│   │   ├── main.tsx           # 入口文件
│   │   ├── App.tsx            # 主組件
│   │   ├── App.css            # 組件樣式
│   │   ├── index.css          # 全局樣式
│   │   └── vite-env.d.ts      # Vite 類型定義
│   ├── index.html             # HTML 模板
│   ├── package.json           # Node.js 依賴
│   ├── vite.config.ts         # Vite 配置
│   ├── tsconfig.json          # TypeScript 配置
│   └── tsconfig.node.json     # Node TypeScript 配置
├── docs/                       # 文檔目錄
│   └── ENVIRONMENT.md         # 本文件
├── scripts/                    # 工具腳本目錄
├── .gitignore                 # Git 排除配置
└── README.md                  # 專案說明文檔
```

## 快速啟動指南

### 後端啟動

```bash
# 1. 進入後端目錄
cd /Users/claw/Projects/gold-analysis/backend

# 2. 創建虛擬環境
python3 -m venv venv

# 3. 激活虛擬環境
source venv/bin/activate  # macOS/Linux

# 4. 安裝依賴
pip install -r requirements.txt

# 5. 配置環境變數
cp .env.example .env
# 編輯 .env 文件

# 6. 啟動開發服務器
uvicorn app.main:app --reload
```

### 前端啟動

```bash
# 1. 進入前端目錄
cd /Users/claw/Projects/gold-analysis/frontend

# 2. 安裝依賴
npm install

# 3. 啟動開發服務器
npm run dev
```

## 開發工具建議

### IDE 推薦
- **VS Code** + Python 擴展 + Pylance
- **PyCharm** (Python 專用)
- **WebStorm** (前端專用)

### VS Code 擴展建議
- Python
- Pylance
- ES7+ React/Redux/React-Native snippets
- TypeScript Importer
- Auto Import
- GitLens

## 開發規範

### Python 代碼規範
- 使用 PEP 8 風格
- 使用 type hints
- 函數和類添加 docstring

### TypeScript 代碼規範
- 使用 ESLint 規則
- 使用 strict 模式
- 優先使用 function components + hooks

### Git 提交規範
```
feat: 新功能
fix: 修復 bug
docs: 文檔更新
style: 代碼格式調整
refactor: 重構
test: 測試相關
chore: 構建/工具相關
```

## 環境變數說明

| 變數名 | 必填 | 描述 | 範例值 |
|--------|------|------|--------|
| DATABASE_URL | 是 | 數據庫連接 URL | postgresql://user:pass@localhost:5432/db |
| GOLD_API_KEY | 是 | 黃金數據 API 密鑰 | your_api_key_here |
| ENVIRONMENT | 否 | 運行環境 | development |
| DEBUG | 否 | 調試模式 | true |
| CORS_ORIGINS | 否 | CORS 允許的來源 | http://localhost:5173 |
| HOST | 否 | 服務器主機 | 0.0.0.0 |
| PORT | 否 | 服務器端口 | 8000 |

## 下一步建議

1. **安裝後端依賴**：執行 `pip install -r requirements.txt`
2. **安裝前端依賴**：執行 `npm install`
3. **配置環境變數**：複製 .env.example 為 .env 並填入實際值
4. **啟動服務器**：分別啟動前後端開發服務器
5. **驗證環境**：訪問 http://localhost:8000/docs 查看 API 文檔

## 故障排除

### Python 虛擬環境問題
```bash
# 刪除舊的虛擬環境
rm -rf venv
# 重新創建
python3 -m venv venv
```

### Node 依賴問題
```bash
# 清除快取並重新安裝
rm -rf node_modules package-lock.json
npm install
```

### 端口占用問題
```bash
# 查找占用端口的進程
lsof -i :8000  # 後端
lsof -i :5173  # 前端

# 終止進程
kill -9 <PID>
```

## 環境檢查清單

- [x] Python 3.9+ 已安裝
- [x] Node.js 18+ 已安裝
- [x] Git 已安裝
- [x] 專案目錄結構已建立
- [x] Python 依賴清單已創建
- [x] Node 依賴清單已創建
- [x] .gitignore 已配置
- [x] README.md 已創建
- [x] 環境文檔已創建

## 最後更新

- 日期：2026-04-07
- 任務：T001 - 搭建開發環境
- 狀態：✅ 完成
