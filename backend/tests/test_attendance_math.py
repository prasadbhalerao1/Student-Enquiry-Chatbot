"""Tests for the central attendance arithmetic."""
from __future__ import annotations

import pytest

from app.services.attendance_math import (
    AttendanceInputError,
    aggregate_percentage,
    attendance_percentage,
    classes_needed_for_target,
    is_below_threshold,
    mean_student_percentage,
    validate_counts,
)


class TestPercentage:
    @pytest.mark.parametrize(
        "attended,conducted,expected",
        [
            (30, 40, 75.0),
            (0, 10, 0.0),
            (10, 10, 100.0),
            (1, 3, 33.33),
            (2, 3, 66.67),
            (25, 40, 62.5),
        ],
    )
    def test_known_values(self, attended, conducted, expected):
        assert attendance_percentage(attended, conducted) == expected

    def test_rejects_zero_conducted(self):
        with pytest.raises(AttendanceInputError):
            attendance_percentage(0, 0)

    def test_rejects_attended_above_conducted(self):
        with pytest.raises(AttendanceInputError):
            attendance_percentage(11, 10)

    def test_rejects_negative(self):
        with pytest.raises(AttendanceInputError):
            attendance_percentage(-1, 10)

    def test_rejects_non_integer(self):
        with pytest.raises(AttendanceInputError):
            validate_counts(1.5, 10)  # type: ignore[arg-type]


class TestThreshold:
    def test_exactly_at_threshold_is_not_below(self):
        # 30/40 is exactly 75%. Floating point must not push it under.
        assert is_below_threshold(30, 40, 75) is False

    def test_one_class_under_is_below(self):
        assert is_below_threshold(29, 40, 75) is True

    def test_thirds_are_exact(self):
        # 2/3 = 66.666...%, genuinely below 66.67 as a threshold.
        assert is_below_threshold(2, 3, 66.67) is True
        assert is_below_threshold(2, 3, 66.66) is False


class TestClassesNeeded:
    def test_already_above_target_needs_none(self):
        assert classes_needed_for_target(38, 40, 75) == 0

    def test_exactly_at_target_needs_none(self):
        assert classes_needed_for_target(30, 40, 75) == 0

    def test_known_case(self):
        # 25/40 = 62.5%. n = ceil((75*40 - 25*100) / 25) = ceil(500/25) = 20.
        assert classes_needed_for_target(25, 40, 75) == 20

    def test_result_actually_reaches_target(self):
        """The returned n must genuinely clear the threshold, and n-1 must not."""
        for attended, conducted, target in [
            (25, 40, 75), (10, 50, 75), (0, 1, 75), (17, 23, 80), (3, 19, 60),
        ]:
            n = classes_needed_for_target(attended, conducted, target)
            assert (attended + n) * 100 >= target * (conducted + n)
            if n > 0:
                assert (attended + n - 1) * 100 < target * (conducted + n - 1)

    def test_target_100_unreachable_after_a_miss(self):
        with pytest.raises(AttendanceInputError):
            classes_needed_for_target(39, 40, 100)

    def test_target_100_with_perfect_record_needs_none(self):
        assert classes_needed_for_target(40, 40, 100) == 0

    def test_rejects_target_above_100(self):
        with pytest.raises(AttendanceInputError):
            classes_needed_for_target(30, 40, 101)

    def test_rejects_negative_target(self):
        with pytest.raises(AttendanceInputError):
            classes_needed_for_target(30, 40, -5)


class TestAggregates:
    def test_pooled_weights_classes(self):
        # 90/100 and 1/2 pooled = 91/102.
        assert aggregate_percentage([(90, 100), (1, 2)]) == round(91 / 102 * 100, 2)

    def test_mean_weights_students(self):
        # 90% and 50% -> 70%.
        assert mean_student_percentage([(90, 100), (1, 2)]) == 70.0

    def test_pooled_and_mean_differ_on_uneven_denominators(self):
        rows = [(90, 100), (1, 2)]
        assert aggregate_percentage(rows) != mean_student_percentage(rows)

    def test_empty_returns_none(self):
        assert aggregate_percentage([]) is None
        assert mean_student_percentage([]) is None
