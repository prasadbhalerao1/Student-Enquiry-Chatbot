"""Tests for the analytics service against the fixture department."""
from __future__ import annotations

from datetime import date

from app.services import analytics as A

TODAY = date(2026, 4, 15)


class TestSubjectAttendance:
    def test_summary_counts(self, db_session):
        s = A.subject_attendance_summary(db_session, "CB3202T", 75.0)
        assert s["enrolled_students"] == 3
        # 38 + 30 + 25 = 93 of 120 conducted.
        assert s["class_attendance_percentage"] == 77.5
        # Only STU0003 (62.5%) is below. STU0002 sits exactly on 75%.
        assert s["students_below_threshold"] == 1

    def test_exact_threshold_is_not_flagged(self, db_session):
        page = A.subject_attendance(db_session, "CB3202T", 75.0, below_only=True)
        assert [r["student_id"] for r in page.items] == ["STU0003"]

    def test_pooled_and_mean_are_both_reported(self, db_session):
        s = A.subject_attendance_summary(db_session, "CB3202T", 75.0)
        assert s["class_attendance_percentage"] is not None
        assert s["mean_student_attendance_percentage"] is not None

    def test_status_labels_are_textual(self, db_session):
        page = A.subject_attendance(db_session, "CB3202T", 75.0)
        labels = {r["status"] for r in page.items}
        assert labels <= {"Below threshold", "At risk", "Meeting threshold"}
        # 95% is comfortable, 75% exactly is "at risk", 62.5% is below.
        by_id = {r["student_id"]: r["status"] for r in page.items}
        assert by_id["STU0001"] == "Meeting threshold"
        assert by_id["STU0002"] == "At risk"
        assert by_id["STU0003"] == "Below threshold"

    def test_pagination(self, db_session):
        page = A.subject_attendance(db_session, "CB3202T", 75.0, page=1, page_size=2)
        assert len(page.items) == 2
        assert page.total == 3
        assert page.total_pages == 2

    def test_sorting(self, db_session):
        asc = A.subject_attendance(db_session, "CB3202T", 75.0, sort_dir="asc")
        desc = A.subject_attendance(db_session, "CB3202T", 75.0, sort_dir="desc")
        assert asc.items[0]["student_id"] == "STU0003"
        assert desc.items[0]["student_id"] == "STU0001"

    def test_search_filters(self, db_session):
        page = A.subject_attendance(db_session, "CB3202T", 75.0, search="Student 1")
        assert [r["student_id"] for r in page.items] == ["STU0001"]

    def test_low_attendance_includes_recovery_count(self, db_session):
        rows = A.low_attendance_students(db_session, ["CB3202T", "CB3202L"], 75.0)
        assert rows
        for r in rows:
            assert r["classes_needed_for_threshold"] > 0
            assert r["attendance_percentage"] < 75.0


class TestPerformance:
    def test_zero_is_scored_missing_is_excluded(self, db_session):
        """STU0002 has a real 0 on one assessment and no mark on the other."""
        summary = A.subject_performance_summary(db_session, "CB3202T")
        by_id = {s["student_id"]: s for s in summary["students"]}

        stu2 = by_id["STU0002"]
        assert stu2["evaluated_count"] == 1
        assert stu2["missing_count"] == 1
        # Scored on the 0/30 only, so 0% -- not 50% and not None.
        assert stu2["performance_percentage"] == 0.0

    def test_absent_is_tracked_separately(self, db_session):
        summary = A.subject_performance_summary(db_session, "CB3202T")
        by_id = {s["student_id"]: s for s in summary["students"]}
        stu3 = by_id["STU0003"]
        assert stu3["absent_count"] == 1
        assert stu3["missing_count"] == 1
        # Scored only on the quiz: 5/10 = 50%.
        assert stu3["performance_percentage"] == 50.0

    def test_fully_evaluated_student(self, db_session):
        summary = A.subject_performance_summary(db_session, "CB3202T")
        by_id = {s["student_id"]: s for s in summary["students"]}
        # 27/30 * 0.5 + 9/10 * 0.5 = 0.45 + 0.45 = 0.9 over weight 1.0 -> 90%.
        assert by_id["STU0001"]["performance_percentage"] == 90.0

    def test_assessment_rollup_separates_evaluated_from_pending(self, db_session):
        rows = A.subject_assessments(db_session, "CB3202T")
        by_id = {r["assessment_id"]: r for r in rows}
        quiz = by_id["ASM0002"]
        assert quiz["total_students"] == 3
        assert quiz["evaluated_count"] == 2       # STU0001, STU0003
        assert quiz["pending_evaluation_count"] == 1  # STU0002
        exam = by_id["ASM0001"]
        assert exam["absent_count"] == 1

    def test_below_marks_threshold(self, db_session):
        rows = A.students_below_marks_threshold(db_session, "CB3202T", 60.0)
        ids = [r["student_id"] for r in rows]
        assert "STU0002" in ids  # 0%
        assert "STU0003" in ids  # 50%
        assert "STU0001" not in ids  # 90%

    def test_empty_subject_is_handled(self, db_session):
        summary = A.subject_performance_summary(db_session, "CB3201T")
        assert summary["assessment_count"] == 0
        assert summary["students"] == []


