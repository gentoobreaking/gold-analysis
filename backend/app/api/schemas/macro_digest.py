"""
Macro digest schemas (T065)
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MacroDigestResponse(BaseModel):
    """LLM 宏觀每日敘事摘要"""
    generated_at: str
    llm_used: bool
    markdown: str
    body: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class MacroDigestRequest(BaseModel):
    """觸發摘要生成"""
    push: bool = Field(default=False, description="是否透過 T056 notify 推送")
    force: bool = Field(default=False, description="保留參數（目前每次皆重新生成）")
