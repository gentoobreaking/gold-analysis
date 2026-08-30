"""
Gold Analysis Core - Main Application Entry Point
黃金價格多維度決策輔助系統
"""

import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    app_name: str = "Gold Analysis Core"
    app_version: str = "0.1.0"
    debug: bool = True
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:5174",
    ]

    class Config:
        extra = "ignore"


settings = Settings()

logger = logging.getLogger(__name__)


scheduler = AsyncIOScheduler()


async def _fetch_real_price_df(days: int = 400) -> pd.DataFrame | None:
    """從 price_history 取得真實黃金價格，構造成監控/重訓所需 DataFrame。

    回傳含 date / close / label 的 DataFrame；取數失敗或樣本不足時回傳 None，
    由呼叫方決定是否跳過本輪（不拋未處理例外）。
    """
    conn = None
    try:
        conn = _get_db()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = conn.execute(
            "SELECT timestamp, local_buy FROM price_history "
            "WHERE metal='gold' AND timestamp >= ? ORDER BY timestamp ASC",
            (cutoff,),
        ).fetchall()
    except Exception as exc:
        logger.warning("[排程] 取得價格資料失敗: %s", exc)
        return None
    finally:
        if conn is not None:
            conn.close()

    if not rows or len(rows) < 30:
        logger.warning("[排程] 真實價格資料不足 (%d 筆)，跳過本輪", len(rows) if rows else 0)
        return None

    df = pd.DataFrame([{"date": r["timestamp"], "close": float(r["local_buy"])} for r in rows])
    # 產生 label：未來 horizon 日報酬方向（與 FeatureEngineer._generate_labels 一致）
    horizon, threshold = 5, 0.01
    future_return = df["close"].shift(-horizon) / df["close"] - 1
    df["label"] = np.select(
        [future_return > threshold, future_return < -threshold],
        [1, -1],
        default=0,
    )
    df = df.dropna().reset_index(drop=True)
    if len(df) < 30:
        logger.warning("[排程] 有效標註樣本不足，跳過本輪")
        return None
    return df


