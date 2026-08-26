#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""UL letter-grade bands.

These are institutional policy, not implementation detail, so they are
pinned exhaustively at every boundary. Phase 3 replaces the if/elif ladder
with a polars ``cut`` expression; these tests are what make that swap safe.
"""

import pytest

from grader_helper import make_letter_grade

# (score, expected) at and around every band edge.
BANDS = [
    (11, "F"),
    (34, "F"),
    (35, "D2"),
    (39, "D2"),
    (40, "D1"),
    (44, "D1"),
    (45, "C3"),
    (49, "C3"),
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
    (100, "A1"),
]


@pytest.mark.parametrize("score,expected", BANDS)
def test_band_boundaries(score, expected):
    assert make_letter_grade(score) == expected


@pytest.mark.parametrize("score", [0, 1, 5, 10])
@pytest.mark.xfail(
    reason=(
        "The lowest band is guarded by `10 < score < fail_threshold`, so a "
        "score of 0-10 matches no branch and falls through to 'NG' "
        "(no grade) instead of 'F'. A genuine zero is a fail, not an "
        "absence of grade."
    ),
    strict=True,
)
def test_very_low_scores_should_be_a_fail_not_no_grade(score):
    assert make_letter_grade(score) == "F"


@pytest.mark.parametrize("score", [0, 1, 5, 10])
def test_very_low_scores_currently_return_ng(score):
    """Characterisation of the behaviour above, so the change is visible."""
    assert make_letter_grade(score) == "NG"


def test_fail_threshold_raises_the_pass_mark():
    """Courses with professional accreditation can require a higher pass."""
    # Default: 35 is the bottom of D2.
    assert make_letter_grade(35) == "D2"
    # Raised: 35 and 37 are now fails, 40 still passes.
    assert make_letter_grade(35, fail_threshold=40) == "F"
    assert make_letter_grade(37, fail_threshold=40) == "F"
    assert make_letter_grade(40, fail_threshold=40) == "D1"


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
