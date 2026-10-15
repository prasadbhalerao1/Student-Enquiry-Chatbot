"""FastAPI application entrypoint.

    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import academics, auth, chat
from app.core.config import settings
from app.core.db import engine
from app.core.logging import configure_logging
from app.schemas import Health

configure_logging()
logger = logging.getLogger(__name__)

SYNTHETIC_NOTICE = (
    "All records served by this API are synthetic demonstration data. They are "
    "not official institutional records."
)

MAX_BODY_BYTES = 256 * 1024  # 256 KB is ample for a chat transcript.

app = FastAPI(
    title="CSBS Faculty Assistant API",
    version="1.0.0",
    description=(
        "Teacher-facing student information API for a third-year CSBS "
        "department. Demonstration authentication; synthetic data only."
    ),
)

# Exact origin only -- never a wildcard, because the session cookie is credentialed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=600,
)


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    """Reject oversized bodies before they are parsed."""
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"detail": "Request body too large."},
        )
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    # Student records must never be cached by an intermediary.
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    """Never leak a stack trace or driver message to a client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred."},
    )


@app.get("/api/health", response_model=Health, tags=["meta"])
def health() -> Health:
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        db_state = "connected"
    except Exception:
        logger.warning("Health check could not reach the database")
        db_state = "unavailable"
    return Health(
        status="ok", database=db_state, synthetic_data_notice=SYNTHETIC_NOTICE
    )


app.include_router(auth.router)
app.include_router(academics.router)
app.include_router(chat.router)