async def run_monitor_job():
    """排程執行監控快照（使用真實價格資料）"""
    try:
        from app.ml.ops import run_monitor

        prices = await _fetch_real_price_df()
        if prices is None:
            return
        result = run_monitor(prices)
        result = {
            **result,
            "source": "price_history",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("[排程] run_monitor: %s", result)
    except Exception:
        logger.exception("[排程] run_monitor 失敗")


async def run_retrain_job():
    """排程檢查是否需要重訓（使用真實價格資料）"""
    try:
        from app.ml.ops import run_retrain

        prices = await _fetch_real_price_df()
        if prices is None:
            return
        result = run_retrain(prices, trigger="cron")
        logger.info("[排程] run_retrain: %s", result)
    except Exception:
        logger.exception("[排程] run_retrain 失敗")


scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動排程器
    scheduler.add_job(
        run_monitor_job,
        IntervalTrigger(minutes=15),
        id="run_monitor",
        replace_existing=True,
    )
    scheduler.add_job(
        run_retrain_job,
        CronTrigger(hour=2, minute=0),
        id="run_retrain",
        replace_existing=True,
    )
    scheduler.start()
    yield
    # 關閉排程器
    scheduler.shutdown()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="黃金價格多維度決策輔助系統 - 核心功能",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── SQLite helper ─────────────────────────────────────────────────────────────

DB_FILE = os.path.expanduser("~/.qclaw/gold_monitor_pro.db")


def _get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# ── API Routes (SQLite mock mode) ────────────────────────────────────────────


@app.get("/api/prices/current")
async def get_current_price():
    """獲取黃金即時價格（從 SQLite 讀取）"""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT local_sell, local_buy, timestamp, source_time "
            "FROM price_history WHERE metal='gold' ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if not row:
            return {
                "sell": 0,
                "buy": 0,
                "sell_twd": 0,
                "buy_twd": 0,
                "timestamp": "",
                "change": 0,
                "change_pct": 0,
            }

        sell = row["local_sell"]
        buy = row["local_buy"]
        ts = row["timestamp"]

        # 計算相對前一天收盤的變動
        prev = conn.execute(
            "SELECT local_sell FROM price_history "
            "WHERE metal='gold' AND local_sell != local_buy "
            "ORDER BY timestamp DESC LIMIT 1 OFFSET 1"
        ).fetchone()
        prev_sell = prev["local_sell"] if prev else sell
        change = sell - prev_sell
        change_pct = (change / prev_sell * 100) if prev_sell else 0

        return {
            "sell": sell,
            "buy": buy,
            "sell_twd": sell,
            "buy_twd": buy,
            "timestamp": ts,
            "change": round(change, 1),
            "change_pct": round(change_pct, 2),
        }
    finally:
        conn.close()


@app.get("/api/prices/history")
async def get_price_history(days: int = 7):
    """獲取歷史價格"""
    conn = _get_db()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = conn.execute(
            "SELECT local_sell AS sell, local_buy AS buy, timestamp "
            "FROM price_history WHERE metal='gold' AND timestamp >= ? "
            "ORDER BY timestamp ASC",
            (cutoff,),
        ).fetchall()
        data = [{"timestamp": r["timestamp"], "sell": r["sell"], "buy": r["buy"]} for r in rows]
        return {"data": data, "count": len(data)}
    finally:
        conn.close()


@app.get("/api/decisions/recommend")
async def get_decision_recommend():
    """AI 決策推薦（mock，基於 RSI 簡單邏輯）"""
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT local_buy FROM price_history WHERE metal='gold' ORDER BY timestamp ASC"
        ).fetchall()
        prices = [r["local_buy"] for r in rows]

        action = "hold"
        confidence = 0.5
        signal = "觀望"
        reasons = ["數據不足，無法給出明確建議"]

        if len(prices) >= 14:
            # RSI(14)
            gains, losses = 0, 0
            for i in range(-14, 0):
                diff = prices[i] - prices[i - 1]
                if diff > 0:
                    gains += diff
                else:
                    losses += abs(diff)
            period = min(14, len(prices) - 1)
            avg_gain = gains / period
            avg_loss = losses / period
            rsi = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss else 100

            # 均線 MA(5) / MA(20) / MA(60)
            ma5 = sum(prices[-5:]) / 5
            ma20 = sum(prices[-20:]) / 20
            ma60 = sum(prices[-60:]) / 60 if len(prices) >= 60 else None

            if rsi < 30 and ma5 < ma20:
                action = "buy"
                confidence = 0.7
                signal = "偏多 - RSI 超賣"
                reasons = [
                    f"RSI(14)={rsi:.1f} 處超賣區",
                    f"MA5={ma5:.0f} < MA20={ma20:.0f}，短線偏弱",
                ]
                if ma60 and ma20 > ma60:
                    reasons.append(f"MA20={ma20:.0f} > MA60={ma60:.0f}，中線仍偏多")
            elif rsi > 70 and ma5 > ma20:
                action = "sell"
                confidence = 0.7
                signal = "偏空 - RSI 超買"
                reasons = [
                    f"RSI(14)={rsi:.1f} 處超買區",
                    f"MA5={ma5:.0f} > MA20={ma20:.0f}，短線偏強",
                ]
                if ma60 and ma20 < ma60:
                    reasons.append(f"MA20={ma20:.0f} < MA60={ma60:.0f}，中線仍偏空")
            else:
                action = "hold"
                confidence = 0.6
                signal = "中性"
                reasons = [f"RSI(14)={rsi:.1f} 中性區間", f"MA5={ma5:.0f} MA20={ma20:.0f}"]
                if ma60:
                    reasons.append(f"MA60={ma60:.0f}")

        return {
            "action": action,
            "confidence": confidence,
            "signal": signal,
            "reason": reasons,
            "price": prices[-1] if prices else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        conn.close()


# ── System endpoints ──────────────────────────────────────────────────────────


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "mode": "sqlite-mock",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": "sqlite-mock"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


# ── Technical Analysis API ─────────────────────────────────────────────────


@app.get("/api/technicals")
async def get_technicals(symbol: str = "TAIFEX-TGF1", timeframe: str = "1D"):
    """
    技術分析：整合 RSI/MACD/MA/Bollinger/Patterns
    timeframe: 1m, 5m, 15m, 1H, 4H, 1D
    資料來源：gold_monitor_pro.db（台灣銀行黃金存摺每日收盤價）
    """
    from .agents.technical_analysis import TechnicalAnalysisAgent

    # 從 SQLite 讀取全量歷史（台灣銀行黃金存摺牌告價）
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT timestamp, local_buy FROM price_history "
            "WHERE metal='gold' ORDER BY timestamp ASC"
        ).fetchall()
        closes = [float(r["local_buy"]) for r in rows]
        sorted_dates = [r["timestamp"][:10] for r in rows]
    finally:
        conn.close()

    MIN_DAYS = 14
    if len(closes) < MIN_DAYS:
        return {
            "error": f"數據不足（{len(closes)} 筆，歷史累積中）",
            "available": len(closes),
            "required": MIN_DAYS,
            "note": "台灣銀行黃金存摺每日執行後資料會自動增加，請稍後再試",
        }

    # 呼叫 TechnicalAnalysisAgent
    agent = TechnicalAnalysisAgent()
    result = await agent.analyze(
        {
            "prices": closes,
            "symbol": symbol,
            "timeframe": timeframe,
        }
    )

    # 加入資料說明
    result["_meta"] = {
        "data_days": len(closes),
        "date_range": f"{sorted_dates[0]} ~ {sorted_dates[-1]}",
        "data_source": "台灣銀行黃金存折每日收盤價",
        "note": f"共 {len(closes)} 個交易日，{MIN_DAYS}+ 筆即可產出指標",
    }
    # ── 轉換為前端格式 ───────────────────────────────────────────────────────
    rsi_val = result.get("indicators", {}).get("rsi")
    macd_val = result.get("indicators", {}).get("macd")
    macd_sig_val = result.get("indicators", {}).get("macd_signal")

    def _rsi_signal(v):
        if v is None:
            return "hold"
        if v > 75:
            return "sell"
        if v > 65:
            return "hold"
        if v < 25:
            return "buy"
        if v < 35:
            return "hold"
        return "hold"

    def _price_signal(current, upper, lower, mid):
        if current > upper:
            return "sell"
        if current < lower:
            return "buy"
        if current > mid:
            return "hold"
        return "hold"

    bb = result.get("indicators", {}).get("bollinger", {})
    ma = result.get("indicators", {}).get("ma", {})
    close = closes[-1] if closes else None

    result["indicators"] = {
        "rsi": {
            "name": "RSI",
            "value": rsi_val,
            "signal": _rsi_signal(rsi_val),
            "description": f"RSI {rsi_val:.1f}" if rsi_val else "無資料",
        },
        "macd": {
            "name": "MACD",
            "value": macd_val,
            "signal": "buy" if (macd_val or 0) > (macd_sig_val or 0) else "sell",
            "description": f"MACD {macd_val:.2f} / Signal {macd_sig_val:.2f}"
            if macd_val and macd_sig_val
            else "無資料",
        },
        "bollinger": {
            "name": "布林通道",
            "value": bb.get("percent_b"),
            "signal": _price_signal(close, bb.get("upper"), bb.get("lower"), bb.get("middle")),
            "description": f"B% {bb.get('percent_b', 0):.0%} | 上下軌 {bb.get('upper', 0):.0f}/{bb.get('lower', 0):.0f}",  # noqa: E501
        },
        "ma_short": {
            "name": "MA短期",
            "value": ma.get("ma20") or ma.get("ma_short"),
            "signal": "hold",
            "description": "短期均線",
        },
        "ma_long": {
            "name": "MA長期",
            "value": ma.get("ma60") or ma.get("ma_long"),
            "signal": "hold",
            "description": "長期均線",
        },
    }

    # 轉換 signals 格式
    raw_signals = result.pop("signals", [])
    result["signals"] = [
        {
            "type": s.get("type", ""),
            "action": s.get("action", "hold"),
            "label": s.get("description", ""),
            "strength": 1.0,
        }
        for s in raw_signals
    ]

    # 轉換 support_resistance
    raw_sr = result.pop("support_resistance", [])
    result["support_resistance"] = [
        {"type": sr.get("type"), "price": sr.get("level")} for sr in raw_sr
    ]

    result["trend_score"] = result.get("trend_score") or 0

    return result


