"""Subject, attendance, student, assignment and extracurricular endpoints.

Every route resolves the teacher from the signed session, authorizes the
requested subject or student against the database, and only then reads data.
Editing an id in the URL does not widen access.
"""
from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import api_rate_limit, current_teacher, threshold
from app.core.db import get_db
from app.core.security import TeacherPrincipal
from app.schemas import (
    AssessmentOut,
    AssignmentOut,
    GenericDict,
    PaginatedAttendance,
    PaginatedStudents,
    SubjectAnalytics,
    SubjectOut,
)
from app.services import analytics as A

router = APIRouter(prefix="/api", tags=["academics"],
                   dependencies=[Depends(api_rate_limit)])

# Pattern applied to any subject code arriving in a path, before the DB sees it.
SUBJECT_PATTERN = r"^[A-Z]{2,4}\d{4}[A-Z](?:-[A-Z])?$"
STUDENT_PATTERN = r"^STU\d{4}$"


# --------------------------------------------------------------------------
# Dashboard and subjects
# --------------------------------------------------------------------------
@router.get("/teachers/me/dashboard", response_model=GenericDict)
def dashboard(
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
    th: float = Depends(threshold),
) -> GenericDict:
    return A.teacher_dashboard(
        db, principal.teacher_id, sorted(principal.subject_codes), th
    )


@router.get("/teachers/me/subjects", response_model=list[SubjectOut])
def my_subjects(
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
) -> list[SubjectOut]:
    rows = A.list_subjects_for_teacher(db, principal.teacher_id)
    return [SubjectOut(**r) for r in rows]


# --------------------------------------------------------------------------
# Attendance
# --------------------------------------------------------------------------
@router.get("/subjects/{subject_code}/attendance",
            response_model=PaginatedAttendance)
