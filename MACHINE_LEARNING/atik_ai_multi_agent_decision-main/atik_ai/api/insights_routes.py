"""
Tahmin / öneri (heuristik) ve LLM köprüsü (Ollama veya OpenAI uyumlu).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.database import DatabaseManager
from ..ewc_heuristic import merge_suggestions

logger = logging.getLogger(__name__)

predict_router = APIRouter(prefix="/predict", tags=["Predict"])
llm_router = APIRouter(prefix="/llm", tags=["LLM"])

db_manager = DatabaseManager()


class LlmChatMessage(BaseModel):
    role: str = Field(..., description="system | user | assistant")
    content: str


class LlmChatRequest(BaseModel):
    messages: List[LlmChatMessage]
    max_tokens: int = Field(512, ge=32, le=4096)
    temperature: float = Field(0.3, ge=0, le=2)


def _ollama_base() -> str:
    raw = (os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST") or "").strip().rstrip("/")
    return raw


def _openai_key() -> str:
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def _openai_url() -> str:
    return (os.getenv("OPENAI_API_URL") or "https://api.openai.com/v1/chat/completions").strip()


def _openai_model() -> str:
    return (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()


def _ollama_model() -> str:
    return (os.getenv("OLLAMA_MODEL") or "llama3.2").strip()


@predict_router.get("/ewc-by-nace")
async def predict_ewc_by_nace(
    nace: str = Query(..., min_length=2, max_length=32, description="Örn: 24.45 veya 38.12"),
    limit_rules: int = Query(25, ge=1, le=100),
    include_waste_table: bool = Query(True, description="waste_types tablosundan skorlu kodlar"),
):
    """NACE için kural tabanlı EWC önerileri + (varsa) veritabanındaki atık kodları sıralaması."""
    waste_rows: Optional[List[tuple]] = None
    if include_waste_table:
        try:
            rows = db_manager.execute_sql(
                "SELECT waste_code, description, status FROM waste_types ORDER BY waste_code LIMIT 500",
                {},
            )
            waste_rows = list(rows)
        except Exception as e:
            logger.warning("waste_types okunamadı: %s", e)
            waste_rows = None
    return merge_suggestions(nace, waste_rows, rule_limit=limit_rules, waste_limit=25)


@predict_router.get("/health-llm")
async def predict_llm_bridge_health():
    """LLM uç noktası yapılandırılmış mı (anahtar / Ollama URL)."""
    ollama = _ollama_base()
    return {
        "ollama_configured": bool(ollama),
        "ollama_base": ollama or None,
        "openai_configured": bool(_openai_key()),
        "hint": "POST /api/v1/llm/chat — Ollama için OLLAMA_BASE_URL, bulut için OPENAI_API_KEY.",
    }


@llm_router.post("/chat")
async def llm_chat(req: LlmChatRequest):
    """
    OpenAI uyumlu sohbet. Önce OLLAMA_BASE_URL (örn. http://host.docker.internal:11434), yoksa OpenAI.
    """
    payload = {
        "model": _ollama_model(),
        "messages": [m.model_dump() for m in req.messages],
        "max_tokens": req.max_tokens,
        "temperature": req.temperature,
    }
    ollama = _ollama_base()
    timeout = httpx.Timeout(120.0, connect=10.0)

    if ollama:
        url = f"{ollama}/v1/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                return r.json()
        except httpx.HTTPError as e:
            logger.error("Ollama isteği hatası: %s", e)
            raise HTTPException(
                status_code=502,
                detail=f"Ollama erişilemedi ({url}). Windows: Ollama çalışıyor mu? Docker: OLLAMA_BASE_URL=http://host.docker.internal:11434",
            )

    key = _openai_key()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="LLM yapılandırılmadı: OLLAMA_BASE_URL veya OPENAI_API_KEY ayarlayın.",
        )

    payload["model"] = _openai_model()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(_openai_url(), headers=headers, json=payload)
            if r.status_code >= 400:
                raise HTTPException(status_code=r.status_code, detail=r.text[:800])
            return r.json()
    except httpx.HTTPError as e:
        logger.error("OpenAI isteği hatası: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@llm_router.post("/waste-advice")
async def llm_waste_advice(
    nace_code: str = Query(..., min_length=2, max_length=32),
    waste_code: Optional[str] = Query(None, max_length=20),
    city: Optional[str] = Query(None, max_length=80),
):
    """Tek çağrıda kısa Türkçe tavsiye metni (LLM varsa)."""
    heur = await predict_ewc_by_nace(nace=nace_code, limit_rules=15, include_waste_table=True)
    system = (
        "Sen döngüsel ekonomi ve atık yönetimi uzmanısın. Kısa, maddeli Türkçe yanıt ver. "
        "Belirsizlik varsa bunu belirt."
    )
    user = json.dumps(
        {
            "nace_code": nace_code,
            "waste_code": waste_code,
            "city": city,
            "heuristic_summary": heur,
        },
        ensure_ascii=False,
    )
    req = LlmChatRequest(
        messages=[
            LlmChatMessage(role="system", content=system),
            LlmChatMessage(role="user", content=f"Bu tesis için atık/geri dönüşüm öner: {user}"),
        ],
        max_tokens=600,
        temperature=0.25,
    )
    advice = None
    llm_error = None
    try:
        raw = await llm_chat(req)
        try:
            advice = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            advice = str(raw)[:2000]
    except HTTPException as e:
        llm_error = e.detail if isinstance(e.detail, str) else str(e.detail)

    return {
        "nace_code": nace_code,
        "waste_code": waste_code,
        "heuristic": heur,
        "advice_markdown": advice,
        "llm_error": llm_error,
    }
