#!/bin/bash
# =============================================================================
# start_frontend.sh — Gold Analysis 前端啟動腳本
# =============================================================================
#
# 功能：啟動 Vite 開發伺服器（React + TypeScript）
# 預設端口：5173
#
# 用法：
#   ./start_frontend.sh                # 預設啟動（port 5173）
#   ./start_frontend.sh --port 3000    # 自訂端口
#   ./start_frontend.sh --build        # 建置生產版本（不啟動 dev server）
#   ./start_frontend.sh --preview      # 預覽生產版本
#
# 前置條件：
#   1. Node.js 18+
#   2. 已安裝依賴：cd frontend && npm install
#
# 頁面清單（共 7 頁）：
#   /            — Dashboard（總覽，即時價格 + 決策卡片）
#   /chart       — K 線圖（TradingView Lightweight Charts）
#   /analysis    — 技術分析（指標、信號）
#   /history     — 歷史數據
#   /settings    — 設定
#   /summary     — 摘要總覽
#   /news        — 新聞動態
#
# 注意事項：
#   前端透過 Vite proxy 轉發 /api/* 請求到後端
#   預設後端地址：http://localhost:8000（正式版）
#   如需修改，請編輯 frontend/vite.config.ts 的 proxy target
#
# =============================================================================

set -e

# ── 目錄與路徑 ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOG_FILE="/tmp/gold-frontend.log"

# ── 預設參數 ──────────────────────────────────────────────────────────────────
PORT=5173
MODE="dev"  # dev | build | preview

# ── 解析參數 ──────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --build)
            MODE="build"
            shift
            ;;
        --preview)
            MODE="preview"
            shift
            ;;
        --help|-h)
            head -n 40 "$0" | grep "^#" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "❌ 未知參數：$1"
            echo "用法：$0 [--port PORT] [--build] [--preview] [--help]"
            exit 1
            ;;
    esac
done

# ── 環境檢查 ──────────────────────────────────────────────────────────────────
if [ ! -f "$FRONTEND_DIR/package.json" ]; then
    echo "❌ 找不到 package.json：$FRONTEND_DIR/package.json"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "❌ node_modules 不存在，正在安裝依賴..."
    cd "$FRONTEND_DIR" && npm install
fi

# ── 建置模式 ──────────────────────────────────────────────────────────────────
if [ "$MODE" = "build" ]; then
    echo "📦 建置生產版本..."
    cd "$FRONTEND_DIR"
    npm run build
    echo "✅ 建置完成，輸出目錄：$FRONTEND_DIR/dist/"
    exit 0
fi

if [ "$MODE" = "preview" ]; then
    echo "👁️  預覽生產版本..."
    cd "$FRONTEND_DIR"
    npx vite preview --port $PORT
    exit 0
fi

# ── 清除殘留進程 ──────────────────────────────────────────────────────────────
EXISTING_PID=$(lsof -ti :$PORT 2>/dev/null)
if [ -n "$EXISTING_PID" ]; then
    echo "⚠️  端口 $PORT 已被佔用（PID: $EXISTING_PID），正在終止..."
    kill -9 $EXISTING_PID 2>/dev/null
    sleep 1
fi

# ── 啟動 Dev Server ────────────────────────────────────────────────────────────
echo "🚀 啟動 Gold Analysis 前端（Vite Dev Server）"
echo "   端口：$PORT"
echo "   地址：http://localhost:$PORT"
echo "   日誌：$LOG_FILE"
echo ""

cd "$FRONTEND_DIR"

nohup npx vite --port $PORT > "$LOG_FILE" 2>&1 &

FRONTEND_PID=$!
sleep 3

# ── 驗證 ──────────────────────────────────────────────────────────────────────
if curl -s "http://localhost:$PORT" > /dev/null 2>&1; then
    echo "✅ 前端啟動成功（PID: $FRONTEND_PID）"
    echo "   http://localhost:$PORT"
else
    echo "❌ 前端啟動失敗，查看日誌："
    echo "   tail -20 $LOG_FILE"
    exit 1
fi
