"""Shared FastAPI dependencies: DB session, authenticated principal, rate limit."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import SESSION_COOKIE, TeacherPrincipal, load_principal, read_session


def current_teacher(
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> TeacherPrincipal:
    """Resolve the signed session cookie into a scoped principal.

    The teacher id comes only from the signed cookie. A teacher id in a request
    body, query string or chat message is never consulted.
    """
    if not session_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active faculty session. Sign in from the demo faculty picker.",
        )
    teacher_id = read_session(session_cookie)
    if teacher_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session is invalid or has expired. Sign in again.",
        )
    principal = load_principal(db, teacher_id)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The faculty account for this session no longer exists.",
        )
    return principal


def threshold() -> float:
    return settings.attendance_threshold


# --------------------------------------------------------------------------
# A small in-process rate limiter.
#
# Adequate for a single-instance demo deployment. A multi-instance deployment
# needs a shared store (Redis) instead; this is documented in the README.
# --------------------------------------------------------------------------
_HITS: dict[str, deque[float]] = defaultdict(deque)


class RateLimit:
    def __init__(self, limit: int, window_seconds: int, scope: str) -> None:
        self.limit = limit
        self.window = window_seconds
        self.scope = scope

    def __call__(self, request: Request) -> None:  # noqa: D401
        client = request.client.host if request.client else "unknown"
        key = f"{self.scope}:{client}"
        now = time.monotonic()
        hits = _HITS[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait a moment and try again.",
                headers={"Retry-After": str(self.window)},
            )
        hits.append(now)


def _limiter(limit: int, window: int, scope: str):
    """Wrap a RateLimit in a plain function so FastAPI reads the signature."""
    guard = RateLimit(limit, window, scope)

    def dependency(request: Request) -> None:
        guard(request)

    return dependency


chat_rate_limit = _limiter(20, 60, "chat")
api_rate_limit = _limiter(240, 60, "api")
session_rate_limit = _limiter(30, 60, "session")
