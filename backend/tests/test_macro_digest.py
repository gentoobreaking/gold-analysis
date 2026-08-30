"""
T065 - LLM 宏觀每日摘要管線測試（mock LLM / 資料源；優雅降級）

專案 pytest 配置為 asyncio_mode=auto，故 async 測試可直接定義。
"""

from __future__ import annotations

import os

import pytest
from app.services import macro_digest as md
from app.services.llm_client import LLMClient, LLMUnavailableError, Message

# ── 注入用的 fake tool / LLM ────────────────────────────────────────────────


class _FakeTools:
    """取代 DataTools.get_sentiment_data（不需網路）。"""

    async def get_sentiment_data(self):
        return {
            "available": True,
            "source": "alternative.me",
            "gold": {"fear_greed_index": 68, "sentiment": "Greed", "classification": "Greed"},
        }


class _FakeLLM:
    def __init__(self, *, available=True, text="市場情緒偏貪婪。美元走弱支撐金價。"):
        self.available = available
        self.text = text
        self.calls = 0

    def is_available(self):
        return self.available

    def chat(self, messages):
        self.calls += 1
        assert all(isinstance(m, Message) for m in messages)
        if not self.available:
            raise LLMUnavailableError("disabled")
        return self.text


@pytest.fixture(autouse=True)
def _patch(tmp_path, monkeypatch):
    fake_dir = tmp_path / "digests"
    monkeypatch.setattr(md, "DIGEST_DIR", str(fake_dir))
    monkeypatch.setattr(md, "LATEST_JSON", str(fake_dir / "macro_digest_latest.json"))
    monkeypatch.setattr(md, "DataTools", _FakeTools)
    yield


async def test_generate_uses_llm_when_available():
    llm = _FakeLLM(available=True)
    result = await md.generate_macro_digest(client=llm)
    assert result["llm_used"] is True
    assert llm.calls == 1
    text = result["markdown"]
    assert "非投資建議" in text  # 必須標註免責聲明
    assert "資料時間" in text  # 必須標註資料時間
    assert "Greed" in text or "貪婪" in text  # 引用真實情緒數據
    assert os.path.exists(md.LATEST_JSON)  # 已存檔


async def test_generate_degrades_when_llm_unavailable():
    llm = _FakeLLM(available=False)
    result = await md.generate_macro_digest(client=llm)
    assert result["llm_used"] is False  # 優雅降級，不崩潰
    assert "非投資建議" in result["markdown"]
    assert "資料時間" in result["markdown"]
    assert os.path.exists(md.LATEST_JSON)


async def test_get_latest_digest_roundtrip():
    llm = _FakeLLM(available=True)
    await md.generate_macro_digest(client=llm)
    latest = md.get_latest_digest()
    assert latest is not None
    assert latest["llm_used"] is True
    assert "markdown" in latest


def test_fallback_digest_on_unavailable_sentiment():
    """真實 sentiment 取不到時，仍產出含免責聲明的降級摘要。"""
    ctx = {
        "sentiment": {"available": False, "reason": "network"},
        "price_context": "",
        "generated_at": "2026-08-28T00:00:00+00:00",
    }
    out = md._fallback_digest(ctx)
    assert out["llm_used"] is False
    assert "非投資建議" in out["markdown"]
    assert "無法取得" in out["markdown"] or "unavailable" in out["markdown"]


def test_llm_client_unavailable_raises():
    client = LLMClient(enabled=False, api_key=None)
    assert client.is_available() is False
    with pytest.raises(LLMUnavailableError):
        client.chat([Message(role="user", content="hi")])
