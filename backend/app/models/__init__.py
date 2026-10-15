"""SQLAlchemy ORM models.

All records in this schema are SYNTHETIC demonstration data.
"""
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Teacher(Base):
    __tablename__ = "teachers"

    teacher_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    department: Mapped[str] = mapped_column(String(64), nullable=False)
    designation: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    is_department_coordinator: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    subjects: Mapped[list["TeacherSubject"]] = relationship(back_populates="teacher")


class Subject(Base):
    __tablename__ = "subjects"

    subject_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    subject_name: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False)  # Theory|Lab
    credits: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    __table_args__ = (
        CheckConstraint("subject_type in ('Theory','Lab')", name="ck_subject_type"),
    )


class TeacherSubject(Base):
    """Authoritative teacher -> subject assignment used for authorization."""

    __tablename__ = "teacher_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    teacher_id: Mapped[str] = mapped_column(
        ForeignKey("teachers.teacher_id", ondelete="CASCADE"), nullable=False
    )
    subject_code: Mapped[str] = mapped_column(
        ForeignKey("subjects.subject_code", ondelete="CASCADE"), nullable=False
    )

    teacher: Mapped[Teacher] = relationship(back_populates="subjects")
    subject: Mapped[Subject] = relationship()

    __table_args__ = (
        UniqueConstraint("teacher_id", "subject_code", name="uq_teacher_subject"),
    )


class Student(Base):
    __tablename__ = "students"

    student_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    roll_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    department: Mapped[str] = mapped_column(String(64), nullable=False)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    division: Mapped[str] = mapped_column(String(4), nullable=False)
    email: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    skills: Mapped[str] = mapped_column(Text, nullable=False, default="")
    interests: Mapped[str] = mapped_column(Text, nullable=False, default="")


class Attendance(Base):
    """One summary row per enrolled student-subject pair."""

    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False
    )
    subject_code: Mapped[str] = mapped_column(
        ForeignKey("subjects.subject_code", ondelete="CASCADE"), nullable=False
    )
    classes_conducted: Mapped[int] = mapped_column(Integer, nullable=False)
    classes_attended: Mapped[int] = mapped_column(Integer, nullable=False)

    student: Mapped[Student] = relationship()
    subject: Mapped[Subject] = relationship()

    __table_args__ = (
        UniqueConstraint("student_id", "subject_code", name="uq_attendance_pair"),
        CheckConstraint("classes_conducted > 0", name="ck_conducted_positive"),
        CheckConstraint(
            "classes_attended >= 0 and classes_attended <= classes_conducted",
            name="ck_attended_range",
        ),
    )


class Assessment(Base):
    __tablename__ = "assessments"

    assessment_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    subject_code: Mapped[str] = mapped_column(
        ForeignKey("subjects.subject_code", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    assessment_date: Mapped[date] = mapped_column(Date, nullable=False)
    weightage: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    subject: Mapped[Subject] = relationship()

    __table_args__ = (CheckConstraint("max_marks > 0", name="ck_max_marks_positive"),)


class Grade(Base):
    """A student's result for one assessment.

    ``marks_obtained IS NULL`` means NOT EVALUATED / missing, which is a
    different thing from a recorded score of 0.
    """

    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_id: Mapped[str] = mapped_column(
        ForeignKey("assessments.assessment_id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False
    )
    marks_obtained: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_absent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    assessment: Mapped[Assessment] = relationship()
    student: Mapped[Student] = relationship()

    __table_args__ = (
        UniqueConstraint("assessment_id", "student_id", name="uq_grade_pair"),
        CheckConstraint(
            "marks_obtained is null or marks_obtained >= 0", name="ck_marks_nonneg"
        ),
    )


class Assignment(Base):
    __tablename__ = "assignments"

    assignment_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    subject_code: Mapped[str] = mapped_column(
        ForeignKey("subjects.subject_code", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    assigned_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False)

    subject: Mapped[Subject] = relationship()


class StudentAssignment(Base):
    """Per-student submission state.

    status: submitted | evaluated | pending
      - pending   -> nothing handed in yet (overdue is derived from due_date)
      - submitted -> handed in, not yet marked (marks_obtained IS NULL)
      - evaluated -> handed in and marked
    """

    __tablename__ = "student_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("assignments.assignment_id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    submission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    marks_obtained: Mapped[float | None] = mapped_column(Float, nullable=True)

    assignment: Mapped[Assignment] = relationship()
    student: Mapped[Student] = relationship()

    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_student_assignment"),
        CheckConstraint(
            "status in ('pending','submitted','evaluated')", name="ck_sa_status"
        ),
    )


class ExtracurricularActivity(Base):
    __tablename__ = "extracurricular_activities"

    activity_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")


class StudentActivity(Base):
    __tablename__ = "student_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[str] = mapped_column(
        ForeignKey("extracurricular_activities.activity_id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False
    )
    participation_date: Mapped[date] = mapped_column(Date, nullable=False)
    role: Mapped[str] = mapped_column(String(48), nullable=False)
    participation_status: Mapped[str] = mapped_column(String(24), nullable=False)
    achievement: Mapped[str | None] = mapped_column(String(160), nullable=True)

    activity: Mapped[ExtracurricularActivity] = relationship()
    student: Mapped[Student] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "activity_id", "student_id", "participation_date", name="uq_student_activity"
        ),
    )
