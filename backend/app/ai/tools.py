"""The only database access the model is ever given.

There is no SQL tool and no free-form query tool. Each function below is a fixed,
parameterized operation, and each re-checks the authenticated teacher's scope
against the database before returning anything -- the model is never trusted to
have respected its instructions.

Every tool is bound to one `TeacherPrincipal` and one `Session` through
`build_tools`, so a subject or student id that the model invents simply fails
authorization.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import TeacherPrincipal
from app.services import analytics as A
from app.services.attendance_math import (
    AttendanceInputError,
    attendance_percentage,
    classes_needed_for_target,
)

# Hard caps so a single tool call can never dump the cohort into the context.
MAX_ROWS = 40


class _Denied(dict):
    """A refusal shaped like a normal tool result so the model can relay it."""


def _denied(message: str) -> dict:
    return {"error": "authorization_denied", "message": message}


def _authorize_subject(principal: TeacherPrincipal, subject_code: str) -> str | None:
    """Return None when allowed, or an error dict's message when not."""
    code = (subject_code or "").strip()
    if not code:
        return "A subject code is required."
    if not principal.may_access_subject(code):
        return (
            f"You are not assigned to subject '{code}'. Your authorized "
            f"subjects are: {', '.join(sorted(principal.subject_codes)) or 'none'}."
        )
    return None


def _truncate(rows: list[dict], limit: int = MAX_ROWS) -> tuple[list[dict], bool]:
    return rows[:limit], len(rows) > limit


# --------------------------------------------------------------------------
# Argument schemas
# --------------------------------------------------------------------------
class NoArgs(BaseModel):
    pass


class SubjectArg(BaseModel):
    subject_code: str = Field(description="Subject code, e.g. CB3202T.")


class LowAttendanceArgs(BaseModel):
    subject_code: str | None = Field(
        default=None,
        description="Subject code. Omit to search all subjects you teach.",
    )
    threshold: float | None = Field(
        default=None,
        description="Attendance percentage threshold. Defaults to the configured value.",
    )
    limit: int = Field(default=15, description="Maximum students to return (max 40).")


class StudentArg(BaseModel):
    student_id: str = Field(description="Student ID, e.g. STU0042.")


class StudentTargetArgs(BaseModel):
    student_id: str = Field(description="Student ID, e.g. STU0042.")
    subject_code: str = Field(description="Subject code, e.g. CB3202T.")
    target: float | None = Field(
        default=None,
        description="Target attendance percentage. Defaults to the configured threshold.",
    )


class MarksThresholdArgs(BaseModel):
    subject_code: str = Field(description="Subject code, e.g. CB3202T.")
    threshold_percentage: float = Field(
        description="Performance percentage below which to flag students."
    )
    limit: int = Field(default=15, description="Maximum students to return (max 40).")


class AssignmentSummaryArgs(BaseModel):
    subject_code: str | None = Field(
        default=None, description="Subject code. Omit for all subjects you teach."
    )
    overdue_only: bool = Field(
        default=False,
        description="Return the list of students with genuinely overdue work.",
    )


class ExtracurricularArgs(BaseModel):
    division: str | None = Field(
        default=None, description="Optional division filter, e.g. A, B or C."
    )


class StudentSearchArgs(BaseModel):
    search: str | None = Field(
        default=None, description="Name, roll number or student ID fragment."
    )
    division: str | None = Field(default=None, description="Division filter.")
    limit: int = Field(default=20, description="Maximum students to return (max 40).")


