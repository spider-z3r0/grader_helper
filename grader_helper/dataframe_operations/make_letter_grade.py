#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""UL letter grades, award equivalents and quality point values.

The bands are institutional policy, taken from the 2026 departmental grade
sheet ("EHS grades UG modules" and the band table in GradeTemplate rows
7-17). They are defined here once, as data, so that the conversion, the
departmental sheet and any future polars expression all read from the same
source.

The 2026 scale differs from the one this module previously implemented:
D2 is gone, C3 now spans 40-50, D1 spans 35-40, and F has no lower bound.
"""

from typing import NamedTuple


class GradeBand(NamedTuple):
    """One row of the institutional grade table."""

    lower: float  #: inclusive
    upper: float  #: exclusive, except for the top band
    letter: str
    award: str
    qpv: float


#: Percentage bands, highest first. Lower bound inclusive, upper exclusive,
#: except the top band which includes 100.
GRADE_BANDS: tuple[GradeBand, ...] = (
    GradeBand(80, 100, "A1", "First Honours", 4.0),
    GradeBand(75, 80, "A2", "First Honours", 3.6),
    GradeBand(70, 75, "B1", "Honours 2.1", 3.2),
    GradeBand(65, 70, "B2", "Honours 2.1", 3.0),
    GradeBand(60, 65, "B3", "Honours 2.2", 2.8),
    GradeBand(55, 60, "C1", "Honours 2.2", 2.6),
    GradeBand(50, 55, "C2", "Third Honours", 2.4),
    GradeBand(40, 50, "C3", "Third Honours", 2.0),
    GradeBand(35, 40, "D1", "Compensated Fail", 1.6),
    GradeBand(0, 35, "F", "Fail", 0.0),
)

#: Awarded where there is no participation at all, as distinct from a mark
#: of zero on submitted work. The departmental sheet expresses this as
#: IF(ROUND(total,2) > 0, <band lookup>, "NG"), and excludes NG from the
#: average QPV.
NO_PARTICIPATION = "NG"


def make_letter_grade(score: int | float, fail_threshold: int | float = 35) -> str:
    """
    Convert a numerical score to a letter grade.

    Args:
    score (int|float): The numerical score.
    fail_threshold (int): The mark below which the grade is F. Defaults to
        35, the institutional pass mark. Raise it for courses with higher
        requirements, such as professionally accredited programmes.

    Returns:
    str: The letter grade, or "NG" where there was no participation.

    Notes:
        A score of exactly 0 is treated as no participation and returns
        "NG", matching the departmental sheet. Any mark above 0 but below
        the fail threshold is "F" -- a student who submitted and scored
        poorly has a fail, not an absence.
    """

    # check that score is an int or float
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise ValueError("Score must be an integer or float.")

    # check that fail_threshold is an int or float
    if not isinstance(fail_threshold, (int, float)):
        raise ValueError("Fail threshold must be an integer or float.")

    # check that score is between 0 and 100
    if not 0 <= score <= 100:
        raise ValueError("Score must be between 0 and 100.")

    # check that fail_threshold is between 0 and 100
    if not 0 <= fail_threshold <= 100:
        raise ValueError("Fail threshold must be between 0 and 100.")

    if score <= 0:
        return NO_PARTICIPATION

    if score < fail_threshold:
        return "F"

    for band in GRADE_BANDS:
        if score >= band.lower:
            return band.letter

    return NO_PARTICIPATION


def grade_band(letter: str) -> GradeBand:
    """Look up a band by its letter grade.

    Raises
    ------
    KeyError
        If ``letter`` is not one of the institutional grades.
    """
    for band in GRADE_BANDS:
        if band.letter == letter:
            return band
    raise KeyError(
        f"{letter!r} is not a UL letter grade. "
        f"Expected one of {[b.letter for b in GRADE_BANDS]} or "
        f"{NO_PARTICIPATION!r}."
    )
