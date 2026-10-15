"""Demo faculty session endpoints.

DEMONSTRATION AUTHENTICATION. Choosing a teacher from a list is enough to be
issued a session; there is no credential check. See the README for what real
institutional deployment would require.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import current_teacher, session_rate_limit
from app.core.config import settings
from app.core.db import get_db
from app.core.security import (
    SESSION_COOKIE,
    TeacherPrincipal,
    issue_session,
    load_principal,
)
from app.models import Teacher, TeacherSubject
from app.schemas import DemoSessionRequest, DemoTeacherOption, TeacherProfile

router = APIRouter(prefix="/api", tags=["session"])

THRESHOLD_NOTE = (
    "This attendance threshold is an illustrative application setting, not a "
    "verified college regulation."
)


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        # Cross-site in deployment (Vercel frontend -> separate backend host),
        # so the cookie must be SameSite=None and therefore Secure.
        samesite="none" if settings.cookie_secure else "lax",
        max_age=settings.session_max_age,
        path="/",
    )


@router.get("/demo-teachers", response_model=list[DemoTeacherOption])
def list_demo_teachers(db: Session = Depends(get_db)) -> list[DemoTeacherOption]:
    """The faculty picker. Public so the login screen can render before sign-in.

    Returns only names and assignments that already appear in the public subject
    catalogue -- no emails and nothing that could serve as a credential.
    """
    teachers = db.scalars(select(Teacher).order_by(Teacher.teacher_id)).all()
    out = []
    for t in teachers:
        codes = db.scalars(
            select(TeacherSubject.subject_code)
            .where(TeacherSubject.teacher_id == t.teacher_id)
            .order_by(TeacherSubject.subject_code)
        ).all()
        out.append(DemoTeacherOption(
            teacher_id=t.teacher_id,
            full_name=t.full_name,
            designation=t.designation,
            department=t.department,
            is_department_coordinator=t.is_department_coordinator,
            subject_codes=list(codes),
        ))
    return out


@router.post("/demo-session", response_model=TeacherProfile)
def create_demo_session(
    payload: DemoSessionRequest,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(session_rate_limit),
) -> TeacherProfile:
    """Issue a signed session for a demo faculty member."""
    principal = load_principal(db, payload.teacher_id)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such demo faculty account.",
        )
    _set_cookie(response, issue_session(principal.teacher_id))
    return _profile(principal)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/teachers/me", response_model=TeacherProfile)
def get_me(
    principal: TeacherPrincipal = Depends(current_teacher),
) -> TeacherProfile:
    return _profile(principal)


def _profile(principal: TeacherPrincipal) -> TeacherProfile:
    return TeacherProfile(
        teacher_id=principal.teacher_id,
        full_name=principal.full_name,
        email=principal.email,
        department=principal.department,
        designation=principal.designation,
        is_department_coordinator=principal.is_coordinator,
        subject_codes=sorted(principal.subject_codes),
        attendance_threshold=settings.attendance_threshold,
        threshold_note=THRESHOLD_NOTE,
    )
