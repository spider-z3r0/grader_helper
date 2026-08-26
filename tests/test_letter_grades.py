#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""UL letter-grade bands, 2026 scale.

Pinned exhaustively at every boundary, because these are institutional
policy rather than implementation detail. The source of truth is the 2026
departmental grade sheet -- the "EHS grades UG modules" tab and the band
table at GradeTemplate rows 7-17.

Changes from the previous scale, which this file used to pin:
  - D2 is gone entirely
  - C3 widened to 40-50 (was 45-50)
  - D1 shifted down to 35-40 (was 40-45)
  - F has no lower bound (was 10-35)
"""

import pytest

from grader_helper import make_letter_grade
from grader_helper.dataframe_operations.make_letter_grade import (
    GRADE_BANDS,
    NO_PARTICIPATION,
    grade_band,
)

# (score, expected) at and around every band edge.
BANDS = [
    (0.5, "F"),
    (1, "F"),
    (10, "F"),
    (34, "F"),
    (34.9, "F"),
    (35, "D1"),
    (39, "D1"),
    (39.9, "D1"),
    (40, "C3"),
    (45, "C3"),
    (49, "C3"),
    (49.9, "C3"),
    (50, "C2"),
    (54, "C2"),
    (55, "C1"),
    (59, "C1"),
    (60, "B3"),
    (64, "B3"),
    (65, "B2"),
    (69, "B2"),
    (70, "B1"),
    (74, "B1"),
    (75, "A2"),
    (79, "A2"),
    (80, "A1"),
    (99, "A1"),
    (100, "A1"),
]


@pytest.mark.parametrize("score,expected", BANDS)
def test_band_boundaries(score, expected):
    assert make_letter_grade(score) == expected


def test_d2_no_longer_exists():
    """The 2026 scale retired D2; nothing may return it."""
    assert "D2" not in {band.letter for band in GRADE_BANDS}
    assert all(make_letter_grade(s) != "D2" for s in range(0, 101))


def test_c3_covers_the_full_forty_to_fifty_band():
    """C3 is a ten-point band now, the widest on the scale."""
    assert all(make_letter_grade(s) == "C3" for s in range(40, 50))


def test_zero_is_no_participation_not_a_fail():
    """The sheet distinguishes an absence from a bad mark.

    GradeTemplate column I reads IF(ROUND(total,2) > 0, <bands>, "NG"), and
    the average QPV explicitly excludes NG. A student who submitted and
    scored 1 has failed; a student who submitted nothing has no grade.
    """
    assert make_letter_grade(0) == NO_PARTICIPATION
    assert make_letter_grade(0.0) == NO_PARTICIPATION
    assert make_letter_grade(0.5) == "F"


def test_one_hundred_is_a1():
    """Guard against the off-by-one in the sheet's own formula.

    GradeTemplate's nested IF tests AND(total >= $A$17, total < $B$17) with
    A17=80 and B17=100, so a mark of exactly 100 matches no band and falls
    through to "NG". A perfect score is an A1, not an absence.
    """
    assert make_letter_grade(100) == "A1"


def test_fail_threshold_raises_the_pass_mark():
    """Professionally accredited courses can require a higher pass."""
    assert make_letter_grade(35) == "D1"
    assert make_letter_grade(35, fail_threshold=40) == "F"
    assert make_letter_grade(39, fail_threshold=40) == "F"
    assert make_letter_grade(40, fail_threshold=40) == "C3"


@pytest.mark.parametrize("bad", [-1, 101, 1000])
def test_out_of_range_scores_raise(bad):
    with pytest.raises(ValueError):
        make_letter_grade(bad)


@pytest.mark.parametrize("bad", ["70", None, [70]])
def test_non_numeric_scores_raise(bad):
    with pytest.raises(ValueError):
        make_letter_grade(bad)


def test_fail_threshold_must_be_in_range():
    with pytest.raises(ValueError):
        make_letter_grade(70, fail_threshold=101)


# ---------------------------------------------------------------------------
# The band table itself
# ---------------------------------------------------------------------------


def test_bands_are_contiguous_and_cover_zero_to_one_hundred():
    """No gaps and no overlaps, or some score has no grade."""
    ascending = sorted(GRADE_BANDS, key=lambda b: b.lower)
    assert ascending[0].lower == 0
    assert ascending[-1].upper == 100
    for lower, upper in zip(ascending, ascending[1:]):
        assert lower.upper == upper.lower, f"gap or overlap at {lower.upper}"


@pytest.mark.parametrize(
    "letter,award,qpv",
    [
        ("A1", "First Honours", 4.0),
        ("A2", "First Honours", 3.6),
        ("B1", "Honours 2.1", 3.2),
        ("B2", "Honours 2.1", 3.0),
        ("B3", "Honours 2.2", 2.8),
        ("C1", "Honours 2.2", 2.6),
        ("C2", "Third Honours", 2.4),
        ("C3", "Third Honours", 2.0),
        ("D1", "Compensated Fail", 1.6),
        ("F", "Fail", 0.0),
    ],
)
def test_award_equivalent_and_qpv(letter, award, qpv):
    """Transcribed from GradeTemplate rows 8-17, columns C, D and E."""
    band = grade_band(letter)
    assert band.award == award
    assert band.qpv == qpv


def test_unknown_letter_grade_is_rejected():
    with pytest.raises(KeyError):
        grade_band("D2")