# --------------------------------------------------------------------------
# Tool factory
# --------------------------------------------------------------------------
def build_tools(
    db: Session,
    principal: TeacherPrincipal,
    threshold: float,
    *,
    today: date | None = None,
) -> list[StructuredTool]:
    """Bind the tool set to one authenticated teacher and one DB session."""
    today = today or date.today()
    scope = sorted(principal.subject_codes)

    # ---- attendance ----------------------------------------------------
    def get_teacher_subjects() -> dict:
        subjects = A.list_subjects_for_teacher(db, principal.teacher_id)
        return {
            "teacher": principal.full_name,
            "is_department_coordinator": principal.is_coordinator,
            "subject_count": len(subjects),
            "subjects": subjects,
            "attendance_threshold": threshold,
            "threshold_note": (
                "Illustrative application setting, not a verified college regulation."
            ),
        }

    def get_subject_attendance_summary(subject_code: str) -> dict:
        if (msg := _authorize_subject(principal, subject_code)):
            return _denied(msg)
        return A.subject_attendance_summary(db, subject_code.strip(), threshold)

    def get_low_attendance_students(
        subject_code: str | None = None,
        threshold_value: float | None = None,
        limit: int = 15,
    ) -> dict:
        if subject_code:
            if (msg := _authorize_subject(principal, subject_code)):
                return _denied(msg)
            codes = [subject_code.strip()]
        else:
            codes = scope
        if not codes:
            return _denied("You have no assigned subjects.")

        used = threshold_value if threshold_value is not None else threshold
        rows = A.low_attendance_students(db, codes, used, limit=min(limit, MAX_ROWS))
        return {
            "threshold_applied": used,
            "subjects_searched": codes,
            "returned_count": len(rows),
            "students": rows,
            "note": (
                "Results are limited to the most affected students. Use the "
                "Attendance Analytics page for the full paginated list and CSV export."
            ),
        }

    def get_student_attendance(student_id: str) -> dict:
        sid = (student_id or "").strip()
        try:
            principal.require_student(db, sid)
        except Exception:
            return _denied(
                f"Student '{sid}' is not enrolled in any subject you teach, "
                "or does not exist."
            )
        rows = A.student_attendance(db, sid, scope, threshold)
        return {
            "student_id": sid,
            "threshold": threshold,
            "subjects_in_your_scope": len(rows),
            "attendance": rows,
        }

    def get_classes_needed_for_target(
        student_id: str, subject_code: str, target: float | None = None
    ) -> dict:
        if (msg := _authorize_subject(principal, subject_code)):
            return _denied(msg)
        sid = (student_id or "").strip()
        try:
            principal.require_student(db, sid)
        except Exception:
            return _denied(f"Student '{sid}' is not in your teaching scope.")

        rows = A.student_attendance(db, sid, [subject_code.strip()], threshold)
        if not rows:
            return {"error": "not_found",
                    "message": f"No attendance record for {sid} in {subject_code}."}

        row = rows[0]
        used = target if target is not None else threshold
        try:
            needed = classes_needed_for_target(
                row["classes_attended"], row["classes_conducted"], used
            )
        except AttendanceInputError as exc:
            return {"error": "invalid_input", "message": str(exc)}

        return {
            "student_id": sid,
            "subject_code": row["subject_code"],
            "classes_attended": row["classes_attended"],
            "classes_conducted": row["classes_conducted"],
            "current_percentage": row["attendance_percentage"],
            "target_percentage": used,
            "consecutive_classes_required": needed,
            "assumption": (
                "Assumes the student attends every one of these future classes "
                "and that no other classes are conducted in the meantime."
            ),
        }

    # ---- academic ------------------------------------------------------
    def get_subject_performance_summary(subject_code: str) -> dict:
        if (msg := _authorize_subject(principal, subject_code)):
            return _denied(msg)
        summary = A.subject_performance_summary(db, subject_code.strip())
        students, truncated = _truncate(summary.get("students", []))
        return {
            **summary,
            "students": students,
            "students_truncated": truncated,
            "total_students": len(summary.get("students", [])),
        }

    def get_students_below_marks_threshold(
        subject_code: str, threshold_percentage: float, limit: int = 15
    ) -> dict:
        if (msg := _authorize_subject(principal, subject_code)):
            return _denied(msg)
        rows = A.students_below_marks_threshold(
            db, subject_code.strip(), threshold_percentage,
            limit=min(limit, MAX_ROWS),
        )
        return {
            "subject_code": subject_code.strip(),
            "marks_threshold_percentage": threshold_percentage,
            "returned_count": len(rows),
            "students": rows,
            "note": (
                "Scores are weighted means over assessments the student was "
                "actually evaluated on. Unevaluated work is excluded, not zeroed."
            ),
        }

    # ---- assignments ---------------------------------------------------
    def get_assignment_submission_summary(
        subject_code: str | None = None, overdue_only: bool = False
    ) -> dict:
        if subject_code:
            if (msg := _authorize_subject(principal, subject_code)):
                return _denied(msg)
            codes = [subject_code.strip()]
        else:
            codes = scope
        if not codes:
            return _denied("You have no assigned subjects.")

        if overdue_only:
            rows = A.overdue_assignments(db, codes, today=today, limit=MAX_ROWS)
            return {
                "as_of_date": today.isoformat(),
                "subjects_searched": codes,
                "returned_count": len(rows),
                "overdue_records": rows,
                "definition": (
                    "Overdue = nothing submitted AND the due date has passed. "
                    "Work submitted but not yet marked is not overdue."
                ),
            }

        out = []
        for code in codes:
            out.extend(A.assignment_summary(db, code, today=today))
        return {
            "as_of_date": today.isoformat(),
            "subjects_searched": codes,
            "assignment_count": len(out),
            "assignments": out[:MAX_ROWS],
        }

    def get_student_assignment_status(student_id: str) -> dict:
        sid = (student_id or "").strip()
        try:
            principal.require_student(db, sid)
        except Exception:
            return _denied(f"Student '{sid}' is not in your teaching scope.")
        rows = A.student_assignment_status(db, sid, scope, today=today)
        return {
            "student_id": sid,
            "as_of_date": today.isoformat(),
            "assignment_count": len(rows),
            "assignments": rows[:MAX_ROWS],
            "overdue_count": sum(1 for r in rows if r["is_overdue"]),
        }

    # ---- extracurricular -----------------------------------------------
    def get_extracurricular_summary(division: str | None = None) -> dict:
        if not scope:
            return _denied("You have no assigned subjects.")
        summary = A.extracurricular_summary(db, scope, division=division)
        return {
            **summary,
            "division_filter": division,
            "note": (
                "Aggregate counts only. Individual participation profiles require "
                "a specific student lookup within your teaching scope."
            ),
        }

    def get_student_extracurricular(student_id: str) -> dict:
        sid = (student_id or "").strip()
        try:
            principal.require_student(db, sid)
        except Exception:
            return _denied(
                f"Student '{sid}' is not in your teaching scope, so their "
                "extracurricular profile is not available to you."
            )
        rows = A.student_activities(db, sid)
        return {
            "student_id": sid,
            "activity_count": len(rows),
            "activities": rows[:MAX_ROWS],
            "achievements_recorded": sum(1 for r in rows if r.get("achievement")),
        }

    # ---- students ------------------------------------------------------
    def get_student_academic_summary(student_id: str) -> dict:
        sid = (student_id or "").strip()
        try:
            principal.require_student(db, sid)
        except Exception:
            return _denied(f"Student '{sid}' is not in your teaching scope.")
        summary = A.student_academic_summary(db, sid, scope, threshold)
        if not summary:
            return {"error": "not_found", "message": f"No record for {sid}."}
        # Keep the payload small: counts plus the attendance table.
        summary["assessments"] = summary["assessments"][:MAX_ROWS]
        summary["assignments"] = summary["assignments"][:MAX_ROWS]
        return summary

    def find_students(
        search: str | None = None, division: str | None = None, limit: int = 20
    ) -> dict:
        if not scope:
            return _denied("You have no assigned subjects.")
        page = A.list_students_in_scope(
            db, scope, division=division, search=search,
            page=1, page_size=min(limit, MAX_ROWS),
        )
        return {
            "matched_total": page.total,
            "returned_count": len(page.items),
            "students": page.items,
            "truncated": page.total > len(page.items),
        }

    # ---- bind ----------------------------------------------------------
    return [
        StructuredTool.from_function(
            func=get_teacher_subjects,
            name="get_teacher_subjects",
            description=(
                "List the subjects this teacher is authorized to access, with "
                "enrolment counts and aggregate attendance. Call this first when "
                "you need to know the teacher's scope."
            ),
            args_schema=NoArgs,
        ),
        StructuredTool.from_function(
            func=get_subject_attendance_summary,
            name="get_subject_attendance_summary",
            description=(
                "Aggregate attendance statistics for one subject: enrolment, "
                "pooled and mean percentages, and how many students fall below "
                "the configured threshold."
            ),
            args_schema=SubjectArg,
        ),
        StructuredTool.from_function(
            func=lambda subject_code=None, threshold=None, limit=15: (
                get_low_attendance_students(subject_code, threshold, limit)
            ),
            name="get_low_attendance_students",
            description=(
                "List students below an attendance threshold, lowest first, with "
                "the number of consecutive classes each would need to recover."
            ),
            args_schema=LowAttendanceArgs,
        ),
        StructuredTool.from_function(
            func=get_student_attendance,
            name="get_student_attendance",
            description=(
                "One student's attendance across every subject you teach, with "
                "status against the threshold."
            ),
            args_schema=StudentArg,
        ),
        StructuredTool.from_function(
            func=get_classes_needed_for_target,
            name="get_classes_needed_for_target",
            description=(
                "Deterministically compute how many consecutive future classes a "
                "student must attend to reach a target attendance percentage. "
                "Always use this instead of calculating it yourself."
            ),
            args_schema=StudentTargetArgs,
        ),
        StructuredTool.from_function(
            func=get_subject_performance_summary,
            name="get_subject_performance_summary",
            description=(
                "Academic performance for one subject: per-student weighted "
                "scores, class average, grade distribution, and counts of "
                "unevaluated and absent results."
            ),
            args_schema=SubjectArg,
        ),
        StructuredTool.from_function(
            func=get_students_below_marks_threshold,
            name="get_students_below_marks_threshold",
            description=(
                "Students whose weighted performance percentage in a subject is "
                "below a given value."
            ),
            args_schema=MarksThresholdArgs,
        ),
        StructuredTool.from_function(
            func=get_assignment_submission_summary,
            name="get_assignment_submission_summary",
            description=(
                "Assignment submission rollups for your subjects. Set "
                "overdue_only=true to list students who never submitted work "
                "whose due date has passed."
            ),
            args_schema=AssignmentSummaryArgs,
        ),
        StructuredTool.from_function(
            func=get_student_assignment_status,
            name="get_student_assignment_status",
            description=(
                "One student's assignment submissions across your subjects, "
                "distinguishing pending, submitted, evaluated and overdue."
            ),
            args_schema=StudentArg,
        ),
        StructuredTool.from_function(
            func=get_extracurricular_summary,
            name="get_extracurricular_summary",
            description=(
                "Aggregate extracurricular participation for students in your "
                "teaching scope: category and role counts, participation rate "
                "and recorded achievements. Use this for class-level questions."
            ),
            args_schema=ExtracurricularArgs,
        ),
        StructuredTool.from_function(
            func=get_student_extracurricular,
            name="get_student_extracurricular",
            description=(
                "One student's individual extracurricular record. Only available "
                "for students in your teaching scope."
            ),
            args_schema=StudentArg,
        ),
        StructuredTool.from_function(
            func=get_student_academic_summary,
            name="get_student_academic_summary",
            description=(
                "Combined attendance, marks and assignment picture for one "
                "student, limited to the subjects you teach."
            ),
            args_schema=StudentArg,
        ),
        StructuredTool.from_function(
            func=find_students,
            name="find_students",
            description=(
                "Look up students in your teaching scope by name, roll number or "
                "ID. Use this to resolve a student ID before calling other tools."
            ),
            args_schema=StudentSearchArgs,
        ),
    ]


def serialize_tool_result(value: Any) -> str:
    """JSON-encode a tool result, handling dates."""
    return json.dumps(value, default=str, ensure_ascii=False)
