"""Demo faculty sessions and server-side authorization.

DEMONSTRATION AUTHENTICATION ONLY.
There is no password, no identity provider and no audit trail. A caller picks a
teacher from a list and the server issues a signed cookie for them. This is fine
for a synthetic-data demo and is NOT suitable for real institutional records.
See the README section "Before using real college records".

What IS real here is the authorization model: once a session exists, every
permission decision is made on the server from the `teacher_subjects` table.
A teacher id, subject code or student id supplied by a client is never trusted.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import HTTPException, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Attendance, Teacher, TeacherSubject

SESSION_COOKIE = "csbs_faculty_session"
_serializer = URLSafeTimedSerializer(settings.session_secret, salt="faculty-session")


def issue_session(teacher_id: str) -> str:
    """Sign a teacher id into an opaque, tamper-evident cookie value."""
    return _serializer.dumps({"teacher_id": teacher_id})


def read_session(token: str) -> str | None:
    """Return the teacher id from a cookie, or None if absent/forged/expired."""
    try:
        data = _serializer.loads(token, max_age=settings.session_max_age)
    except (BadSignature, SignatureExpired):
        return None
    teacher_id = data.get("teacher_id") if isinstance(data, dict) else None
    return teacher_id if isinstance(teacher_id, str) else None


@dataclass
class TeacherPrincipal:
    """The authenticated teacher plus their resolved, server-side scope."""

    teacher_id: str
    full_name: str
    email: str
    department: str
    designation: str
    is_coordinator: bool
    subject_codes: frozenset[str] = field(default_factory=frozenset)

    # ---- subject scope -------------------------------------------------
    def may_access_subject(self, subject_code: str) -> bool:
        return subject_code in self.subject_codes

    def require_subject(self, subject_code: str) -> str:
        """Authorize a subject, or raise 403. Returns the code when allowed.

        The same 403 is returned for "not yours" and "does not exist" so the
        endpoint cannot be used to enumerate the subject catalogue.
        """
        if not self.may_access_subject(subject_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this subject.",
            )
        return subject_code

    def scoped_subjects(self, requested: list[str] | None) -> list[str]:
        """Narrow a requested subject list to the permitted set, or raise 403."""
        if not requested:
            return sorted(self.subject_codes)
        return [self.require_subject(code) for code in requested]

    # ---- student scope -------------------------------------------------
    def require_student(self, db: Session, student_id: str) -> str:
        """A student is in scope only if enrolled in a subject this teacher teaches."""
        if not self.subject_codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You have no assigned subjects.",
            )
        enrolled = db.scalar(
            select(Attendance.student_id)
            .where(
                Attendance.student_id == student_id,
                Attendance.subject_code.in_(self.subject_codes),
            )
            .limit(1)
        )
        if enrolled is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This student is not enrolled in any subject you teach.",
            )
        return student_id

    def require_coordinator(self) -> None:
        """Gate department-wide reporting behind the explicit coordinator role."""
        if not self.is_coordinator:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Department-wide reporting requires the department "
                    "coordinator role."
                ),
            )


def load_principal(db: Session, teacher_id: str) -> TeacherPrincipal | None:
    """Build a principal by reading the teacher and their scope from the DB."""
    teacher = db.get(Teacher, teacher_id)
    if teacher is None:
        return None
    codes = db.scalars(
        select(TeacherSubject.subject_code).where(
            TeacherSubject.teacher_id == teacher_id
        )
    ).all()
    return TeacherPrincipal(
        teacher_id=teacher.teacher_id,
        full_name=teacher.full_name,
        email=teacher.email,
        department=teacher.department,
        designation=teacher.designation,
        is_coordinator=teacher.is_department_coordinator,
        subject_codes=frozenset(codes),
    )
