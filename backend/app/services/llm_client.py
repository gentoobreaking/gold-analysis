"""
LLM 客戶端 (T065) — OpenAI-compatible /v1/chat/completions，env-gated。

設計原則：
- 不依賴任何 LLM SDK（用 httpx 直接打標準 OpenAI 相容端點），避免新增重依賴。
- 未啟用（llm_enabled=False）或缺少金鑰時 is_available()=False，
  呼叫 chat() 會拋出 LLMUnavailableError，由 macro_digest 管線優雅降級。
- 所有網路呼叫失敗都轉為 LLMUnavailableError，絕不讓管線崩潰。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx
from app.core.config import get_core_settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    """LLM 未啟用或呼叫失敗，管線應優雅降級。"""


@dataclass
class Message:
    role: str
    content: str


@dataclass
class LLMClient:
    """OpenAI-compatible 聊天客戶端"""

    base_url: str = ""
    api_key: str | None = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    timeout: float = 30.0
    enabled: bool = False

    @classmethod
    def from_settings(cls) -> LLMClient:
        s = get_core_settings()
        return cls(
            base_url=s.llm_base_url,
            api_key=s.llm_api_key,
            model=s.llm_model,
            temperature=s.llm_temperature,
            enabled=bool(s.llm_enabled and s.llm_api_key),
        )

    def is_available(self) -> bool:
        return self.enabled and bool(self.api_key)

    def chat(
        self,
        messages: list[Message],
        *,
        temperature: float | None = None,
    ) -> str:
        """回傳 LLM 文字回應；未啟用或失敗時拋出 LLMUnavailableError。"""
        if not self.is_available():
            raise LLMUnavailableError(
                "LLM 未啟用或缺少 API key（請設定 CORE_LLM_ENABLED/CORE_LLM_API_KEY）"
            )

        url = self.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self.temperature if temperature is None else temperature,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPError as e:
            logger.error("LLM request failed: %s", e)
            raise LLMUnavailableError(f"LLM 呼叫失敗: {e}") from e
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error("LLM response parse failed: %s", e)
            raise LLMUnavailableError(f"LLM 回應解析失敗: {e}") from e
