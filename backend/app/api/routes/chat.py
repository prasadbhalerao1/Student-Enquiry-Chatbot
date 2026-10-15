"""Streaming chat and BYOK provider endpoints.

The request carries the teacher's own provider credential. It is used to build a
client for this one call and is never logged, persisted or echoed back.
"""
from __future__ import annotations


import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.ai.model_registry import list_providers
from app.ai.orchestration import _sse, stream_chat, test_provider_connection
from app.ai.provider_factory import ProviderConfig
from app.api.dependencies import (
    api_rate_limit,
    chat_rate_limit,
    current_teacher,
    threshold,
)
from app.core.config import settings
from app.core.db import get_db
from app.core.security import TeacherPrincipal
from app.schemas import (
    ChatRequest,
    GenericDict,
    ProviderSettings,
    ProviderTestRequest,
    ProviderTestResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["ai"])




def _to_config(p: ProviderSettings) -> ProviderConfig:
    return ProviderConfig(
        provider=p.provider,
        model=p.model,
        api_key=p.api_key,
        base_url=p.base_url,
        temperature=p.temperature,
    )


def _server_default() -> ProviderConfig | None:
    """The deployment's own provider, if one is configured."""
    if not settings.has_default_provider:
        return None
    return ProviderConfig(
        provider=settings.default_ai_provider,
        model=settings.default_ai_model,
        api_key=settings.default_ai_api_key or None,
        base_url=settings.default_ai_base_url or None,
    )


def _resolve(p: ProviderSettings | None) -> ProviderConfig | None:
    """A teacher's own configuration wins; otherwise use the server default."""
    return _to_config(p) if p is not None else _server_default()


@router.get("/providers", response_model=list[GenericDict],
            dependencies=[Depends(api_rate_limit)])
def providers() -> list[GenericDict]:
    """Provider catalogue for the Settings page. Contains no credentials."""
    return list_providers()


@router.post("/providers/test-connection", response_model=ProviderTestResponse,
             dependencies=[Depends(chat_rate_limit)])
async def test_connection(
    payload: ProviderTestRequest,
    _: TeacherPrincipal = Depends(current_teacher),
) -> ProviderTestResponse:
    result = await test_provider_connection(_to_config(payload.provider))
    return ProviderTestResponse(**result)


@router.get("/providers/default", response_model=GenericDict,
            dependencies=[Depends(api_rate_limit)])
def default_provider(
    _: TeacherPrincipal = Depends(current_teacher),
) -> GenericDict:
    """Whether this deployment supplies a provider, so the UI can say so.

    Returns the provider and model only. The API key is never included.
    """
    if not settings.has_default_provider:
        return {"configured": False}
    return {
        "configured": True,
        "provider": settings.default_ai_provider,
        "model": settings.default_ai_model,
    }


@router.post("/chat", dependencies=[Depends(chat_rate_limit)])
async def chat(
    payload: ChatRequest,
    request: Request,
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
    th: float = Depends(threshold),
) -> StreamingResponse:
    """Stream one assistant turn as Server-Sent Events.

    Frames: status | tool | token | error | done. Tokens are forwarded as the
    provider emits them; nothing is buffered to completion first.
    """
    history = [{"role": m.role, "content": m.content} for m in payload.messages]
    config = _resolve(payload.provider)

    if config is None:
        # No teacher configuration and no server default. Say so plainly
        # rather than letting the model layer fail with a vaguer message.
        message = (
            "No AI provider is configured. Open Settings to choose a "
            "provider and enter your API key."
        )

        async def refuse():
            yield _sse("error", {"message": message, "kind": "configuration"})
            yield _sse("done", {"ok": False})

        return StreamingResponse(
            refuse(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store"},
        )

    async def generator():
        try:
            async for frame in stream_chat(
                db=db,
                principal=principal,
                config=config,
                history=history,
                threshold=th,
                timeout=settings.upstream_timeout,
            ):
                # Stop promptly when the teacher presses Stop or navigates away.
                if await request.is_disconnected():
                    logger.info("Client disconnected; ending stream")
                    break
                yield frame
        finally:
            db.close()

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            # Stops nginx and similar proxies buffering the stream.
            "X-Accel-Buffering": "no",
        },
    )