def subject_attendance(
    subject_code: str = Path(..., pattern=SUBJECT_PATTERN),
    division: str | None = Query(default=None, pattern=r"^[A-C]$"),
    search: str | None = Query(default=None, max_length=80),
    below_only: bool = False,
    sort_by: str = Query(default="percentage",
                         pattern=r"^(percentage|name|roll_number|attended)$"),
    sort_dir: str = Query(default="asc", pattern=r"^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
    th: float = Depends(threshold),
) -> PaginatedAttendance:
    principal.require_subject(subject_code)
    result = A.subject_attendance(
        db, subject_code, th, division=division, search=search,
        below_only=below_only, sort_by=sort_by, sort_dir=sort_dir,
        page=page, page_size=page_size,
    )
    return PaginatedAttendance(
        items=result.items, total=result.total, page=result.page,
        page_size=result.page_size, total_pages=result.total_pages, threshold=th,
    )


@router.get("/subjects/{subject_code}/analytics", response_model=SubjectAnalytics)
def subject_analytics(
    subject_code: str = Path(..., pattern=SUBJECT_PATTERN),
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
    th: float = Depends(threshold),
) -> SubjectAnalytics:
    principal.require_subject(subject_code)
    return SubjectAnalytics(**A.subject_attendance_summary(db, subject_code, th))


@router.get("/subjects/{subject_code}/attendance.csv")
def export_attendance_csv(
    subject_code: str = Path(..., pattern=SUBJECT_PATTERN),
    division: str | None = Query(default=None, pattern=r"^[A-C]$"),
    search: str | None = Query(default=None, max_length=80),
    below_only: bool = False,
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
    th: float = Depends(threshold),
) -> Response:
    """Export exactly the rows the same filters would display, nothing wider."""
    principal.require_subject(subject_code)
    # One query for the whole export. An export is bounded by a single subject's
    # enrolment, so this stays small, and it avoids holding a pooled connection
    # across a sequence of paginated round trips.
    all_rows = A.subject_attendance_all(
        db, subject_code, th, division=division, search=search,
        below_only=below_only,
    )

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([
        "student_id", "roll_number", "full_name", "division",
        "classes_attended", "classes_conducted", "attendance_percentage",
        "status",
    ])
    for r in all_rows:
        writer.writerow([
            r["student_id"], r["roll_number"], r["full_name"], r["division"],
            r["classes_attended"], r["classes_conducted"],
            r["attendance_percentage"], r["status"],
        ])

    filename = f"attendance_{subject_code}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


# --------------------------------------------------------------------------
# Academic performance
# --------------------------------------------------------------------------
@router.get("/subjects/{subject_code}/assessments",
            response_model=list[AssessmentOut])
def subject_assessments(
    subject_code: str = Path(..., pattern=SUBJECT_PATTERN),
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
) -> list[AssessmentOut]:
    principal.require_subject(subject_code)
    return [AssessmentOut(**r) for r in A.subject_assessments(db, subject_code)]


@router.get("/subjects/{subject_code}/performance", response_model=GenericDict)
def subject_performance(
    subject_code: str = Path(..., pattern=SUBJECT_PATTERN),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    below: float | None = Query(default=None, ge=0, le=100),
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
) -> GenericDict:
    principal.require_subject(subject_code)
    summary = A.subject_performance_summary(db, subject_code)
    students = summary["students"]
    if below is not None:
        students = [
            s for s in students
            if s["performance_percentage"] is not None
            and s["performance_percentage"] < below
        ]
    total = len(students)
    start = (page - 1) * page_size
    return {
        **summary,
        "students": students[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


# --------------------------------------------------------------------------
# Assignments
# --------------------------------------------------------------------------
@router.get("/subjects/{subject_code}/assignments",
            response_model=list[AssignmentOut])
def subject_assignments(
    subject_code: str = Path(..., pattern=SUBJECT_PATTERN),
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
) -> list[AssignmentOut]:
    principal.require_subject(subject_code)
    return [AssignmentOut(**r) for r in A.assignment_summary(db, subject_code)]


@router.get("/teachers/me/overdue-assignments", response_model=GenericDict)
def overdue(
    subject_code: str | None = Query(default=None, pattern=SUBJECT_PATTERN),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
) -> GenericDict:
    codes = (
        [principal.require_subject(subject_code)] if subject_code
        else sorted(principal.subject_codes)
    )
    rows = A.overdue_assignments(db, codes, limit=1000)
    total = len(rows)
    start = (page - 1) * page_size
    return {
        "as_of_date": date.today(),
        "items": rows[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "definition": (
            "Overdue means nothing was submitted and the due date has passed. "
            "Work submitted but not yet marked is not counted as overdue."
        ),
    }


# --------------------------------------------------------------------------
# Students
# --------------------------------------------------------------------------
@router.get("/teachers/me/students", response_model=PaginatedStudents)
def my_students(
    division: str | None = Query(default=None, pattern=r"^[A-C]$"),
    subject_code: str | None = Query(default=None, pattern=SUBJECT_PATTERN),
    search: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
) -> PaginatedStudents:
    if subject_code:
        principal.require_subject(subject_code)
    result = A.list_students_in_scope(
        db, sorted(principal.subject_codes), division=division,
        subject_code=subject_code, search=search, page=page, page_size=page_size,
    )
    return PaginatedStudents(
        items=result.items, total=result.total, page=result.page,
        page_size=result.page_size, total_pages=result.total_pages,
    )


@router.get("/students/{student_id}/academic-summary", response_model=GenericDict)
def student_summary(
    student_id: str = Path(..., pattern=STUDENT_PATTERN),
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
    th: float = Depends(threshold),
) -> GenericDict:
    principal.require_student(db, student_id)
    summary = A.student_academic_summary(
        db, student_id, sorted(principal.subject_codes), th
    )
    if not summary:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found.")
    return summary


@router.get("/students/{student_id}/activities", response_model=GenericDict)
def student_activities(
    student_id: str = Path(..., pattern=STUDENT_PATTERN),
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
) -> GenericDict:
    """Individual extracurricular record, gated on teaching scope."""
    principal.require_student(db, student_id)
    rows = A.student_activities(db, student_id)
    return {
        "student_id": student_id,
        "activity_count": len(rows),
        "activities": rows,
        "achievements_recorded": sum(1 for r in rows if r.get("achievement")),
    }


# --------------------------------------------------------------------------
# Extracurricular
# --------------------------------------------------------------------------
@router.get("/teachers/me/extracurricular", response_model=GenericDict)
def extracurricular(
    division: str | None = Query(default=None, pattern=r"^[A-C]$"),
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
) -> GenericDict:
    """Aggregate participation across the teacher's scope."""
    return A.extracurricular_summary(
        db, sorted(principal.subject_codes), division=division
    )


@router.get("/department/extracurricular", response_model=GenericDict)
def department_extracurricular(
    principal: TeacherPrincipal = Depends(current_teacher),
    db: Session = Depends(get_db),
) -> GenericDict:
    """Department-wide reporting, restricted to the coordinator role."""
    principal.require_coordinator()
    from sqlalchemy import select

    from app.models import Subject

    all_codes = db.scalars(select(Subject.subject_code)).all()
    return {
        "scope": "department",
        **A.extracurricular_summary(db, list(all_codes)),
    }
