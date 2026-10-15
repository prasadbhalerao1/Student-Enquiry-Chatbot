"""Pydantic v2 request/response models for the public API."""
from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# A subject code like CB3203T-A or HSO3203T-F. Anything else is rejected before
# it reaches the database layer.
SubjectCode = Annotated[str, Field(pattern=r"^[A-Z]{2,4}\d{4}[A-Z](?:-[A-Z])?$", max_length=16)]
StudentId = Annotated[str, Field(pattern=r"^STU\d{4}$")]
TeacherId = Annotated[str, Field(pattern=r"^TCH\d{3}$")]
Division = Annotated[str, Field(pattern=r"^[A-C]$")]


class Health(BaseModel):
    status: Literal["ok"]
    database: Literal["connected", "unavailable"]
    synthetic_data_notice: str


# --------------------------------------------------------------------------
# Session
# --------------------------------------------------------------------------
class DemoSessionRequest(BaseModel):
    teacher_id: TeacherId


class DemoTeacherOption(BaseModel):
    teacher_id: str
    full_name: str
    designation: str
    department: str
    is_department_coordinator: bool
    subject_codes: list[str]


class TeacherProfile(BaseModel):
    teacher_id: str
    full_name: str
    email: str
    department: str
    designation: str
    is_department_coordinator: bool
    subject_codes: list[str]
    attendance_threshold: float
    threshold_note: str
    demo_mode: bool = True


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subject_code: str
    subject_name: str
    subject_type: str
    credits: int
    faculty_name: str | None = None
    enrolled_students: int
    class_attendance_percentage: float | None
    mean_student_attendance_percentage: float | None


# --------------------------------------------------------------------------
# Attendance
# --------------------------------------------------------------------------
class AttendanceRow(BaseModel):
    student_id: str
    full_name: str
    roll_number: str
    division: str
    classes_attended: int
    classes_conducted: int
    attendance_percentage: float
    below_threshold: bool
    status: str


class PaginatedAttendance(BaseModel):
    items: list[AttendanceRow]
    total: int
    page: int
    page_size: int
    total_pages: int
    threshold: float


class SubjectAnalytics(BaseModel):
    subject_code: str
    subject_name: str | None
    subject_type: str | None
    enrolled_students: int
    classes_conducted: int
    threshold: float
    class_attendance_percentage: float | None
    mean_student_attendance_percentage: float | None
    students_below_threshold: int
    students_meeting_threshold: int
    lowest_percentage: float | None
    highest_percentage: float | None


# --------------------------------------------------------------------------
# Academic / assignments / activities
# --------------------------------------------------------------------------
class AssessmentOut(BaseModel):
    assessment_id: str
    subject_code: str
    title: str
    assessment_type: str
    max_marks: int
    assessment_date: date
    weightage: float
    total_students: int
    evaluated_count: int
    pending_evaluation_count: int
    absent_count: int
    average_marks: float | None
    average_percentage: float | None


class AssignmentOut(BaseModel):
    assignment_id: str
    subject_code: str
    title: str
    description: str
    assigned_date: date
    due_date: date
    max_marks: int
    is_past_due: bool
    total_students: int
    pending_count: int
    submitted_count: int
    evaluated_count: int
    overdue_count: int
    not_yet_due_pending_count: int
    average_marks: float | None


class StudentOut(BaseModel):
    student_id: str
    full_name: str
    roll_number: str
    division: str
    academic_year: int
    semester: int
    skills: list[str]
    interests: list[str]


class PaginatedStudents(BaseModel):
    items: list[StudentOut]
    total: int
    page: int
    page_size: int
    total_pages: int


# --------------------------------------------------------------------------
# Chat / providers
# --------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Annotated[str, Field(min_length=1, max_length=8000)]


class ProviderSettings(BaseModel):
    """BYOK configuration. Received per request, never stored."""

    provider: Annotated[str, Field(min_length=1, max_length=40)]
    model: Annotated[str, Field(min_length=1, max_length=120)]
    api_key: Annotated[str | None, Field(default=None, max_length=400)] = None
    base_url: Annotated[str | None, Field(default=None, max_length=400)] = None
    temperature: Annotated[float, Field(default=0.1, ge=0.0, le=2.0)] = 0.1

    @field_validator("api_key", "base_url")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return (v or "").strip() or None


class ChatRequest(BaseModel):
    messages: Annotated[list[ChatMessage], Field(min_length=1, max_length=40)]
    provider: ProviderSettings


class ProviderTestRequest(BaseModel):
    provider: ProviderSettings


class ProviderTestResponse(BaseModel):
    ok: bool
    message: str
    model: str | None = None
    provider: str | None = None
    supports_tool_calling: bool | None = None
    sample: str | None = None


class ErrorResponse(BaseModel):
    detail: str


GenericDict = dict[str, Any]
