"""Deterministic business logic shared by the REST API and the AI tools.

Every function here takes an already-authorized scope (subject codes that the
caller has proven the teacher may see). Authorization itself lives in
`app.core.security`; these functions assume it has already happened.

All attendance arithmetic is delegated to `attendance_math` so there is exactly
one implementation of the percentage formula in the codebase.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Integer, Select, func, select
from sqlalchemy.orm import Session

from app.models import (
    Assessment,
    Assignment,
    Attendance,
    ExtracurricularActivity,
    Grade,
    Student,
    StudentActivity,
    StudentAssignment,
    Subject,
    Teacher,
    TeacherSubject,
)
from app.services.attendance_math import (
    aggregate_percentage,
    attendance_percentage,
    classes_needed_for_target,
    is_below_threshold,
    mean_student_percentage,
)

MAX_PAGE_SIZE = 200


# --------------------------------------------------------------------------
# Subjects
# --------------------------------------------------------------------------
def list_subjects_for_teacher(db: Session, teacher_id: str) -> list[dict]:
    """Subjects assigned to a teacher, with enrolment and attendance rollups."""
    rows = db.execute(
        select(Subject)
        .join(TeacherSubject, TeacherSubject.subject_code == Subject.subject_code)
        .where(TeacherSubject.teacher_id == teacher_id)
        .order_by(Subject.subject_code)
    ).scalars().all()

    out = []
    for subject in rows:
        counts = db.execute(
            select(Attendance.classes_attended, Attendance.classes_conducted)
            .where(Attendance.subject_code == subject.subject_code)
        ).all()
        pairs = [(a, c) for a, c in counts]
        faculty = db.scalar(
            select(Teacher.full_name)
            .join(TeacherSubject, TeacherSubject.teacher_id == Teacher.teacher_id)
            .where(TeacherSubject.subject_code == subject.subject_code)
            .limit(1)
        )
        out.append({
            "subject_code": subject.subject_code,
            "subject_name": subject.subject_name,
            "subject_type": subject.subject_type,
            "credits": subject.credits,
            "faculty_name": faculty,
            "enrolled_students": len(pairs),
            "class_attendance_percentage": aggregate_percentage(pairs),
            "mean_student_attendance_percentage": mean_student_percentage(pairs),
        })
    return out


def get_subject(db: Session, subject_code: str) -> Subject | None:
    return db.get(Subject, subject_code)


# --------------------------------------------------------------------------
# Attendance
# --------------------------------------------------------------------------
@dataclass
class Page:
    items: list[dict]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return max(1, -(-self.total // self.page_size))


def _attendance_rows_query(subject_code: str, division: str | None) -> Select:
    q = (
        select(
            Student.student_id,
            Student.full_name,
            Student.roll_number,
            Student.division,
            Attendance.classes_attended,
            Attendance.classes_conducted,
        )
        .join(Attendance, Attendance.student_id == Student.student_id)
        .where(Attendance.subject_code == subject_code)
    )
    if division:
        q = q.where(Student.division == division)
    return q


def subject_attendance(
    db: Session,
    subject_code: str,
    threshold: float,
    *,
    division: str | None = None,
    search: str | None = None,
    below_only: bool = False,
    sort_by: str = "percentage",
    sort_dir: str = "asc",
    page: int = 1,
    page_size: int = 50,
) -> Page:
    """Paginated per-student attendance for one subject.

    Filtering by percentage and sorting by percentage happen in Python because
    the percentage is derived by the central helper rather than stored.
    """
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    q = _attendance_rows_query(subject_code, division)
    if search:
        pattern = f"%{search.strip()}%"
        q = q.where(
            Student.full_name.ilike(pattern) | Student.roll_number.ilike(pattern)
        )

    records = []
    for sid, name, roll, div, attended, conducted in db.execute(q).all():
        below = is_below_threshold(attended, conducted, threshold)
        if below_only and not below:
            continue
        records.append({
            "student_id": sid,
            "full_name": name,
            "roll_number": roll,
            "division": div,
            "classes_attended": attended,
            "classes_conducted": conducted,
            "attendance_percentage": attendance_percentage(attended, conducted),
            "below_threshold": below,
            "status": _status_label(attended, conducted, threshold),
        })

    reverse = sort_dir.lower() == "desc"
    key_map = {
        "percentage": lambda r: r["attendance_percentage"],
        "name": lambda r: r["full_name"],
        "roll_number": lambda r: r["roll_number"],
        "attended": lambda r: r["classes_attended"],
    }
    records.sort(key=key_map.get(sort_by, key_map["percentage"]), reverse=reverse)

    total = len(records)
    start = (max(1, page) - 1) * page_size
    return Page(records[start:start + page_size], total, max(1, page), page_size)


def subject_attendance_all(
    db: Session,
    subject_code: str,
    threshold: float,
    *,
    division: str | None = None,
    search: str | None = None,
    below_only: bool = False,
) -> list[dict]:
    """Every matching row for one subject, unpaginated, for CSV export.

    Bounded by a single subject's enrolment, so it is safe to materialise.
    """
    q = _attendance_rows_query(subject_code, division)
    if search:
        pattern = f"%{search.strip()}%"
        q = q.where(
            Student.full_name.ilike(pattern) | Student.roll_number.ilike(pattern)
        )

    out = []
    for sid, name, roll, div, attended, conducted in db.execute(q).all():
        below = is_below_threshold(attended, conducted, threshold)
        if below_only and not below:
            continue
        out.append({
            "student_id": sid,
            "full_name": name,
            "roll_number": roll,
            "division": div,
            "classes_attended": attended,
            "classes_conducted": conducted,
            "attendance_percentage": attendance_percentage(attended, conducted),
            "below_threshold": below,
            "status": _status_label(attended, conducted, threshold),
        })
    out.sort(key=lambda r: r["attendance_percentage"])
    return out


def _status_label(attended: int, conducted: int, threshold: float) -> str:
    """Accessible text status, never conveyed by colour alone."""
    pct = attendance_percentage(attended, conducted)
    if is_below_threshold(attended, conducted, threshold):
        return "Below threshold"
    if pct < threshold + 5:
        return "At risk"
    return "Meeting threshold"


def subject_attendance_summary(
    db: Session, subject_code: str, threshold: float
) -> dict:
    """Aggregate attendance statistics for one subject."""
    pairs = db.execute(
        select(Attendance.classes_attended, Attendance.classes_conducted)
        .where(Attendance.subject_code == subject_code)
    ).all()
    pairs = [(a, c) for a, c in pairs]
    subject = db.get(Subject, subject_code)

    below = sum(1 for a, c in pairs if is_below_threshold(a, c, threshold))
    percentages = [attendance_percentage(a, c) for a, c in pairs]

    return {
        "subject_code": subject_code,
        "subject_name": subject.subject_name if subject else None,
        "subject_type": subject.subject_type if subject else None,
        "enrolled_students": len(pairs),
        "classes_conducted": pairs[0][1] if pairs else 0,
        "threshold": threshold,
        # Pooled: every CLASS counts equally (sum attended / sum conducted).
        "class_attendance_percentage": aggregate_percentage(pairs),
        # Unweighted: every STUDENT counts equally.
        "mean_student_attendance_percentage": mean_student_percentage(pairs),
        "students_below_threshold": below,
        "students_meeting_threshold": len(pairs) - below,
        "lowest_percentage": min(percentages) if percentages else None,
        "highest_percentage": max(percentages) if percentages else None,
    }


def low_attendance_students(
    db: Session,
    subject_codes: Sequence[str],
    threshold: float,
) -> list[dict]:
    """ALL student-subject records below `threshold`, worst first.

    Returns the complete list. Callers that need a shorter list truncate it
    themselves AND report the full count, so a reader is never shown a
    truncated list without being told how many records actually matched.
    """
    rows = db.execute(
        select(
            Student.student_id,
            Student.full_name,
            Student.roll_number,
            Student.division,
            Attendance.subject_code,
            Attendance.classes_attended,
            Attendance.classes_conducted,
        )
        .join(Attendance, Attendance.student_id == Student.student_id)
        .where(Attendance.subject_code.in_(list(subject_codes)))
    ).all()

    out = []
    for sid, name, roll, div, code, attended, conducted in rows:
        if not is_below_threshold(attended, conducted, threshold):
            continue
        out.append({
            "student_id": sid,
            "full_name": name,
            "roll_number": roll,
            "division": div,
            "subject_code": code,
            "classes_attended": attended,
            "classes_conducted": conducted,
            "attendance_percentage": attendance_percentage(attended, conducted),
            "classes_needed_for_threshold": classes_needed_for_target(
                attended, conducted, threshold
            ),
        })
    out.sort(key=lambda r: r["attendance_percentage"])
    return out


def student_attendance(
    db: Session, student_id: str, subject_codes: Sequence[str], threshold: float
) -> list[dict]:
    """One student's attendance across the teacher's authorized subjects."""
    rows = db.execute(
        select(
            Attendance.subject_code,
            Subject.subject_name,
            Attendance.classes_attended,
            Attendance.classes_conducted,
        )
        .join(Subject, Subject.subject_code == Attendance.subject_code)
        .where(
            Attendance.student_id == student_id,
            Attendance.subject_code.in_(list(subject_codes)),
        )
        .order_by(Attendance.subject_code)
    ).all()

    return [
        {
            "subject_code": code,
            "subject_name": name,
            "classes_attended": attended,
            "classes_conducted": conducted,
            "attendance_percentage": attendance_percentage(attended, conducted),
            "below_threshold": is_below_threshold(attended, conducted, threshold),
            "status": _status_label(attended, conducted, threshold),
            "classes_needed_for_threshold": classes_needed_for_target(
                attended, conducted, threshold
            ),
        }
        for code, name, attended, conducted in rows
    ]


# --------------------------------------------------------------------------
# Academic performance
# --------------------------------------------------------------------------
def subject_assessments(db: Session, subject_code: str) -> list[dict]:
    """Assessment definitions for a subject with evaluation progress."""
    assessments = db.scalars(
        select(Assessment)
        .where(Assessment.subject_code == subject_code)
        .order_by(Assessment.assessment_date)
    ).all()

    out = []
    for a in assessments:
        stats = db.execute(
            select(
                func.count(Grade.id),
                func.count(Grade.marks_obtained),
                func.avg(Grade.marks_obtained),
                func.sum(func.cast(Grade.is_absent, Integer)),
            ).where(Grade.assessment_id == a.assessment_id)
        ).one()
        total, evaluated, avg_marks, absent = stats
        out.append({
            "assessment_id": a.assessment_id,
            "subject_code": a.subject_code,
            "title": a.title,
            "assessment_type": a.assessment_type,
            "max_marks": a.max_marks,
            "assessment_date": a.assessment_date,
            "weightage": a.weightage,
            "total_students": total or 0,
            # Evaluated = a recorded mark. A blank mark is NOT a zero.
            "evaluated_count": evaluated or 0,
            "pending_evaluation_count": (total or 0) - (evaluated or 0),
            "absent_count": int(absent or 0),
            "average_marks": round(float(avg_marks), 2) if avg_marks is not None else None,
            "average_percentage": (
                round(float(avg_marks) / a.max_marks * 100, 2)
                if avg_marks is not None else None
            ),
        })
    return out


def subject_performance_summary(db: Session, subject_code: str) -> dict:
    """Weighted per-student performance for a subject.

    A student's score is the weighted mean of the assessments they were actually
    evaluated on. Unevaluated assessments are excluded from the denominator
    rather than counted as zero.
    """
    assessments = db.scalars(
        select(Assessment).where(Assessment.subject_code == subject_code)
    ).all()
    if not assessments:
        return {
            "subject_code": subject_code,
            "assessment_count": 0,
            "students": [],
            "class_average_percentage": None,
            "distribution": {},
            "note": "No assessments recorded for this subject.",
        }

    by_id = {a.assessment_id: a for a in assessments}
    rows = db.execute(
        select(
            Grade.student_id,
            Grade.assessment_id,
            Grade.marks_obtained,
            Grade.is_absent,
            Student.full_name,
            Student.roll_number,
            Student.division,
        )
        .join(Student, Student.student_id == Grade.student_id)
        .where(Grade.assessment_id.in_(list(by_id)))
    ).all()

    acc: dict[str, dict] = {}
    for sid, aid, marks, absent, name, roll, div in rows:
        entry = acc.setdefault(sid, {
            "student_id": sid, "full_name": name, "roll_number": roll,
            "division": div, "weighted_score": 0.0, "weight_total": 0.0,
            "evaluated_count": 0, "missing_count": 0, "absent_count": 0,
        })
        assessment = by_id[aid]
        if marks is None:
            entry["missing_count"] += 1
            if absent:
                entry["absent_count"] += 1
            continue
        entry["evaluated_count"] += 1
        entry["weighted_score"] += (marks / assessment.max_marks) * assessment.weightage
        entry["weight_total"] += assessment.weightage

    students = []
    for entry in acc.values():
        pct = (
            round(entry["weighted_score"] / entry["weight_total"] * 100, 2)
            if entry["weight_total"] > 0 else None
        )
        students.append({
            "student_id": entry["student_id"],
            "full_name": entry["full_name"],
            "roll_number": entry["roll_number"],
            "division": entry["division"],
            "performance_percentage": pct,
            "evaluated_count": entry["evaluated_count"],
            "missing_count": entry["missing_count"],
            "absent_count": entry["absent_count"],
        })
    students.sort(key=lambda s: (s["performance_percentage"] is None,
                                 -(s["performance_percentage"] or 0)))

    scored = [s["performance_percentage"] for s in students
              if s["performance_percentage"] is not None]
    buckets = {"0-40": 0, "40-55": 0, "55-70": 0, "70-85": 0, "85-100": 0}
    for p in scored:
        key = ("0-40" if p < 40 else "40-55" if p < 55 else
               "55-70" if p < 70 else "70-85" if p < 85 else "85-100")
        buckets[key] += 1

    return {
        "subject_code": subject_code,
        "assessment_count": len(assessments),
        "students": students,
        "evaluated_students": len(scored),
        "class_average_percentage": (
            round(sum(scored) / len(scored), 2) if scored else None
        ),
        "distribution": buckets,
        "calculation_note": (
            "Each student's score is the weighted mean of the assessments they "
            "were evaluated on. Unevaluated assessments are excluded from the "
            "denominator and are not treated as zero."
        ),
    }


def students_below_marks_threshold(
    db: Session, subject_code: str, threshold_percentage: float
) -> list[dict]:
    """ALL students scoring below the threshold, worst first.

    Returns the complete list; callers truncate for display AND report the
    full count, so a reader is never shown a sample without being told the
    total. Students with no evaluated work are excluded rather than treated
    as scoring zero.
    """
    summary = subject_performance_summary(db, subject_code)
    out = [
        s for s in summary["students"]
        if s["performance_percentage"] is not None
        and s["performance_percentage"] < threshold_percentage
    ]
    out.sort(key=lambda s: s["performance_percentage"])
    return out


# --------------------------------------------------------------------------
# Assignments
# --------------------------------------------------------------------------
def assignment_summary(
    db: Session, subject_code: str, *, today: date | None = None
) -> list[dict]:
    """Per-assignment submission rollup.

    "Overdue" means: nothing submitted AND the due date has passed. A submission
    that simply has not been marked yet is `submitted`, never overdue.
    """
    today = today or date.today()
    assignments = db.scalars(
        select(Assignment)
        .where(Assignment.subject_code == subject_code)
        .order_by(Assignment.due_date)
    ).all()

    out = []
    for a in assignments:
        rows = db.execute(
            select(StudentAssignment.status, StudentAssignment.marks_obtained)
            .where(StudentAssignment.assignment_id == a.assignment_id)
        ).all()
        pending = sum(1 for s, _ in rows if s == "pending")
        submitted = sum(1 for s, _ in rows if s == "submitted")
        evaluated = sum(1 for s, _ in rows if s == "evaluated")
        marks = [m for s, m in rows if s == "evaluated" and m is not None]
        is_past_due = a.due_date < today

        out.append({
            "assignment_id": a.assignment_id,
            "subject_code": a.subject_code,
            "title": a.title,
            "description": a.description,
            "assigned_date": a.assigned_date,
            "due_date": a.due_date,
            "max_marks": a.max_marks,
            "is_past_due": is_past_due,
            "total_students": len(rows),
            "pending_count": pending,
            "submitted_count": submitted,
            "evaluated_count": evaluated,
            # Only a genuine miss counts as overdue.
            "overdue_count": pending if is_past_due else 0,
            "not_yet_due_pending_count": 0 if is_past_due else pending,
            "average_marks": round(sum(marks) / len(marks), 2) if marks else None,
        })
    return out


def student_assignment_status(
    db: Session,
    student_id: str,
    subject_codes: Sequence[str],
    *,
    today: date | None = None,
) -> list[dict]:
    today = today or date.today()
    rows = db.execute(
        select(
            Assignment.assignment_id,
            Assignment.subject_code,
            Assignment.title,
            Assignment.due_date,
            Assignment.max_marks,
            StudentAssignment.status,
            StudentAssignment.submission_date,
            StudentAssignment.marks_obtained,
        )
        .join(StudentAssignment,
              StudentAssignment.assignment_id == Assignment.assignment_id)
        .where(
            StudentAssignment.student_id == student_id,
            Assignment.subject_code.in_(list(subject_codes)),
        )
        .order_by(Assignment.due_date)
    ).all()

    out = []
    for aid, code, title, due, max_marks, status_, sub_date, marks in rows:
        out.append({
            "assignment_id": aid,
            "subject_code": code,
            "title": title,
            "due_date": due,
            "max_marks": max_marks,
            "status": status_,
            "submission_date": sub_date,
            "marks_obtained": marks,
            "is_overdue": status_ == "pending" and due < today,
        })
    return out


def overdue_assignments(
    db: Session, subject_codes: Sequence[str], *, today: date | None = None,
    limit: int = 100,
) -> list[dict]:
    """Students who never submitted work whose due date has passed."""
    today = today or date.today()
    rows = db.execute(
        select(
            Student.student_id,
            Student.full_name,
            Student.roll_number,
            Student.division,
            Assignment.assignment_id,
            Assignment.subject_code,
            Assignment.title,
            Assignment.due_date,
        )
        .join(StudentAssignment,
              StudentAssignment.student_id == Student.student_id)
        .join(Assignment,
              Assignment.assignment_id == StudentAssignment.assignment_id)
        .where(
            Assignment.subject_code.in_(list(subject_codes)),
            StudentAssignment.status == "pending",
            Assignment.due_date < today,
        )
        .order_by(Assignment.due_date, Student.roll_number)
        .limit(limit)
    ).all()

    return [
        {
            "student_id": sid, "full_name": name, "roll_number": roll,
            "division": div, "assignment_id": aid, "subject_code": code,
            "title": title, "due_date": due,
            "days_overdue": (today - due).days,
        }
        for sid, name, roll, div, aid, code, title, due in rows
    ]


# --------------------------------------------------------------------------
# Extracurricular
# --------------------------------------------------------------------------
def extracurricular_summary(
    db: Session, subject_codes: Sequence[str], *, division: str | None = None
) -> dict:
    """Aggregate participation for students in the teacher's authorized scope.

    Returns counts and category rollups only -- no per-student profiles -- so an
    aggregate question never pulls everyone's detailed record into AI context.
    """
    student_q = (
        select(Student.student_id)
        .join(Attendance, Attendance.student_id == Student.student_id)
        .where(Attendance.subject_code.in_(list(subject_codes)))
    )
    if division:
        student_q = student_q.where(Student.division == division)
    student_ids = set(db.scalars(student_q).all())

    if not student_ids:
        return {
            "students_in_scope": 0, "students_with_activities": 0,
            "total_participations": 0, "by_category": {}, "by_role": {},
            "achievement_count": 0, "top_activities": [],
        }

    rows = db.execute(
        select(
            StudentActivity.student_id,
            ExtracurricularActivity.title,
            ExtracurricularActivity.category,
            StudentActivity.role,
            StudentActivity.participation_status,
            StudentActivity.achievement,
        )
        .join(ExtracurricularActivity,
              ExtracurricularActivity.activity_id == StudentActivity.activity_id)
        .where(StudentActivity.student_id.in_(student_ids))
    ).all()

    by_category: dict[str, int] = {}
    by_role: dict[str, int] = {}
    by_activity: dict[str, int] = {}
    participants: set[str] = set()
    achievements = 0

    for sid, title, category, role, _status, achievement in rows:
        participants.add(sid)
        by_category[category] = by_category.get(category, 0) + 1
        by_role[role] = by_role.get(role, 0) + 1
        by_activity[title] = by_activity.get(title, 0) + 1
        if achievement:
            achievements += 1

    top = sorted(by_activity.items(), key=lambda kv: -kv[1])[:10]
    return {
        "students_in_scope": len(student_ids),
        "students_with_activities": len(participants),
        "students_without_activities": len(student_ids) - len(participants),
        "total_participations": len(rows),
        "by_category": dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
        "by_role": dict(sorted(by_role.items(), key=lambda kv: -kv[1])),
        "achievement_count": achievements,
        "top_activities": [{"title": t, "participants": c} for t, c in top],
    }


def student_activities(db: Session, student_id: str) -> list[dict]:
    """One student's activity records. Caller MUST have authorized the student."""
    rows = db.execute(
        select(
            ExtracurricularActivity.activity_id,
            ExtracurricularActivity.title,
            ExtracurricularActivity.category,
            ExtracurricularActivity.description,
            StudentActivity.participation_date,
            StudentActivity.role,
            StudentActivity.participation_status,
            StudentActivity.achievement,
        )
        .join(StudentActivity,
              StudentActivity.activity_id == ExtracurricularActivity.activity_id)
        .where(StudentActivity.student_id == student_id)
        .order_by(StudentActivity.participation_date.desc())
    ).all()

    return [
        {
            "activity_id": aid, "title": title, "category": cat,
            "description": desc, "participation_date": pdate, "role": role,
            "participation_status": pstatus, "achievement": achievement,
        }
        for aid, title, cat, desc, pdate, role, pstatus, achievement in rows
    ]


