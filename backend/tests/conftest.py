"""Shared fixtures.

Tests run against a throwaway SQLite database built from the same SQLAlchemy
metadata as production, so no live PostgreSQL is required to run the suite.
The authorization logic under test is database-agnostic.
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.main import app
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

TODAY = date(2026, 4, 15)


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite ignores foreign keys unless asked.
    @event.listens_for(engine, "connect")
    def _fk_on(conn, _rec):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = maker()
    _seed_fixture_data(db)
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _seed_fixture_data(db: Session) -> None:
    """A miniature department: two teachers, four subjects, four students."""
    db.add_all([
        Teacher(teacher_id="TCH001", full_name="Alpha Teacher",
                department="CSBS", designation="Professor",
                email="alpha@csbs-demo.invalid", is_department_coordinator=True),
        Teacher(teacher_id="TCH002", full_name="Beta Teacher",
                department="CSBS", designation="Assistant Professor",
                email="beta@csbs-demo.invalid", is_department_coordinator=False),
    ])
    db.add_all([
        Subject(subject_code="CB3202T", subject_name="Machine Learning",
                subject_type="Theory", credits=3),
        Subject(subject_code="CB3202L", subject_name="Machine Learning Laboratory",
                subject_type="Lab", credits=1),
        Subject(subject_code="CB3201T", subject_name="Computer Networks",
                subject_type="Theory", credits=3),
        Subject(subject_code="CB3203T-A", subject_name="Artificial Intelligence",
                subject_type="Theory", credits=3),
    ])
    db.flush()

    # Alpha teaches ML (theory + lab). Beta teaches Computer Networks.
    # Nobody teaches CB3203T-A, so it is out of scope for both.
    db.add_all([
        TeacherSubject(teacher_id="TCH001", subject_code="CB3202T"),
        TeacherSubject(teacher_id="TCH001", subject_code="CB3202L"),
        TeacherSubject(teacher_id="TCH002", subject_code="CB3201T"),
    ])

    for i in range(1, 5):
        db.add(Student(
            student_id=f"STU{i:04d}", full_name=f"Student {i}",
            roll_number=f"CSBS3A{i:03d}", department="CSBS",
            academic_year=3, semester=6, division="ABC"[(i - 1) % 3],
            email=f"stu{i:04d}@csbs-demo.invalid",
            skills="Python; SQL", interests="Machine Learning",
        ))
    db.flush()

    # STU0001-3 take ML; STU0004 takes only Computer Networks (Beta's subject).
    attendance = [
        ("STU0001", "CB3202T", 40, 38),   # 95%
        ("STU0002", "CB3202T", 40, 30),   # exactly 75%
        ("STU0003", "CB3202T", 40, 25),   # 62.5%, below
        ("STU0001", "CB3202L", 24, 20),
        ("STU0002", "CB3202L", 24, 12),   # 50%, below
        ("STU0003", "CB3202L", 24, 23),
        ("STU0004", "CB3201T", 40, 20),   # 50%, Beta's student only
    ]
    for sid, code, conducted, attended in attendance:
        db.add(Attendance(student_id=sid, subject_code=code,
                          classes_conducted=conducted, classes_attended=attended))

    db.add_all([
        Assessment(assessment_id="ASM0001", subject_code="CB3202T",
                   title="Internal Examination I", assessment_type="Internal Exam",
                   max_marks=30, assessment_date=date(2026, 2, 10), weightage=0.5),
        Assessment(assessment_id="ASM0002", subject_code="CB3202T",
                   title="Unit Quiz", assessment_type="Quiz",
                   max_marks=10, assessment_date=date(2026, 3, 10), weightage=0.5),
    ])
    db.flush()

    db.add_all([
        # STU0001: strong, fully evaluated.
        Grade(assessment_id="ASM0001", student_id="STU0001", marks_obtained=27.0),
        Grade(assessment_id="ASM0002", student_id="STU0001", marks_obtained=9.0),
        # STU0002: a recorded ZERO -- distinct from a missing mark.
        Grade(assessment_id="ASM0001", student_id="STU0002", marks_obtained=0.0),
        # ...and one genuinely not evaluated yet.
        Grade(assessment_id="ASM0002", student_id="STU0002", marks_obtained=None),
        # STU0003: absent for one, evaluated on the other.
        Grade(assessment_id="ASM0001", student_id="STU0003",
              marks_obtained=None, is_absent=True),
        Grade(assessment_id="ASM0002", student_id="STU0003", marks_obtained=5.0),
    ])

    db.add_all([
        # Closed assignment: due date in the past.
        Assignment(assignment_id="ASG0001", subject_code="CB3202T",
                   title="Problem Set 1", description="Unit 1 problems.",
                   assigned_date=date(2026, 2, 1), due_date=date(2026, 2, 20),
                   max_marks=20),
        # Open assignment: due date still ahead of TODAY.
        Assignment(assignment_id="ASG0002", subject_code="CB3202T",
                   title="Problem Set 2", description="Unit 2 problems.",
                   assigned_date=date(2026, 4, 1), due_date=date(2026, 5, 1),
                   max_marks=20),
    ])
    db.flush()

    db.add_all([
        # Genuinely overdue: nothing submitted, due date passed.
        StudentAssignment(assignment_id="ASG0001", student_id="STU0001",
                          status="pending"),
        # Submitted but unmarked -- must NOT count as overdue.
        StudentAssignment(assignment_id="ASG0001", student_id="STU0002",
                          status="submitted", submission_date=date(2026, 2, 15)),
        StudentAssignment(assignment_id="ASG0001", student_id="STU0003",
                          status="evaluated", submission_date=date(2026, 2, 12),
                          marks_obtained=16.0),
        # Not yet due -- pending here is not overdue either.
        StudentAssignment(assignment_id="ASG0002", student_id="STU0001",
                          status="pending"),
    ])

    db.add(ExtracurricularActivity(
        activity_id="ACT001", title="CSBS Coding Club",
        category="Technical Club", description="Weekly sessions.",
    ))
    db.flush()
    db.add_all([
        StudentActivity(activity_id="ACT001", student_id="STU0001",
                        participation_date=date(2025, 9, 1), role="Team Lead",
                        participation_status="Completed", achievement="First Place"),
        StudentActivity(activity_id="ACT001", student_id="STU0004",
                        participation_date=date(2025, 9, 2), role="Participant",
                        participation_status="Completed", achievement=None),
    ])
    db.commit()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def alpha(client):
    """Signed-in client for TCH001 (teaches CB3202T + CB3202L, coordinator)."""
    r = client.post("/api/demo-session", json={"teacher_id": "TCH001"})
    assert r.status_code == 200
    return client


@pytest.fixture
def beta(db_session):
    """A separate client signed in as TCH002 (teaches CB3201T only)."""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        r = c.post("/api/demo-session", json={"teacher_id": "TCH002"})
        assert r.status_code == 200
        yield c
    app.dependency_overrides.clear()
