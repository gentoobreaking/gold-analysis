"""
LLM 宏觀敘事每日摘要路由 (T065)
"""
from __future__ import annotations

import logging

from app.api.schemas.macro_digest import MacroDigestRequest, MacroDigestResponse
from app.services.macro_digest import generate_macro_digest, get_latest_digest
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/macro", tags=["macro"])


@router.post("/generate", response_model=MacroDigestResponse)
async def generate(request: MacroDigestRequest) -> MacroDigestResponse:
    """生成黃金宏觀每日敘事摘要（接真實情緒/價格資料，LLM 不可用時優雅降級）。"""
    result = await generate_macro_digest(push=request.push)
    return MacroDigestResponse(**{k: result[k] for k in MacroDigestResponse.model_fields})


@router.get("/latest", response_model=MacroDigestResponse)
async def latest() -> MacroDigestResponse:
    """讀取最近一次摘要；若無則即時生成（降級模式）。"""
    result = get_latest_digest()
    if result is None:
        result = await generate_macro_digest(push=False)
    return MacroDigestResponse(**{k: result[k] for k in MacroDigestResponse.model_fields})