class TestAssignments:
    def test_overdue_requires_both_missing_and_past_due(self, db_session):
        rows = A.assignment_summary(db_session, "CB3202T", today=TODAY)
        by_id = {r["assignment_id"]: r for r in rows}

        closed = by_id["ASG0001"]
        assert closed["is_past_due"] is True
        # Only STU0001 never submitted.
        assert closed["overdue_count"] == 1
        assert closed["submitted_count"] == 1
        assert closed["evaluated_count"] == 1

    def test_pending_before_due_date_is_not_overdue(self, db_session):
        rows = A.assignment_summary(db_session, "CB3202T", today=TODAY)
        by_id = {r["assignment_id"]: r for r in rows}
        open_one = by_id["ASG0002"]
        assert open_one["is_past_due"] is False
        assert open_one["pending_count"] == 1
        assert open_one["overdue_count"] == 0
        assert open_one["not_yet_due_pending_count"] == 1

    def test_submitted_but_unmarked_is_never_overdue(self, db_session):
        rows = A.student_assignment_status(
            db_session, "STU0002", ["CB3202T"], today=TODAY
        )
        sub = next(r for r in rows if r["assignment_id"] == "ASG0001")
        assert sub["status"] == "submitted"
        assert sub["marks_obtained"] is None
        assert sub["is_overdue"] is False

    def test_overdue_list(self, db_session):
        rows = A.overdue_assignments(db_session, ["CB3202T"], today=TODAY)
        assert len(rows) == 1
        assert rows[0]["student_id"] == "STU0001"
        assert rows[0]["days_overdue"] == (TODAY - date(2026, 2, 20)).days


class TestExtracurricular:
    def test_aggregate_excludes_out_of_scope_students(self, db_session):
        """STU0004 participates but is not in CB3202T/L."""
        summary = A.extracurricular_summary(db_session, ["CB3202T", "CB3202L"])
        assert summary["students_in_scope"] == 3
        assert summary["students_with_activities"] == 1   # STU0001 only
        assert summary["students_without_activities"] == 2
        assert summary["achievement_count"] == 1

    def test_aggregate_returns_no_individual_profiles(self, db_session):
        summary = A.extracurricular_summary(db_session, ["CB3202T"])
        assert "students" not in summary
        assert "by_category" in summary

    def test_individual_record(self, db_session):
        rows = A.student_activities(db_session, "STU0001")
        assert len(rows) == 1
        assert rows[0]["role"] == "Team Lead"
        assert rows[0]["achievement"] == "First Place"

    def test_no_invented_achievements(self, db_session):
        rows = A.student_activities(db_session, "STU0004")
        assert rows[0]["achievement"] is None


class TestDashboard:
    def test_metrics_come_from_the_database(self, db_session):
        d = A.teacher_dashboard(
            db_session, "TCH001", ["CB3202T", "CB3202L"], 75.0, today=TODAY
        )
        assert d["subject_count"] == 2
        assert d["student_count"] == 3
        assert d["attendance_record_count"] == 6
        # STU0003 in CB3202T (62.5%) and STU0002 in CB3202L (50%).
        assert d["students_below_threshold"] == 2
        assert d["overdue_assignment_count"] == 1

    def test_calculation_notes_are_documented(self, db_session):
        d = A.teacher_dashboard(db_session, "TCH001", ["CB3202T"], 75.0, today=TODAY)
        notes = d["calculation_notes"]
        assert "pooled" in notes["overall_class_attendance_percentage"].lower()
        assert "unweighted" in (
            notes["overall_mean_student_attendance_percentage"].lower()
        )

    def test_upcoming_deadlines_exclude_past_ones(self, db_session):
        d = A.teacher_dashboard(db_session, "TCH001", ["CB3202T"], 75.0, today=TODAY)
        for item in d["upcoming_deadlines"]:
            assert item["due_date"] >= TODAY

    def test_no_subjects_yields_empty_metrics(self, db_session):
        d = A.teacher_dashboard(db_session, "TCH999", [], 75.0, today=TODAY)
        assert d["subject_count"] == 0
        assert d["student_count"] == 0


class TestStudentSummary:
    def test_combines_all_three_areas(self, db_session):
        s = A.student_academic_summary(
            db_session, "STU0002", ["CB3202T", "CB3202L"], 75.0
        )
        assert s["full_name"] == "Student 2"
        assert len(s["attendance"]) == 2
        assert s["subjects_below_attendance_threshold"] == 1  # the lab
        assert s["assessments_not_evaluated"] == 1

    def test_evaluation_states_are_distinct(self, db_session):
        s = A.student_academic_summary(db_session, "STU0003", ["CB3202T"], 75.0)
        states = {a["evaluation_state"] for a in s["assessments"]}
        assert "absent" in states
        assert "evaluated" in states
