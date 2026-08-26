#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""One workbook per grader, holding only that grader's allocation.

Each grader's initials name their file (``KOM.xlsx``), which is why
``Person.initials`` is upper-cased and has to be unique.

This used to prompt on stdin before replacing an existing file. That made it
unusable from anything without a terminal -- a marimo dashboard calling
``input()`` waits forever -- and untestable without faking stdin. It also
crashed: ``choice[0]`` raises IndexError when the user just presses Enter.
The decision is now the caller's, passed in as ``overwrite``.
"""

import pathlib as pl
from typing import Sequence

from ..dependencies import pd

#: The column holding each row's allocated grader. Matches the default that
#: assign_graders_individual writes.
GRADER_COLUMN = "grader"


def save_grader_sheets(
    data: pd.DataFrame,
    folder: pl.Path,
    graders: Sequence[str],
    criteria: Sequence[str] | None = None,
    overwrite: bool = False,
    grader_column: str = GRADER_COLUMN,
) -> dict[str, pl.Path]:
    """
    Write one Excel workbook per grader, holding that grader's rows.

    Args:
    data (pd.DataFrame): The allocated submissions, one row per student.
    folder (pl.Path): Where the workbooks are written.
    graders (Sequence[str]): The graders to write a workbook for.
    criteria (Sequence[str] | None): Extra empty columns for the grader to
        fill in, appended in order.
    overwrite (bool): Replace workbooks that already exist. Defaults to
        False, because an existing workbook may already hold marks.
    grader_column (str): The column naming each row's grader.

    Returns:
    dict[str, pl.Path]: Each grader mapped to the file written for them.

    Raises:
    KeyError: If ``grader_column`` is not in ``data``.
    ValueError: If ``graders`` is empty or holds duplicates.
    FileExistsError: If a workbook exists and ``overwrite`` is False. Nothing
        is written in that case -- the check runs over every grader first, so
        a refusal does not leave half the graders written and half not.
    """
    folder = pl.Path(folder)

    if grader_column not in data.columns:
        raise KeyError(
            f"No {grader_column!r} column in the data, so there is no way to "
            f"tell whose rows are whose. Columns present: {list(data.columns)}. "
            "assign_graders_individual writes this column."
        )

    graders = list(graders)
    if not graders:
        raise ValueError("graders is empty, so there is nothing to write.")
    duplicates = {g for g in graders if graders.count(g) > 1}
    if duplicates:
        raise ValueError(
            f"Duplicate grader(s): {sorted(duplicates)}. Each grader gets one "
            "workbook named for them, so the names must be unique."
        )

    if criteria is not None:
        new_cols = list(data.columns) + [
            c for c in criteria if c not in data.columns
        ]
        data = data.reindex(columns=new_cols)

    targets = {g: folder / f"{g}.xlsx" for g in graders}

    # Check every target before writing any of them. A refusal half way
    # through would leave the allocation split across old and new files.
    if not overwrite:
        existing = sorted(g for g, path in targets.items() if path.exists())
        if existing:
            raise FileExistsError(
                f"Workbook(s) already exist for: {', '.join(existing)}. They "
                "may already hold marks, so nothing has been written. Pass "
                "overwrite=True to replace them."
            )

    folder.mkdir(parents=True, exist_ok=True)
    for grader, path in targets.items():
        data.loc[data[grader_column] == grader].to_excel(path, index=False)

    return targets
