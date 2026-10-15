"""Load data/synthetic/*.csv into PostgreSQL.

Idempotent: existing rows are cleared first, so re-running always leaves the
database matching the CSVs exactly.

    python scripts/seed_database.py
"""
from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
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

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"

# Child tables first so foreign keys never block a delete.
DELETE_ORDER = [
    StudentActivity, ExtracurricularActivity,
    StudentAssignment, Assignment,
    Grade, Assessment,
    Attendance, TeacherSubject,
    Student, Subject, Teacher,
]


def _rows(filename: str) -> list[dict[str, str]]:
    path = DATA_DIR / filename
    if not path.exists():
        raise SystemExit(
            f"Missing {path}.\nRun: python scripts/generate_dataset.py"
        )
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def _date_or_none(value: str) -> date | None:
    value = value.strip()
    return date.fromisoformat(value) if value else None


def _float_or_none(value: str) -> float | None:
    value = value.strip()
    return float(value) if value else None


def seed(db: Session) -> None:
    print("Clearing existing rows...")
    for model in DELETE_ORDER:
        db.execute(delete(model))
    db.flush()

    print("Loading CSVs...")

    db.add_all([
        Teacher(
            teacher_id=r["teacher_id"],
            full_name=r["full_name"],
            department=r["department"],
            designation=r["designation"],
            email=r["email"],
            is_department_coordinator=_bool(r["is_department_coordinator"]),
        )
        for r in _rows("teachers.csv")
    ])

    db.add_all([
        Subject(
            subject_code=r["subject_code"],
            subject_name=r["subject_name"],
            subject_type=r["subject_type"],
            credits=int(r["credits"]),
        )
        for r in _rows("subjects.csv")
    ])
    db.flush()

    db.add_all([
        TeacherSubject(teacher_id=r["teacher_id"], subject_code=r["subject_code"])
        for r in _rows("teacher_subjects.csv")
    ])

    db.add_all([
        Student(
            student_id=r["student_id"],
            full_name=r["full_name"],
            roll_number=r["roll_number"],
            department=r["department"],
            academic_year=int(r["academic_year"]),
            semester=int(r["semester"]),
            division=r["division"],
            email=r["email"],
            skills=r["skills"],
            interests=r["interests"],
        )
        for r in _rows("students.csv")
    ])
    db.flush()

    db.add_all([
        Attendance(
            student_id=r["student_id"],
            subject_code=r["subject_code"],
            classes_conducted=int(r["classes_conducted"]),
            classes_attended=int(r["classes_attended"]),
        )
        for r in _rows("attendance.csv")
    ])

    db.add_all([
        Assessment(
            assessment_id=r["assessment_id"],
            subject_code=r["subject_code"],
            title=r["title"],
            assessment_type=r["assessment_type"],
            max_marks=int(r["max_marks"]),
            assessment_date=date.fromisoformat(r["assessment_date"]),
            weightage=float(r["weightage"]),
        )
        for r in _rows("assessments.csv")
    ])
    db.flush()

    db.add_all([
        Grade(
            assessment_id=r["assessment_id"],
            student_id=r["student_id"],
            marks_obtained=_float_or_none(r["marks_obtained"]),
            is_absent=_bool(r["is_absent"]),
        )
        for r in _rows("grades.csv")
    ])

    db.add_all([
        Assignment(
            assignment_id=r["assignment_id"],
            subject_code=r["subject_code"],
            title=r["title"],
            description=r["description"],
            assigned_date=date.fromisoformat(r["assigned_date"]),
            due_date=date.fromisoformat(r["due_date"]),
            max_marks=int(r["max_marks"]),
        )
        for r in _rows("assignments.csv")
    ])
    db.flush()

    db.add_all([
        StudentAssignment(
            assignment_id=r["assignment_id"],
            student_id=r["student_id"],
            status=r["status"],
            submission_date=_date_or_none(r["submission_date"]),
            marks_obtained=_float_or_none(r["marks_obtained"]),
        )
        for r in _rows("student_assignments.csv")
    ])

    db.add_all([
        ExtracurricularActivity(
            activity_id=r["activity_id"],
            title=r["title"],
            category=r["category"],
            description=r["description"],
        )
        for r in _rows("extracurricular_activities.csv")
    ])
    db.flush()

    db.add_all([
        StudentActivity(
            activity_id=r["activity_id"],
            student_id=r["student_id"],
            participation_date=date.fromisoformat(r["participation_date"]),
            role=r["role"],
            participation_status=r["participation_status"],
            achievement=r["achievement"].strip() or None,
        )
        for r in _rows("student_activities.csv")
    ])

    db.commit()


def verify(db: Session) -> None:
    print("\nRow counts in PostgreSQL:")
    for model in reversed(DELETE_ORDER):
        count = db.scalar(select(func.count()).select_from(model))
        print(f"  {model.__tablename__:<32} {count:>6}")

    subjects = db.scalar(select(func.count()).select_from(Subject))
    if subjects != 12:
        raise SystemExit(f"Expected exactly 12 subjects, found {subjects}")

    bad = db.scalar(
        select(func.count())
        .select_from(Attendance)
        .where(
            (Attendance.classes_attended > Attendance.classes_conducted)
            | (Attendance.classes_conducted <= 0)
            | (Attendance.classes_attended < 0)
        )
    )
    if bad:
        raise SystemExit(f"Found {bad} invalid attendance rows")

    print("\nIntegrity checks passed. All records are synthetic demo data.")


def main() -> None:
    print(f"Seeding {engine.url.render_as_string(hide_password=True)}")
    with SessionLocal() as db:
        seed(db)
        verify(db)


if __name__ == "__main__":
    main()
