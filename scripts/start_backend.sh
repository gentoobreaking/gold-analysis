#!/bin/bash
# =============================================================================
# start_backend.sh — Gold Analysis 正式版後端啟動腳本
# =============================================================================
#
# 功能：啟動 FastAPI 後端（正式版），讀取 SQLite 數據庫
# 數據源：~/.qclaw/gold_monitor_pro.db（SQLite）
# 預設端口：8000
# API 文檔：http://localhost:8000/docs（Swagger UI）
#
# 用法：
#   ./start_backend.sh              # 預設啟動（port 8000，debug 模式）
#   ./start_backend.sh --port 9000  # 自訂端口
#   ./start_backend.sh --no-reload  # 關閉熱重載（生產用）
#
# 前置條件：
#   1. Python 3.9+
#   2. 已安裝依賴：pip install -r backend/requirements.txt
#   3. 已建立虛擬環境：python3 -m venv backend/venv
#
# API 端點：
#   GET /                       — 服務資訊
#   GET /health                 — 健康檢查
#   GET /api/prices/current     — 即時黃金價格（賣出/買入/變動）
#   GET /api/prices/history     — 歷史價格（預設 7 天）
#   GET /api/decisions/recommend — AI 決策推薦（RSI + MA 邏輯）
#
# =============================================================================

set -e

# ── 目錄與路徑 ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
VENV_DIR="$BACKEND_DIR/venv"
LOG_FILE="/tmp/gold-backend.log"

# ── 預設參數 ──────────────────────────────────────────────────────────────────
PORT=8000
RELOAD="--reload"

# ── 解析參數 ──────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --no-reload)
            RELOAD=""
            shift
            ;;
        --help|-h)
            head -n 35 "$0" | grep "^#" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "❌ 未知參數：$1"
            echo "用法：$0 [--port PORT] [--no-reload] [--help]"
            exit 1
            ;;
    esac
done

# ── 環境檢查 ──────────────────────────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ 虛擬環境不存在：$VENV_DIR"
    echo "   請先執行：cd $BACKEND_DIR && python3 -m venv venv"
    exit 1
fi

if [ ! -f "$BACKEND_DIR/app/main.py" ]; then
    echo "❌ 找不到 main.py：$BACKEND_DIR/app/main.py"
    exit 1
fi

# ── 清除殘留進程 ──────────────────────────────────────────────────────────────
EXISTING_PID=$(lsof -ti :$PORT 2>/dev/null)
if [ -n "$EXISTING_PID" ]; then
    echo "⚠️  端口 $PORT 已被佔用（PID: $EXISTING_PID），正在終止..."
    kill -9 $EXISTING_PID 2>/dev/null
    sleep 1
fi

# ── 啟動 ──────────────────────────────────────────────────────────────────────
echo "🚀 啟動 Gold Analysis 正式版後端"
echo "   數據源：SQLite（gold_monitor_pro.db）"
echo "   端口：$PORT"
echo "   API 文檔：http://localhost:$PORT/docs"
echo "   日誌：$LOG_FILE"
echo ""

source "$VENV_DIR/bin/activate"
cd "$BACKEND_DIR"

nohup python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    $RELOAD \
    > "$LOG_FILE" 2>&1 &

BACKEND_PID=$!
sleep 2

# ── 驗證 ──────────────────────────────────────────────────────────────────────
if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
    echo "✅ 後端啟動成功（PID: $BACKEND_PID）"
    echo "   http://localhost:$PORT/health"
else
    echo "❌ 後端啟動失敗，查看日誌："
    echo "   tail -20 $LOG_FILE"
    exit 1
fi
