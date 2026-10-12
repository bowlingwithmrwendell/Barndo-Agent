"""Public, anonymous endpoints used by the barndobible.com widget.

No API key needed. Nothing personal is stored: chat text is not logged,
only anonymous counters for rate limiting.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.agent.kb import get_kb, sync
from app.agent.llm import AnthropicClient, LLMError
from app.agent.service import Agent, run_estimate
from app.config import get_settings
from app.ratelimit import RateLimiter
from app.security import Principal, require

log = logging.getLogger(__name__)
router = APIRouter(tags=["website agent"])


# ---------------------------------------------------------------- schemas
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=60)

    @field_validator("messages")
    @classmethod
    def _ends_with_user(cls, v):
        if v[-1].role != "user":
            raise ValueError("The last message must be from the user")
        return v


class Source(BaseModel):
    title: str
    url: str


class ChatOut(BaseModel):
    reply: str
    sources: list[Source]
    estimate: dict | None = None


class EstimateIn(BaseModel):
    width_ft: float = Field(ge=10, le=200)
    length_ft: float = Field(ge=10, le=400)
    eave_height_ft: float = Field(14, ge=8, le=30)
    roof_pitch: float = Field(3, ge=0.5, le=12)
    overhang_ft: float = Field(1, ge=0, le=4)
    living_sqft: float | None = Field(None, ge=100)
    ceiling_height_ft: float = Field(10, ge=7, le=20)
    slab_thickness_in: float = Field(4, ge=3.5, le=12)
    grade_beam: bool = True
    insulation: Literal["closed_cell", "open_cell"] = "closed_cell"
    framing: Literal["wood", "steel"] = "wood"
    frame_exterior_walls: bool = True
    waste_pct: float = Field(10, ge=0, le=30)


# ---------------------------------------------------------------- dependencies
@lru_cache
def _limiter() -> RateLimiter:
    s = get_settings()
    return RateLimiter(s.public_rate_limit, s.public_rate_window_s, s.agent_daily_limit)


@lru_cache
def _estimate_limiter() -> RateLimiter:
    # Estimates are cheap (no AI call) but still capped per IP.
    return RateLimiter(60, 600, 1_000_000)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def get_agent() -> Agent:
    s = get_settings()
    try:
        llm = AnthropicClient(s.anthropic_api_key, s.agent_model, s.anthropic_base_url)
    except LLMError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The assistant isn't configured yet") from exc
    return Agent(llm, get_kb(), max_tokens=s.agent_max_tokens)


# ---------------------------------------------------------------- routes
@router.post("/public/chat", response_model=ChatOut)
def chat(body: ChatIn, request: Request, agent: Agent = Depends(get_agent)):
    s = get_settings()
    msgs = body.messages
    if len(msgs[-1].content) > s.chat_max_message_chars:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"Please keep messages under {s.chat_max_message_chars} characters"
        )
    ok, reason, retry = _limiter().check(_client_ip(request))
    if not ok:
        detail = (
            "The assistant has reached today's limit. Please try again tomorrow."
            if reason == "daily"
            else "You're sending messages quickly. Please wait a few minutes."
        )
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail, headers={"Retry-After": str(retry)})

    # Keep recent context only; history must start with a user turn.
    history = [m.model_dump() for m in msgs[-s.chat_max_history - 1 :]]
    while history and history[0]["role"] != "user":
        history.pop(0)
    for m in history:
        m["content"] = m["content"][: s.chat_max_message_chars * 2]

    try:
        result = agent.chat(history)
    except LLMError as exc:
        log.error("Agent LLM error: %s", exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "The assistant is having trouble right now. Please try again shortly."
        ) from exc
    log.info("chat ok: in=%s out=%s", result.usage.get("input_tokens"), result.usage.get("output_tokens"))
    return ChatOut(reply=result.reply, sources=result.sources, estimate=result.estimate)


@router.post("/public/estimate")
def public_estimate(body: EstimateIn, request: Request):
    ok, _, retry = _estimate_limiter().check(_client_ip(request))
    if not ok:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many estimates; please wait a few minutes.",
            headers={"Retry-After": str(retry)},
        )
    return run_estimate(body.model_dump(exclude_none=True))


@router.get("/public/status")
def public_status():
    s, kb = get_settings(), get_kb()
    return {
        "assistant_configured": bool(s.anthropic_api_key),
        "knowledge_base": {"articles": kb.article_count, "chunks": len(kb.chunks), "synced_at": kb.synced_at},
    }


@router.post("/admin/kb/refresh")
def refresh_kb(_: Principal = Depends(require("admin"))):
    s = get_settings()
    try:
        n = sync(get_kb(), s.kb_source_url, s.kb_cache_path)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Sync failed: {exc}") from exc
    kb = get_kb()
    return {"articles": kb.article_count, "chunks": n, "synced_at": kb.synced_at}


@router.get("/admin/agent/usage")
def agent_usage(_: Principal = Depends(require("admin"))):
    s = get_settings()
    return {"chats_today": _limiter().used_today, "daily_limit": s.agent_daily_limit}