# --------------------------------------------------------------------------
# Students
# --------------------------------------------------------------------------
def list_students_in_scope(
    db: Session,
    subject_codes: Sequence[str],
    *,
    division: str | None = None,
    subject_code: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> Page:
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    codes = [subject_code] if subject_code else list(subject_codes)

    base = (
        select(Student)
        .join(Attendance, Attendance.student_id == Student.student_id)
        .where(Attendance.subject_code.in_(codes))
        .distinct()
    )
    if division:
        base = base.where(Student.division == division)
    if search:
        pattern = f"%{search.strip()}%"
        base = base.where(
            Student.full_name.ilike(pattern)
            | Student.roll_number.ilike(pattern)
            | Student.student_id.ilike(pattern)
        )

    total = db.scalar(
        select(func.count()).select_from(base.subquery())
    ) or 0

    rows = db.scalars(
        base.order_by(Student.roll_number)
        .offset((max(1, page) - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        {
            "student_id": s.student_id,
            "full_name": s.full_name,
            "roll_number": s.roll_number,
            "division": s.division,
            "academic_year": s.academic_year,
            "semester": s.semester,
            "skills": [x.strip() for x in s.skills.split(";") if x.strip()],
            "interests": [x.strip() for x in s.interests.split(";") if x.strip()],
        }
        for s in rows
    ]
    return Page(items, total, max(1, page), page_size)


def student_academic_summary(
    db: Session, student_id: str, subject_codes: Sequence[str], threshold: float
) -> dict:
    """Combined attendance + marks + assignments for one authorized student."""
    student = db.get(Student, student_id)
    if student is None:
        return {}

    attendance_rows = student_attendance(db, student_id, subject_codes, threshold)
    assignments = student_assignment_status(db, student_id, subject_codes)

    marks_rows = db.execute(
        select(
            Assessment.subject_code,
            Assessment.title,
            Assessment.assessment_type,
            Assessment.max_marks,
            Grade.marks_obtained,
            Grade.is_absent,
        )
        .join(Grade, Grade.assessment_id == Assessment.assessment_id)
        .where(
            Grade.student_id == student_id,
            Assessment.subject_code.in_(list(subject_codes)),
        )
        .order_by(Assessment.subject_code)
    ).all()

    assessments = [
        {
            "subject_code": code, "title": title, "assessment_type": atype,
            "max_marks": max_marks, "marks_obtained": marks,
            "is_absent": absent,
            "percentage": (
                round(marks / max_marks * 100, 2) if marks is not None else None
            ),
            "evaluation_state": (
                "evaluated" if marks is not None
                else "absent" if absent else "not yet evaluated"
            ),
        }
        for code, title, atype, max_marks, marks, absent in marks_rows
    ]

    evaluated = [a["percentage"] for a in assessments if a["percentage"] is not None]
    overdue = sum(1 for a in assignments if a["is_overdue"])

    return {
        "student_id": student.student_id,
        "full_name": student.full_name,
        "roll_number": student.roll_number,
        "division": student.division,
        "department": student.department,
        "academic_year": student.academic_year,
        "semester": student.semester,
        "skills": [x.strip() for x in student.skills.split(";") if x.strip()],
        "interests": [x.strip() for x in student.interests.split(";") if x.strip()],
        "attendance": attendance_rows,
        "subjects_below_attendance_threshold": sum(
            1 for a in attendance_rows if a["below_threshold"]
        ),
        "assessments": assessments,
        "average_assessment_percentage": (
            round(sum(evaluated) / len(evaluated), 2) if evaluated else None
        ),
        "assessments_not_evaluated": sum(
            1 for a in assessments if a["evaluation_state"] == "not yet evaluated"
        ),
        "assignments": assignments,
        "overdue_assignment_count": overdue,
        "threshold": threshold,
    }


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
def teacher_dashboard(
    db: Session, teacher_id: str, subject_codes: Sequence[str], threshold: float,
    *, today: date | None = None,
) -> dict:
    """Everything the faculty dashboard shows, computed from the database."""
    today = today or date.today()
    codes = list(subject_codes)

    if not codes:
        return {
            "subject_count": 0, "student_count": 0, "threshold": threshold,
            "subject_attendance": [], "students_below_threshold": 0,
            "overdue_assignment_count": 0, "upcoming_deadlines": [],
            "recent_activities": [], "overall_class_attendance_percentage": None,
            "pending_evaluation_count": 0,
        }

    student_ids = set(db.scalars(
        select(Attendance.student_id).where(Attendance.subject_code.in_(codes))
    ).all())

    subject_attendance_list = [
        subject_attendance_summary(db, code, threshold) for code in sorted(codes)
    ]

    all_pairs = db.execute(
        select(Attendance.classes_attended, Attendance.classes_conducted)
        .where(Attendance.subject_code.in_(codes))
    ).all()
    all_pairs = [(a, c) for a, c in all_pairs]

    below_count = sum(
        1 for a, c in all_pairs if is_below_threshold(a, c, threshold)
    )

    overdue_total = db.scalar(
        select(func.count())
        .select_from(StudentAssignment)
        .join(Assignment, Assignment.assignment_id == StudentAssignment.assignment_id)
        .where(
            Assignment.subject_code.in_(codes),
            StudentAssignment.status == "pending",
            Assignment.due_date < today,
        )
    ) or 0

    upcoming = db.execute(
        select(Assignment.assignment_id, Assignment.subject_code,
               Assignment.title, Assignment.due_date)
        .where(Assignment.subject_code.in_(codes), Assignment.due_date >= today)
        .order_by(Assignment.due_date)
        .limit(5)
    ).all()

    pending_eval = db.scalar(
        select(func.count())
        .select_from(Grade)
        .join(Assessment, Assessment.assessment_id == Grade.assessment_id)
        .where(
            Assessment.subject_code.in_(codes),
            Grade.marks_obtained.is_(None),
            Grade.is_absent.is_(False),
        )
    ) or 0

    recent = db.execute(
        select(ExtracurricularActivity.title, ExtracurricularActivity.category,
               StudentActivity.participation_date, Student.full_name,
               StudentActivity.achievement)
        .join(StudentActivity,
              StudentActivity.activity_id == ExtracurricularActivity.activity_id)
        .join(Student, Student.student_id == StudentActivity.student_id)
        .where(StudentActivity.student_id.in_(student_ids))
        .order_by(StudentActivity.participation_date.desc())
        .limit(6)
    ).all()

    return {
        "subject_count": len(codes),
        "student_count": len(student_ids),
        "threshold": threshold,
        "subject_attendance": subject_attendance_list,
        "overall_class_attendance_percentage": aggregate_percentage(all_pairs),
        "overall_mean_student_attendance_percentage": mean_student_percentage(all_pairs),
        "students_below_threshold": below_count,
        "attendance_record_count": len(all_pairs),
        "overdue_assignment_count": overdue_total,
        "pending_evaluation_count": pending_eval,
        "upcoming_deadlines": [
            {"assignment_id": aid, "subject_code": code, "title": title,
             "due_date": due, "days_until_due": (due - today).days}
            for aid, code, title, due in upcoming
        ],
        "recent_activities": [
            {"title": t, "category": c, "participation_date": d,
             "student_name": n, "achievement": a}
            for t, c, d, n, a in recent
        ],
        "calculation_notes": {
            "overall_class_attendance_percentage":
                "Pooled: sum(classes_attended) / sum(classes_conducted) across all "
                "authorized subjects. Every class counts equally.",
            "overall_mean_student_attendance_percentage":
                "Unweighted mean of each student-subject percentage. Every "
                "student-subject record counts equally.",
            "students_below_threshold":
                "Count of student-subject records below the threshold, not "
                "distinct students.",
        },
    }
