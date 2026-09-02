#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Who in the finished sheet somebody has to do something about.

The departmental sheet is the record. These are the two lists that get read
*off* it and acted on, and both were being worked out by eye:

**Repeats.** Every student at F or NG has to be contacted about repeating.
NG is not the same as F -- it means no participation at all, where F means
submitted work that did not pass -- but both go on the same list, because
both are a conversation the module leader has to start.

**Borderlines.** Every student within a mark of the next band up. One mark
is the tolerance because the sheet's totals are whole numbers, so "within
one" means one more mark would have moved them. `flag_borderline` has
computed this since the moderation sample was built; nothing outside
moderation ever looked at it, and it is at least as useful to the person
deciding who to look at again.

Neither list is a decision. They are the students a decision is due about,
written down so the decision is made from a list rather than from a scroll
through eighty rows.

It lives at the top level beside `collating.py` for the same reason: it is
an assembly layer, over `moderation` and the prepared marks frame.

House convention::

    import pathlib as pl        # pl is pathlib
    import polars as pr         # pr is polars
"""

import pathlib as pl
from typing import NamedTuple, Sequence

import pandas as pd

from .dataframe_operations.sort_order_columns import TRAILING_COLUMNS
from .models import Module
from .moderation.borderline import (
    BORDERLINE_COLUMN,
    DEFAULT_TOLERANCE,
    NEXT_GRADE_COLUMN,
    POINTS_COLUMN,
    flag_borderline,
)

#: The grades that mean the student has not passed this module.
#:
#: Both, not just F. NG is *no participation* where F is work that did not
#: pass, and the difference matters in the conversation -- but the
#: conversation happens either way, so one list.
REPEAT_GRADES: tuple[str, ...] = ("F", "NG")

#: The column the letter grade is in, as the departmental sheet names it.
GRADE_COLUMN = TRAILING_COLUMNS[1]

#: What the two lists are called, under the module folder. Named for the
#: module, because these get attached to emails and a file called
#: "repeats.csv" tells the reader nothing about which module's repeats.
REPEATS_STEM = "repeats"
BORDERLINE_STEM = "borderline"


class Outcomes(NamedTuple):
    """The two follow-up lists, and where they were written.

    The frames are the point; the paths are what makes it a step with
    evidence, so `record()` can set the flag from what it produced.
    """

    #: Students at F or NG, whole rows from the sheet.
    repeats: pd.DataFrame
    #: Students within `tolerance` of the next band, with the three columns
    #: `flag_borderline` adds.
    borderline: pd.DataFrame
    #: Where each was written, or None when nothing was.
    repeats_path: pl.Path | None
    borderline_path: pl.Path | None

    def __str__(self) -> str:
        return (
            f"{len(self.repeats)} to repeat, "
            f"{len(self.borderline)} within a mark of the next grade"
        )


def _require(sheet: pd.DataFrame, column: str) -> None:
    if not isinstance(sheet, pd.DataFrame):
        raise ValueError(
            "sheet must be a pandas DataFrame, as "
            "prepare_data_for_departmental_template returns it."
        )
    if column not in sheet.columns:
        raise ValueError(
            f"The sheet has no {column!r} column, so this cannot be worked "
            f"out. Columns present: {list(sheet.columns)}. "
            "prepare_data_for_departmental_template adds it."
        )


def students_to_repeat(
    sheet: pd.DataFrame,
    *,
    grades: Sequence[str] = REPEAT_GRADES,
    grade_column: str = GRADE_COLUMN,
) -> pd.DataFrame:
    """
    The students who have not passed, whole rows from the sheet.

    Whole rows deliberately: the per-assessment marks are what say *why*
    they did not pass, and a repeat conversation that starts from a total
    alone starts by going back to the sheet.

    Args:
    sheet (pd.DataFrame): The prepared marks frame.
    grades (Sequence[str]): Which grades count. Defaults to F and NG.
    grade_column (str): Where the letter grade is.

    Returns:
    pd.DataFrame: The matching rows, in the sheet's own order.

    Raises:
    ValueError: If the sheet has no grade column.

    Example:
        >>> students_to_repeat(sheet)[["Name", "Total % Grade", "Letter Grade"]]
    """
    _require(sheet, grade_column)
    wanted = [str(g).strip().upper() for g in grades]
    matches = sheet[grade_column].astype(str).str.strip().str.upper().isin(wanted)
    return sheet.loc[matches].copy()


def students_on_a_boundary(
    sheet: pd.DataFrame,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    total_column: str = TRAILING_COLUMNS[0],
    fail_threshold: float = 35,
) -> pd.DataFrame:
    """
    The students within `tolerance` marks of the next grade band.

    A thin read over :func:`flag_borderline`, which has computed this since
    the moderation sample was built and which nothing outside moderation
    ever looked at.

    Args:
    sheet (pd.DataFrame): The prepared marks frame.
    tolerance (float): How close counts, in percentage points. One by
        default, because the sheet's totals are whole numbers, so "within
        one" means one more mark would have moved them up.
    total_column (str): Where the module total is.
    fail_threshold (float): Passed through to the banding.

    Returns:
    pd.DataFrame: The matching rows, with `Next Grade`, `Points To Next` and
    `Borderline` added, nearest the boundary first.

    Example:
        >>> students_on_a_boundary(sheet)[["Name", "Letter Grade", "Next Grade"]]
    """
    _require(sheet, total_column)
    flagged = flag_borderline(
        sheet,
        tolerance=tolerance,
        total_column=total_column,
        fail_threshold=fail_threshold,
    )
    on_it = flagged.loc[flagged[BORDERLINE_COLUMN]].copy()
    return on_it.sort_values(POINTS_COLUMN, kind="stable")


def write_outcomes(
    module: Module,
    sheet: pd.DataFrame,
    *,
    folder: pl.Path | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
    overwrite: bool = False,
    save: bool = True,
) -> Outcomes:
    """
    Work out the two follow-up lists and write them beside the module.

    Args:
    module (Module): The module, for its code and its root.
    sheet (pd.DataFrame): The prepared marks frame, as
        `prepare_data_for_departmental_template` returns it.
    folder (pl.Path | None): Where to write. Defaults to the module root,
        beside the departmental sheet.
    tolerance (float): How close to the next band counts as borderline.
    overwrite (bool): Replace files that are already there.
    save (bool): Write them. False works the lists out and writes nothing.

    Returns:
    Outcomes: The two frames, and where they went.

    Raises:
    ValueError: If the module has no root and no folder was given.
    FileExistsError: If a file exists and `overwrite` is False. Checked for
        both before either is written, so a refusal does not leave one list
        current and the other stale.

    Example:
        >>> outcomes = write_outcomes(module, sheet)
        >>> handle.record(outcomes)
    """
    repeats = students_to_repeat(sheet)
    borderline = students_on_a_boundary(sheet, tolerance=tolerance)

    if not save:
        return Outcomes(repeats, borderline, None, None)

    where = pl.Path(folder) if folder is not None else module.root
    if where is None:
        raise ValueError(
            "This module has no root, so there is nowhere to write the "
            "lists. Load it with load_module(), or pass folder=."
        )

    targets = {
        "repeats": where / f"{module.code} {REPEATS_STEM}.csv",
        "borderline": where / f"{module.code} {BORDERLINE_STEM}.csv",
    }
    if not overwrite:
        # Both before either: a refusal half way through leaves one list
        # current and the other from the last run, which is worse than
        # neither being written.
        existing = sorted(str(p) for p in targets.values() if p.exists())
        if existing:
            raise FileExistsError(
                f"Already there: {existing}. They are worked out from the "
                "sheet, so replacing them is safe -- pass overwrite=True."
            )

    where.mkdir(parents=True, exist_ok=True)
    repeats.to_csv(targets["repeats"], index=False)
    borderline.to_csv(targets["borderline"], index=False)
    return Outcomes(repeats, borderline, targets["repeats"], targets["borderline"])


__all__ = [
    "BORDERLINE_COLUMN",
    "GRADE_COLUMN",
    "NEXT_GRADE_COLUMN",
    "Outcomes",
    "POINTS_COLUMN",
    "REPEAT_GRADES",
    "students_on_a_boundary",
    "students_to_repeat",
    "write_outcomes",
]
