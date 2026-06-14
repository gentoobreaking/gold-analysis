"""
Gold Analysis MVP - 極簡版後端
直接串接 gold_monitor.py 的數據源，快速展示 Dashboard
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# ── 數據源路徑 ────────────────────────────────────────────────────────────────
HISTORY_FILE = Path("/Users/claw/.qclaw/gold_price_history.json")
CONFIG_FILE = Path("/Users/claw/.qclaw/gold_monitor_config.json")

# ── Pydantic Models ───────────────────────────────────────────────────────────
class PriceResponse(BaseModel):
    sell: float
    buy: float
    sell_twd: float
    buy_twd: float
    timestamp: str
    change: Optional[float] = None
    change_pct: Optional[float] = None

class DecisionResponse(BaseModel):
    action: str
    confidence: float
    signal: str
    reason: list[str]
    price: float
    timestamp: str

class HistoryPoint(BaseModel):
    timestamp: str
    sell: float
    buy: float

class HistoryResponse(BaseModel):
    data: list[HistoryPoint]
    count: int

# ── 核心函數 ─────────────────────────────────────────────────────────────────
def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {"daily": {}, "intraday": {}}

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def _get_latest_from_intraday(intraday: dict):
    """從 intraday 列表中找最新一筆（intraday 值是 list）"""
    today_key = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    for key in [today_key, yesterday]:
        if key in intraday and isinstance(intraday[key], list):
            data_list = intraday[key]
            if data_list:
                # 取最後一筆（最新）
                last = data_list[-1]
                return last
    return None

def get_latest_price():
    history = load_history()
    intraday = history.get("intraday", {})
    daily = history.get("daily", {})
    
    latest = _get_latest_from_intraday(intraday)
    if not latest:
        # Fallback: 用 daily
        dates = sorted(daily.keys())
        if dates:
            latest = daily[dates[-1]]
        else:
            return None
    
    sell = float(latest.get("sell", 0) or latest.get("price", 0))
    buy = float(latest.get("buy", 0) or latest.get("price", 0))
    ts = latest.get("timestamp", datetime.now().isoformat())
    
    # 計算變動（相對於昨日收盤）
    dates = sorted(daily.keys())
    change = 0.0
    change_pct = 0.0
    if len(dates) >= 2:
        yesterday_close = float(daily[dates[-2]]["sell"])
        change = sell - yesterday_close
        change_pct = (change / yesterday_close * 100) if yesterday_close else 0
    
    return {
        "sell": sell,
        "buy": buy,
        "sell_twd": sell,
        "buy_twd": buy,
        "timestamp": ts,
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
    }

def get_decision():
    price_data = get_latest_price()
    if not price_data:
        return None
    
    sell = price_data["sell"]
    config = load_config()
    buy_threshold = config.get("buy_threshold", 4500)
    sell_threshold = config.get("sell_threshold", 5000)
    
    if sell <= buy_threshold:
        action, signal, reason = "buy", "💰 買入信號", [f"價格 {sell} ≤ 買入門檻 {buy_threshold}"]
    elif sell >= sell_threshold:
        action, signal, reason = "sell", "⚠️ 賣出信號", [f"價格 {sell} ≥ 賣出門檻 {sell_threshold}"]
    else:
        action, signal, reason = "hold", "➡️ 觀望", [f"價格在區間內（{buy_threshold} - {sell_threshold}）"]
    
    return {
        "action": action,
        "confidence": 0.75,
        "signal": signal,
        "reason": reason,
        "price": sell,
        "timestamp": price_data["timestamp"],
    }

def get_history(days: int = 7):
    history = load_history()
    intraday = history.get("intraday", {})
    daily = history.get("daily", {})
    cutoff = datetime.now() - timedelta(days=days)
    all_data = []
    
    for key, value in intraday.items():
        if isinstance(value, list):
            for item in value:
                try:
                    dt = datetime.fromisoformat(item["timestamp"])
                    if dt >= cutoff:
                        all_data.append(HistoryPoint(
                            timestamp=item["timestamp"],
                            sell=float(item.get("sell", 0) or item.get("price", 0)),
                            buy=float(item.get("buy", 0) or item.get("price", 0)),
                        ))
                except:
                    pass
    
    all_data.sort(key=lambda x: x.timestamp)
    return {"data": all_data, "count": len(all_data)}

# ── FastAPI App ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Gold Analysis MVP",
    version="0.1.0",
    description="黃金價格多維度決策輔助系統 - MVP",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"name": "Gold Analysis MVP", "version": "0.1.0", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/prices/current", response_model=PriceResponse)
async def current_price():
    price = get_latest_price()
    if not price:
        raise ValueError("無法取得價格數據")
    return PriceResponse(**price)

@app.get("/api/prices/history", response_model=HistoryResponse)
async def price_history(days: int = 7):
    return HistoryResponse(**get_history(days))

@app.get("/api/decisions/recommend", response_model=DecisionResponse)
async def recommend():
    decision = get_decision()
    if not decision:
        raise ValueError("無法產生決策")
    return DecisionResponse(**decision)

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8765, reload=False)
