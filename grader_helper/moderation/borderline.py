#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Students a point or two below the next grade up.

A total of 69 is a B2. A total of 70 is a B1, which is a different degree
classification on a transcript. The distance between them is one mark on a
piece of work somebody marked by hand, and that is the case a moderator most
wants to see -- not because the mark is likely wrong, but because if it *is*
wrong it costs the student more here than anywhere else in the range.

The department is discussing moderating on this basis rather than by a random
sample per band, so this is written as its own thing: it flags borderline
students whatever else the sampling does, and `sample_for_moderation` can be
told to take them as well.

**The mark of record is the rounded one.** The departmental sheet computes
``H = ROUND(SUM(...), 0)`` and bands *that*, so a student whose exact total is
69.6 has 70 on the sheet and is already a B1. Measuring the distance from the
unrounded figure would flag people who are not near a boundary at all and miss
people who are, so the distance is measured from the total as the sheet shows
it.

House convention: ``pl`` is pathlib, ``pr`` is polars.

    >>> import pathlib as pl
    >>> import polars as pr
"""

from ..dataframe_operations.make_letter_grade import (
    GRADE_BANDS,
    NO_PARTICIPATION,
    make_letter_grade,
)
from ..dependencies import pd

#: How close to the next band counts as borderline, in percentage points.
#: One, because totals are whole numbers -- the sheet rounds them -- so a
#: tolerance of 1 means "one more mark would have moved them up".
DEFAULT_TOLERANCE = 1.0

#: The columns added to a marks frame.
NEXT_GRADE_COLUMN = "Next Grade"
POINTS_COLUMN = "Points To Next"
BORDERLINE_COLUMN = "Borderline"

#: The band thresholds, ascending. `GRADE_BANDS` is highest-first; the next
#: grade up from any total is the lowest threshold above it.
_THRESHOLDS: tuple[tuple[float, str], ...] = tuple(
    sorted((band.lower, band.letter) for band in GRADE_BANDS)
)


def next_grade_up(total: float, fail_threshold: float = 35) -> tuple[str, float] | None:
    """The grade above `total`, and how many points away it is.

    Args:
    total (float): The student's module total, as the grade sheet shows it.
    fail_threshold (float): The mark below which the grade is F. Passed
        through to `make_letter_grade` so the current grade is decided the
        same way everywhere.

    Returns:
    tuple[str, float] | None: ``(letter, points_needed)``, or None where
    there is no grade above -- the top band, and no participation.

    Example:
        >>> next_grade_up(69)
        ('B1', 1.0)
        >>> next_grade_up(64)     # a B3, one mark below B2
        ('B2', 1.0)
        >>> next_grade_up(85) is None
        True
    """
    if make_letter_grade(total, fail_threshold=fail_threshold) == NO_PARTICIPATION:
        # No participation is not a mark one point below anything. A student
        # who sat nothing is not on the edge of a D1.
        return None

    for threshold, letter in _THRESHOLDS:
        if threshold > total:
            return letter, float(threshold) - float(total)
    return None  # already in the top band


def flag_borderline(
    df: pd.DataFrame,
    tolerance: float = DEFAULT_TOLERANCE,
    total_column: str = "Total % Grade",
    fail_threshold: float = 35,
) -> pd.DataFrame:
    """
    Mark the students within `tolerance` points of the next grade up.

    Args:
    df (pd.DataFrame): A prepared marks frame, as
        `prepare_data_for_departmental_template` returns it.
    tolerance (float): How close counts. Defaults to 1.0 -- one more mark.
    total_column (str): The column holding the module total.
    fail_threshold (float): Passed to `make_letter_grade`.

    Returns:
    pd.DataFrame: A copy with three columns added -- 'Next Grade', 'Points To
    Next' and 'Borderline'. Nothing is dropped and no rows are removed, so
    the frame stays usable for everything else.

    Note:
        A student already in the top band, and one with no participation, get
        no next grade and are never borderline. Neither is one point below
        anything.

        The distance is measured from the total **as the sheet shows it**,
        which is the rounded one. See this module's docstring.

    Raises:
    ValueError: If `df` is not a DataFrame or has no total column.

    Example:
        >>> flagged = flag_borderline(sheet)
        >>> flagged[flagged["Borderline"]][["Name", "Letter Grade", "Next Grade"]]
    """
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a pandas DataFrame")
    if total_column not in df.columns:
        raise ValueError(
            f"DataFrame has no {total_column!r} column, so nobody's distance "
            "to the next grade can be measured. Run "
            "prepare_data_for_departmental_template first, which adds it."
        )
    if tolerance <= 0:
        raise ValueError(
            f"tolerance must be greater than 0, not {tolerance}. A tolerance "
            "of 0 would flag only students already on the boundary, who are "
            "in the higher band already."
        )

    flagged = df.copy()
    nearest = [
        next_grade_up(total, fail_threshold=fail_threshold)
        if pd.notna(total)
        else None
        for total in flagged[total_column]
    ]

    flagged[NEXT_GRADE_COLUMN] = [item[0] if item else None for item in nearest]
    flagged[POINTS_COLUMN] = [item[1] if item else None for item in nearest]
    flagged[BORDERLINE_COLUMN] = [
        bool(item and item[1] <= tolerance) for item in nearest
    ]
    return flagged
