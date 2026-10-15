"""Dataset integrity tests, run directly against the generated CSVs."""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_dataset.py"

EXPECTED_SUBJECT_CODES = {
    "ARM3201L", "ARM3201T", "CB3201L", "CB3201T", "CB3202L", "CB3202T",
    "CB3203L-A", "CB3203T-A", "CB3204L", "CB3205L", "CB3206L", "HSO3203T-F",
}


def rows(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    if not path.exists():
        pytest.skip(f"{name} not generated; run scripts/generate_dataset.py")
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def students():
    return rows("students.csv")


@pytest.fixture(scope="module")
def subjects():
    return rows("subjects.csv")


@pytest.fixture(scope="module")
def attendance():
    return rows("attendance.csv")


class TestSubjects:
    def test_exactly_twelve(self, subjects):
        assert len(subjects) == 12

    def test_codes_match_the_catalogue_verbatim(self, subjects):
        assert {s["subject_code"] for s in subjects} == EXPECTED_SUBJECT_CODES

    def test_codes_are_unique(self, subjects):
        codes = [s["subject_code"] for s in subjects]
        assert len(codes) == len(set(codes))

    def test_hso_stored_once(self, subjects):
        assert sum(1 for s in subjects if s["subject_code"] == "HSO3203T-F") == 1

    def test_types_are_valid(self, subjects):
        assert {s["subject_type"] for s in subjects} <= {"Theory", "Lab"}


class TestTeachers:
    def test_one_account_per_distinct_faculty_name(self):
        teachers = rows("teachers.csv")
        names = [t["full_name"] for t in teachers]
        assert len(names) == len(set(names))
        # Eight distinct faculty names appear in the supplied catalogue.
        assert len(teachers) == 8

    def test_faculty_spelling_preserved(self):
        names = {t["full_name"] for t in rows("teachers.csv")}
        for expected in [
            "SUJIN ACHANKUNJU PANIKKASSERI",
            "Aarrjun Shrikrishna Umrikar",
            "MAHESH KANTHALE",
            "NEERAJ SATHAWANE",
            "SUMEDHA RAUT",
            "RUTUJA S BACCHAV",
            "Kavita Manojkumar Patil",
            "SUHASINI BHAT",
        ]:
            assert expected in names

    def test_assignments_reference_valid_rows(self, subjects):
        teacher_ids = {t["teacher_id"] for t in rows("teachers.csv")}
        codes = {s["subject_code"] for s in subjects}
        links = rows("teacher_subjects.csv")
        assert len(links) == 12
        for link in links:
            assert link["teacher_id"] in teacher_ids
            assert link["subject_code"] in codes

    def test_every_subject_has_exactly_one_teacher(self):
        links = rows("teacher_subjects.csv")
        seen = [link["subject_code"] for link in links]
        assert len(seen) == len(set(seen))

    def test_exactly_one_coordinator(self):
        coords = [
            t for t in rows("teachers.csv")
            if t["is_department_coordinator"] == "true"
        ]
        assert len(coords) == 1


class TestStudents:
    def test_count(self, students):
        assert len(students) == 250

    def test_ids_and_rolls_unique(self, students):
        assert len({s["student_id"] for s in students}) == 250
        assert len({s["roll_number"] for s in students}) == 250

    def test_emails_use_a_reserved_domain(self, students):
        # .invalid is reserved by RFC 2606 and can never resolve.
        assert all(s["email"].endswith(".invalid") for s in students)

    def test_divisions_populated(self, students):
        assert {s["division"] for s in students} == {"A", "B", "C"}

    def test_all_third_year(self, students):
        assert all(s["academic_year"] == "3" for s in students)


class TestAttendance:
    def test_one_row_per_student_subject_pair(self, attendance, students, subjects):
        assert len(attendance) == len(students) * len(subjects)
        pairs = {(a["student_id"], a["subject_code"]) for a in attendance}
        assert len(pairs) == len(attendance)

    def test_counts_are_valid(self, attendance):
        for a in attendance:
            conducted = int(a["classes_conducted"])
            attended = int(a["classes_attended"])
            assert conducted > 0
            assert 0 <= attended <= conducted

    def test_references_are_valid(self, attendance, students, subjects):
        sids = {s["student_id"] for s in students}
        codes = {s["subject_code"] for s in subjects}
        for a in attendance:
            assert a["student_id"] in sids
            assert a["subject_code"] in codes

    def test_spans_all_analytic_bands(self, attendance):
        pct = [
            int(a["classes_attended"]) / int(a["classes_conducted"]) * 100
            for a in attendance
        ]
        assert any(p < 50 for p in pct), "need severe low-attendance cases"
        assert any(50 <= p < 75 for p in pct), "need below-threshold cases"
        assert any(75 <= p < 85 for p in pct), "need borderline cases"
        assert any(p >= 85 for p in pct), "need excellent cases"

    def test_conducted_varies_between_subjects(self, attendance):
        by_subject = {a["subject_code"]: a["classes_conducted"] for a in attendance}
        assert len(set(by_subject.values())) > 1


class TestAcademics:
    def test_grades_reference_valid_assessments(self):
        asm_ids = {a["assessment_id"] for a in rows("assessments.csv")}
        for g in rows("grades.csv"):
            assert g["assessment_id"] in asm_ids

    def test_marks_within_range(self):
        max_by_id = {
            a["assessment_id"]: float(a["max_marks"]) for a in rows("assessments.csv")
        }
        for g in rows("grades.csv"):
            if g["marks_obtained"] == "":
                continue
            assert 0 <= float(g["marks_obtained"]) <= max_by_id[g["assessment_id"]]

    def test_missing_marks_are_blank_not_zero(self):
        grades = rows("grades.csv")
        blanks = [g for g in grades if g["marks_obtained"] == ""]
        zeros = [g for g in grades if g["marks_obtained"] == "0.0"]
        assert blanks, "dataset must contain unevaluated results"
        # Blank and zero are represented differently.
        assert all(g["marks_obtained"] != "0" for g in blanks)
        assert len(blanks) != len(zeros)

    def test_all_three_evaluation_states_exist(self):
        """A blank mark, an absence and a real zero must all be present.

        These are three different things, and the dataset has to contain each
        so the distinction is exercised against real data and not only in test
        fixtures.
        """
        grades = rows("grades.csv")
        unevaluated = [
            g for g in grades
            if g["marks_obtained"] == "" and g["is_absent"] == "false"
        ]
        absent = [g for g in grades if g["is_absent"] == "true"]
        real_zeros = [g for g in grades if g["marks_obtained"] in ("0.0", "0")]

        assert unevaluated, "need results with no mark recorded"
        assert absent, "need absences"
        assert real_zeros, "need students who attempted and scored zero"

    def test_absent_is_distinct_from_unevaluated(self):
        grades = rows("grades.csv")
        absent = [g for g in grades if g["is_absent"] == "true"]
        unevaluated = [
            g for g in grades
            if g["marks_obtained"] == "" and g["is_absent"] == "false"
        ]
        assert absent and unevaluated

    def test_performance_is_not_uniform(self):
        marks = [
            float(g["marks_obtained"]) for g in rows("grades.csv")
            if g["marks_obtained"] != ""
        ]
        assert len(set(marks)) > 50, "scores must vary across students"


class TestAssignments:
    def test_statuses_are_valid(self):
        statuses = {r["status"] for r in rows("student_assignments.csv")}
        assert statuses <= {"pending", "submitted", "evaluated"}
        assert statuses == {"pending", "submitted", "evaluated"}

    def test_pending_has_no_submission_date(self):
        for r in rows("student_assignments.csv"):
            if r["status"] == "pending":
                assert r["submission_date"] == ""
                assert r["marks_obtained"] == ""

    def test_submitted_has_date_but_no_marks(self):
        """A submission awaiting marking is not the same as a missing one."""
        for r in rows("student_assignments.csv"):
            if r["status"] == "submitted":
                assert r["submission_date"] != ""
                assert r["marks_obtained"] == ""

    def test_evaluated_has_both(self):
        for r in rows("student_assignments.csv"):
            if r["status"] == "evaluated":
                assert r["submission_date"] != ""
                assert r["marks_obtained"] != ""

    def test_submission_never_after_due_date(self):
        due = {a["assignment_id"]: a["due_date"] for a in rows("assignments.csv")}
        for r in rows("student_assignments.csv"):
            if r["submission_date"]:
                assert r["submission_date"] <= due[r["assignment_id"]]

    def test_marks_within_range(self):
        max_by_id = {
            a["assignment_id"]: float(a["max_marks"]) for a in rows("assignments.csv")
        }
        for r in rows("student_assignments.csv"):
            if r["marks_obtained"]:
                assert 0 <= float(r["marks_obtained"]) <= max_by_id[r["assignment_id"]]

    def test_due_after_assigned(self):
        for a in rows("assignments.csv"):
            assert a["due_date"] > a["assigned_date"]


class TestExtracurricular:
    def test_activity_count_in_range(self):
        activities = rows("extracurricular_activities.csv")
        assert 15 <= len(activities) <= 25

    def test_categories_cover_the_required_spread(self):
        cats = {a["category"] for a in rows("extracurricular_activities.csv")}
        for required in [
            "Technical Club", "Hackathon", "Coding Competition", "Workshop",
            "Seminar", "Sports", "Volunteering", "Cultural",
            "Project Exhibition", "Student Leadership",
        ]:
            assert required in cats

    def test_participation_is_varied(self, students):
        participations = rows("student_activities.csv")
        with_activity = {p["student_id"] for p in participations}
        assert len(with_activity) < len(students), "some students must have none"
        assert len(with_activity) > 100, "many students must participate"

    def test_awards_are_the_exception(self):
        participations = rows("student_activities.csv")
        awarded = [p for p in participations if p["achievement"]]
        assert awarded, "some achievements must exist"
        assert len(awarded) < len(participations) * 0.4, "not everyone wins an award"

    def test_references_valid(self, students):
        sids = {s["student_id"] for s in students}
        aids = {a["activity_id"] for a in rows("extracurricular_activities.csv")}
        for p in rows("student_activities.csv"):
            assert p["student_id"] in sids
            assert p["activity_id"] in aids


class TestDeterminism:
    def test_regeneration_is_byte_identical(self, tmp_path):
        """Re-running the generator must not change any file."""
        before = {
            p.name: p.read_bytes() for p in sorted(DATA_DIR.glob("*.csv"))
        }
        if not before:
            pytest.skip("no dataset generated")

        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True, text=True,
            cwd=str(SCRIPT.parent.parent),
        )
        assert result.returncode == 0, result.stderr

        after = {p.name: p.read_bytes() for p in sorted(DATA_DIR.glob("*.csv"))}
        assert set(before) == set(after)
        for name in before:
            assert before[name] == after[name], f"{name} changed between runs"
