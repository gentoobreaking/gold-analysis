#!/bin/bash
# =============================================================================
# start_backend_mvp.sh — Gold Analysis 極簡版後端啟動腳本
# =============================================================================
#
# 功能：啟動 FastAPI 後端（MVP 極簡版），讀取 JSON 數據檔案
# 數據源：~/.qclaw/gold_price_history.json（JSON）
# 預設端口：8765
#
# 用法：
#   ./start_backend_mvp.sh              # 預設啟動（port 8765）
#   ./start_backend_mvp.sh --port 9000  # 自訂端口
#
# 前置條件：
#   1. Python 3.9+
#   2. 已安裝依賴：fastapi, uvicorn, pydantic
#
# 與正式版（start_backend.sh）的差異：
#   - 數據源：JSON 檔案（非 SQLite）
#   - 決策邏輯：簡單閾值比對（非 RSI + MA）
#   - 單檔架構 server.py（非模組化 app/）
#   - 適合快速原型驗證，不適合生產環境
#
# API 端點：
#   GET /                       — 服務資訊
#   GET /health                 — 健康檢查
#   GET /api/prices/current     — 即時黃金價格
#   GET /api/prices/history     — 歷史價格（預設 7 天）
#   GET /api/decisions/recommend — 決策推薦（閾值邏輯）
#
# =============================================================================

set -e

# ── 目錄與路徑 ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MVP_DIR="$PROJECT_ROOT/backend_mvp"
LOG_FILE="/tmp/gold-backend-mvp.log"

# ── 預設參數 ──────────────────────────────────────────────────────────────────
PORT=8765

# ── 解析參數 ──────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --help|-h)
            head -n 33 "$0" | grep "^#" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "❌ 未知參數：$1"
            echo "用法：$0 [--port PORT] [--help]"
            exit 1
            ;;
    esac
done

# ── 環境檢查 ──────────────────────────────────────────────────────────────────
if [ ! -f "$MVP_DIR/server.py" ]; then
    echo "❌ 找不到 server.py：$MVP_DIR/server.py"
    exit 1
fi

if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "❌ 缺少 fastapi，請先安裝：pip install fastapi uvicorn pydantic"
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
echo "🚀 啟動 Gold Analysis MVP 極簡版後端"
echo "   數據源：JSON（gold_price_history.json）"
echo "   端口：$PORT"
echo "   日誌：$LOG_FILE"
echo ""

cd "$MVP_DIR"

nohup python3 -m uvicorn server:app \
    --host 0.0.0.0 \
    --port $PORT \
    > "$LOG_FILE" 2>&1 &

MVP_PID=$!
sleep 2

# ── 驗證 ──────────────────────────────────────────────────────────────────────
if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
    echo "✅ MVP 後端啟動成功（PID: $MVP_PID）"
    echo "   http://localhost:$PORT/health"
else
    echo "❌ MVP 後端啟動失敗，查看日誌："
    echo "   tail -20 $LOG_FILE"
    exit 1
fi
