"""
LLM 宏觀敘事每日摘要管線 (T065)。

流程：
  1. 蒐集真實資料：市場情緒（alternative.me，T056 已實作）＋近期黃金價格（price_history）
  2. 組裝 prompt（利率/美元/地緣/ETF 資金流 視角）
  3. 呼叫 LLM（OpenAI-compatible，env-gated）生成 markdown 敘事
  4. 補上「非投資建議」與資料時間戳
  5. 存檔（JSON + Markdown）並可推送（T056 notify）
  6. LLM 不可用時優雅降級：產出一段以真實資料為基礎的結構化摘要，不崩潰
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from app.services.llm_client import LLMClient, LLMUnavailableError, Message
from app.services.price_data import fetch_price_series
from app.tools.data_tools import DataTools

logger = logging.getLogger(__name__)

DIGEST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "digests")
LATEST_JSON = os.path.join(DIGEST_DIR, "macro_digest_latest.json")


async def _build_context() -> dict[str, Any]:
    """蒐集真實資料作為 LLM 輸入與降級摘要的依據。"""
    tools = DataTools()
    sentiment = await tools.get_sentiment_data()
    _, closes = fetch_price_series("GOLD", limit=30)
    price_context = ""
    if len(closes) >= 2:
        last = closes[-1]
        prev = closes[-2]
        chg = (last / prev - 1) * 100 if prev else 0.0
        price_context = (
            f"近期黃金收盤價最新 {last:.2f}，前筆 {prev:.2f}，單期變動 {chg:+.2f}%。"
        )
    return {
        "sentiment": sentiment,
        "price_context": price_context,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _system_prompt() -> str:
    return (
        "你是宏觀研究助理，專注黃金市場。請根據提供的真實市場情緒與價格數據，"
        "用繁體中文撰寫一段簡潔的每日黃金宏觀敘事（markdown），涵蓋："
        "(1) 市場情緒與風險偏好；(2) 美元與實質利率暗示；(3) 資金流向與地緣風險；"
        "(4) 對黃金的啟示。必須明確引用提供的數據，並在文末標註資料時間。"
        "若數據標示 unavailable，請如實說明無法取得。"
    )


def _user_prompt(ctx: dict[str, Any]) -> str:
    sentiment = ctx["sentiment"]
    if sentiment.get("available"):
        gold = sentiment.get("gold", {})
        fg = gold.get("fear_greed_index")
        s_class = gold.get("sentiment") or gold.get("classification") or "n/a"
        sentiment_block = (
            f"市場情緒（alternative.me，{sentiment.get('source')}）："
            f"恐懼貪婪指數 = {fg}，分類 = {s_class}。"
        )
    else:
        sentiment_block = f"市場情緒：unavailable（{sentiment.get('reason', '取得失敗')}）。"

    return (
        f"{sentiment_block}\n"
        f"價格背景：{ctx['price_context'] or '無'}\n"
        f"資料時間：{ctx['generated_at']}\n\n"
        "請輸出 markdown 敘事。"
    )


def _markdown_template(ctx: dict[str, Any], body: str) -> str:
    return (
        f"# 黃金宏觀每日敘事\n\n"
        f"> 資料時間：{ctx['generated_at']}  |  來源：alternative.me / price_history\n\n"
        f"{body}\n\n"
        "---\n"
        "⚠️ 本摘要由 LLM 根據公開數據自動生成，僅供研究參考，**非投資建議**。\n"
    )


def _fallback_digest(ctx: dict[str, Any]) -> dict[str, Any]:
    """LLM 不可用時的優雅降級：以真實資料產生結構化摘要。"""
    sentiment = ctx["sentiment"]
    if sentiment.get("available"):
        gold = sentiment.get("gold", {})
        fg = gold.get("fear_greed_index")
        s_class = gold.get("sentiment") or gold.get("classification") or "n/a"
        body = (
            f"市場情緒指數為 **{fg}（{s_class}）**。{ctx['price_context']}\n\n"
            "（LLM 敘事服務未啟用或暫時無法連線，此為基礎資料摘要。）"
        )
    else:
        body = (
            "市場情緒資料暫時無法取得，請稍後重試或檢查資料源連線。\n\n"
            f"{ctx['price_context']}"
        )
    markdown = _markdown_template(ctx, body)
    return {
        "generated_at": ctx["generated_at"],
        "llm_used": False,
        "markdown": markdown,
        "body": body,
        "context": ctx,
    }


async def generate_macro_digest(
    client: LLMClient | None = None,
    *,
    push: bool = False,
) -> dict[str, Any]:
    """生成黃金宏觀每日敘事摘要。

    Args:
        client: 外部可注入 LLMClient（測試用）；預設取 settings。
        push: 是否透過 T056 notify 推送（需 notify_enabled）。
    Returns:
        { generated_at, llm_used, markdown, body, context }
    """
    ctx = await _build_context()
    client = client or LLMClient.from_settings()
    markdown = body = ""
    llm_used = False

    if client.is_available():
        try:
            text = client.chat(
                [
                    Message(role="system", content=_system_prompt()),
                    Message(role="user", content=_user_prompt(ctx)),
                ]
            )
            body = text
            markdown = _markdown_template(ctx, text)
            llm_used = True
            logger.info("LLM macro digest generated (%d chars)", len(text))
        except LLMUnavailableError as e:
            logger.warning("LLM unavailable, degrading: %s", e)
            result = _fallback_digest(ctx)
            return _save_and_maybe_push(result, push)

    if not llm_used:
        result = _fallback_digest(ctx)
        return _save_and_maybe_push(result, push)

    result = {
        "generated_at": ctx["generated_at"],
        "llm_used": llm_used,
        "markdown": markdown,
        "body": body,
        "context": ctx,
    }
    return _save_and_maybe_push(result, push)


def _save_and_maybe_push(result: dict[str, Any], push: bool) -> dict[str, Any]:
    os.makedirs(DIGEST_DIR, exist_ok=True)
    with open(LATEST_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    # 同時存一份 markdown
    md_path = os.path.join(DIGEST_DIR, "macro_digest_latest.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result.get("markdown", ""))

    if push:
        try:
            from app.services.notify import notify_alert

            notify_alert(
                {
                    "title": "黃金宏觀每日摘要",
                    "body": result.get("markdown", ""),
                    "level": "info",
                    "source": "macro_digest",
                }
            )
        except Exception as e:  # noqa: BLE001
            logger.error("push digest failed: %s", e)
    return result


def get_latest_digest() -> dict[str, Any] | None:
    """讀取最近一次摘要；若不存在回傳 None。"""
    if not os.path.exists(LATEST_JSON):
        return None
    try:
        with open(LATEST_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        logger.error("read latest digest failed: %s", e)
        return None
