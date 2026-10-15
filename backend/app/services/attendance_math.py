"""Centralised, exact attendance arithmetic.

Every attendance percentage shown anywhere in this application -- API responses,
dashboard metrics, CSV exports, AI tool output -- comes from this module. Nothing
recomputes it inline.

Integer / Fraction arithmetic is used throughout so results do not drift with
floating point rounding.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import ceil


class AttendanceInputError(ValueError):
    """Raised when attendance counts or a target threshold are not usable."""


def validate_counts(classes_attended: int, classes_conducted: int) -> None:
    if not isinstance(classes_attended, int) or not isinstance(classes_conducted, int):
        raise AttendanceInputError("Class counts must be integers.")
    if classes_conducted <= 0:
        raise AttendanceInputError("classes_conducted must be greater than zero.")
    if classes_attended < 0:
        raise AttendanceInputError("classes_attended cannot be negative.")
    if classes_attended > classes_conducted:
        raise AttendanceInputError(
            "classes_attended cannot exceed classes_conducted."
        )


def attendance_percentage(
    classes_attended: int, classes_conducted: int, *, digits: int = 2
) -> float:
    """attended / conducted * 100, rounded to `digits` decimal places."""
    validate_counts(classes_attended, classes_conducted)
    exact = Fraction(classes_attended * 100, classes_conducted)
    return round(float(exact), digits)


def is_below_threshold(
    classes_attended: int, classes_conducted: int, threshold: float
) -> bool:
    """Compare exactly, so e.g. 30/40 == 75.0 is NOT counted as below 75."""
    validate_counts(classes_attended, classes_conducted)
    _validate_threshold(threshold, allow_100=True)
    return Fraction(classes_attended * 100, classes_conducted) < Fraction(
        str(threshold)
    )


def _validate_threshold(target: float, *, allow_100: bool) -> None:
    if target < 0:
        raise AttendanceInputError("Target attendance cannot be negative.")
    limit = 100 if allow_100 else 100
    if target > limit:
        raise AttendanceInputError("Target attendance cannot exceed 100%.")


def classes_needed_for_target(
    classes_attended: int, classes_conducted: int, target: float
) -> int:
    """Minimum consecutive future classes that must ALL be attended to reach `target`.

        n = max(0, ceil((T*C - A*100) / (100 - T)))

    `target` is a percentage (e.g. 75). Raises AttendanceInputError for a target
    of 100% when the student has already missed at least one class, because no
    finite number of future classes can recover a perfect record.
    """
    validate_counts(classes_attended, classes_conducted)
    _validate_threshold(target, allow_100=True)

    t = Fraction(str(target))
    a = Fraction(classes_attended)
    c = Fraction(classes_conducted)

    if a * 100 >= t * c:  # already at or above the target
        return 0

    if t == 100:
        raise AttendanceInputError(
            "A target of 100% is unreachable once any class has been missed."
        )

    return max(0, ceil((t * c - a * 100) / (100 - t)))


@dataclass(frozen=True)
class AttendanceRecord:
    """A single student-subject attendance summary with derived values."""

    student_id: str
    subject_code: str
    classes_attended: int
    classes_conducted: int
    threshold: float

    @property
    def percentage(self) -> float:
        return attendance_percentage(self.classes_attended, self.classes_conducted)

    @property
    def below_threshold(self) -> bool:
        return is_below_threshold(
            self.classes_attended, self.classes_conducted, self.threshold
        )

    @property
    def status(self) -> str:
        """Accessible text label, never colour alone."""
        if self.below_threshold:
            return "Below threshold"
        # "At risk" = within 5 points above the threshold.
        pct = Fraction(self.classes_attended * 100, self.classes_conducted)
        if pct < Fraction(str(self.threshold)) + 5:
            return "At risk"
        return "Meeting threshold"

    def classes_needed(self, target: float | None = None) -> int:
        return classes_needed_for_target(
            self.classes_attended, self.classes_conducted, target or self.threshold
        )


def aggregate_percentage(rows: list[tuple[int, int]], *, digits: int = 2) -> float | None:
    """Pooled ("class-level") attendance: sum(attended) / sum(conducted) * 100.

    This weights every CLASS equally. Use `mean_student_percentage` when every
    STUDENT should count equally instead. Returns None for an empty input.
    """
    if not rows:
        return None
    total_attended = sum(a for a, _ in rows)
    total_conducted = sum(c for _, c in rows)
    if total_conducted <= 0:
        return None
    return round(float(Fraction(total_attended * 100, total_conducted)), digits)


def mean_student_percentage(
    rows: list[tuple[int, int]], *, digits: int = 2
) -> float | None:
    """Unweighted mean of each student's own percentage. Returns None if empty."""
    if not rows:
        return None
    total = sum(Fraction(a * 100, c) for a, c in rows if c > 0)
    count = sum(1 for _, c in rows if c > 0)
    if count == 0:
        return None
    return round(float(total / count), digits)