# ── Forward Curve API ─────────────────────────────────────────────────────────

from app.routers.forward_curve import ForwardCurveResponse, get_forward_curve_data


@app.get("/api/forward-curve", response_model=ForwardCurveResponse)
async def forward_curve():
    """
    遠期曲線 API
    回傳黃金期貨各月合約價格結構（Contango / Backwardation 分析）
    """
    return await get_forward_curve_data()


# ── 季節性分析 ──────────────────────────────────────────────────────────────
# 黃金季節性：CME Group / World Gold Council / Kitco 多年研究平均值
GOLD_SEASONALITY = {
    1: {"avg_return": 1.2, "label": "春節前實物需求", "confidence": "medium"},
    2: {"avg_return": 0.8, "label": "春節效應持續", "confidence": "medium"},
    3: {"avg_return": -0.4, "label": "春節結束獲利了結", "confidence": "low"},
    4: {"avg_return": -0.2, "label": "淡季/稅務因素", "confidence": "low"},
    5: {"avg_return": -0.1, "label": "結婚淡季", "confidence": "low"},
    6: {"avg_return": -0.3, "label": "夏季傳統淡季", "confidence": "low"},
    7: {"avg_return": 0.5, "label": "印度婚禮季準備啟動", "confidence": "medium"},
    8: {"avg_return": 1.5, "label": "結婚旺季(印度)", "confidence": "medium"},
    9: {"avg_return": 2.1, "label": "中秋/十一假期", "confidence": "high"},
    10: {"avg_return": 1.8, "label": "排燈節/黃金周", "confidence": "high"},
    11: {"avg_return": 0.3, "label": "年底整理", "confidence": "low"},
    12: {"avg_return": 0.6, "label": "年終避險/禮品採購", "confidence": "medium"},
}
MONTH_NAMES_ZH = {
    1: "1月",
    2: "2月",
    3: "3月",
    4: "4月",
    5: "5月",
    6: "6月",
    7: "7月",
    8: "8月",
    9: "9月",
    10: "10月",
    11: "11月",
    12: "12月",
}


def _season_strength(r):
    if r >= 1.5:
        return "strong_buy"
    if r >= 0.5:
        return "buy"
    if r >= -0.2:
        return "neutral"
    if r >= -0.4:
        return "sell"
    return "strong_sell"


def _get_season(m):
    if m in (3, 4, 5):
        return "Q2(夏)"
    if m in (6, 7, 8):
        return "Q3(秋)"
    if m in (9, 10, 11):
        return "Q4(冬)"
    return "Q1(春)"


@app.get("/api/seasonality")
async def seasonality():
    """
    黃金季節性分析。
    返回月度平均漲跌（市場研究參考值）、強度評級、當前季節分析。
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    current_month = now.month

    # 從 SQLite 讀取月均價（台灣銀行黃金存摺）
    monthly_prices: dict = {}
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT timestamp, local_buy FROM price_history "
            "WHERE metal='gold' ORDER BY timestamp ASC"
        ).fetchall()
        for r in rows:
            ym = r["timestamp"][:7]  # 'YYYY-MM'
            if ym not in monthly_prices:
                monthly_prices[ym] = []
            monthly_prices[ym].append(float(r["local_buy"]))
    finally:
        conn.close()

    # 月均價
    {ym: sum(v) / len(v) for ym, v in monthly_prices.items()}

    monthly_stats = []
    for m in range(1, 13):
        ref = GOLD_SEASONALITY[m]
        year_months = [f"{now.year}-{m:02d}", f"{now.year - 1}-{m:02d}", f"{now.year - 2}-{m:02d}"]
        local = []
        for ym in year_months:
            if ym in monthly_prices:
                local.extend(monthly_prices[ym])
        avg_price = round(sum(local) / len(local), 2) if len(local) >= 2 else None
        monthly_stats.append(
            {
                "month": m,
                "month_label": MONTH_NAMES_ZH[m],
                "avg_return_pct": ref["avg_return"],
                "avg_price": avg_price,
                "data_count": len(local),
                "reference_return": ref["avg_return"],
                "reference_label": ref["label"],
                "confidence": ref["confidence"],
                "strength": _season_strength(ref["avg_return"]),
            }
        )

    sorted_by = sorted(monthly_stats, key=lambda x: x["reference_return"])
    worst_month = sorted_by[0]["month"]
    best_month = sorted_by[-1]["month"]

    total_days = sum(s["data_count"] for s in monthly_stats)
    if total_days < 30:
        data_note = "⚠️ 本地歷史資料不足，月度統計以市場研究參考值為主。黃金季節性是多年平均趨勢，請謹慎解讀。"  # noqa: E501
    else:
        data_note = f"共 {total_days} 天本地歷史資料"

    return {
        "monthly_stats": monthly_stats,
        "current_month": current_month,
        "current_month_label": MONTH_NAMES_ZH[current_month],
        "current_season": _get_season(current_month),
        "best_month": best_month,
        "worst_month": worst_month,
        "data_note": data_note,
        "fetched_at": now.strftime("%Y/%m/%d %H:%M"),
    }


# ────────────────────────────────────────────────────────────────
# 合約資訊 API (T007)
# 資料來源：TAIFEX 台灣期貨交易所
# ────────────────────────────────────────────────────────────────


@app.get("/api/contracts")
async def get_contracts():
    """期貨合約資訊：合約規格 + 月份合約列表"""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    # ── 靜態合約規格 ─────────────────────────────────────────────
    specs = {
        "symbol": "TGF1",
        "full_name": "台灣黃金期貨",
        "exchange": "TAIFEX 台灣期貨交易所",
        "multiplier": "100 盎司 (oz)",
        "tick_size": "1 元/盎司",
        "tick_value": "100 元/口",
        "trading_session": "一般時段 08:45–13:45 / 盤後交易 15:00–次日 05:00",
        "settlement": "現金結算",
        "last_trading_day": "每月倒數第 2 個營業日",
        "delivery_months": "逐月續報，最多 12 個月份",
        "margin": "原始保證金 約 NT$ 55,000 / 口（依交易所公告）",
        "price_limit": "前一交易日結算價 ± 10%",
        "daily_settlement": "每日結算",
    }

    # ── 月份合約列表 ─────────────────────────────────────────────
    # TAIFEX 黃金期貨：每月一個合約，商品代碼 TGF1
    # 近月合約 = 當月 + 接下來 5 個月份（GC! 慣例）
    def _next_n_months(n: int):
        """取得最近 n 個未到期的月份合約"""
        contracts = []
        d = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        while len(contracts) < n:
            month = d.month
            year = d.year
            # 月份代碼：F G H J K M N Q U V X Z
            codes = {
                1: "F",
                2: "G",
                3: "H",
                4: "J",
                5: "K",
                6: "M",
                7: "N",
                8: "Q",
                9: "U",
                10: "V",
                11: "X",
                12: "Z",
            }
            code = codes[month]
            # 到期日：每月倒數第 2 個營業日，約在每月 25 日左右
            # 粗估：每月 25 日（若為假日前移）
            last_trading = _estimate_last_trading_day(year, month)
            contracts.append(
                {
                    "delivery_month": f"{year}-{month:02d}",
                    "delivery_label": f"{year}年{month}月 ({_zh_month(month)})",
                    "contract_code": f"TGF1{code}{str(year)[2:]}",
                    "last_trading_date": last_trading,
                    "is_near": len(contracts) == 0,
                    "months_ahead": len(contracts),
                }
            )
            # 下一個月
            d = datetime(year if month < 12 else year + 1, (month % 12) + 1, 1, tzinfo=timezone.utc)
        return contracts

    def _estimate_last_trading_day(year: int, month: int) -> str:
        """估算：每月 25 日，若為週末/假日往前推至最近營業日"""
        # 每月 25 日
        day = 25
        d = datetime(year, month, day, tzinfo=timezone.utc)
        # 往前推到非週末
        while d.weekday() >= 5:  # 5=Sat, 6=Sun
            d = d - timedelta(days=1)
        return d.strftime("%Y-%m-%d")

    def _zh_month(m: int) -> str:
        return ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"][
            m - 1
        ] + "月"

    months = _next_n_months(6)

    return {
        "specs": specs,
        "contracts": months,
        "fetched_at": now.strftime("%Y/%m/%d %H:%M"),
    }


# ── Merged advanced ops triggers (approach 2) ──────────────────────────────
from app.routers.advanced_ops import ml_router as _ml_ops_router
from app.routers.advanced_ops import trade_router as _trade_router

app.include_router(_ml_ops_router)
app.include_router(_trade_router)

# T063/T064: 掛載 API 路由（app/api/routes/* 原先未 include_router，
# 導致回測與投組風險端點在執行期 404）。無前綴者在此給定 /api/backtest。
from app.api.routes.backtest import router as _backtest_router
from app.api.routes.macro_digest import router as _macro_digest_router
from app.api.routes.portfolio_risk import router as _portfolio_risk_router

app.include_router(_backtest_router, prefix="/api/backtest")
app.include_router(_portfolio_risk_router)
app.include_router(_macro_digest_router)

# T067: Webhook signal ingest (TradingView / external signals)
from app.api.routes.webhooks import router as _webhooks_router

app.include_router(_webhooks_router)
