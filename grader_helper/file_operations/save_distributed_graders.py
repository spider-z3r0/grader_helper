#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The master sheet: every student and who is marking their work.

The counterpart to the per-grader workbooks. This is the one file that shows
the whole allocation, so it is what you check when a student asks who marked
them.

Like save_grader_sheets, this used to prompt on stdin. Worse, the two write
paths disagreed: the first wrote ``index=False`` and the overwrite branch did
not, so replacing the file silently added an unnamed index column -- which
then flowed into ingest_completed_graderfiles as a spurious column.
"""

import pathlib as pl

from ..dependencies import pd

#: The conventional filename for the master allocation sheet.
DISTRIBUTED_FILENAME = "distributed.xlsx"


def save_distributed_graders(
    d: pd.DataFrame,
    folder: pl.Path,
    overwrite: bool = False,
    filename: str = DISTRIBUTED_FILENAME,
) -> pl.Path:
    """
    Save the whole allocation to one Excel sheet.

    Args:
    d (pd.DataFrame): The allocated students.
    folder (pl.Path): Where the sheet is written.
    overwrite (bool): Replace an existing sheet. Defaults to False.
    filename (str): The filename to write. Defaults to "distributed.xlsx".

    Returns:
    pl.Path: The file written.

    Raises:
    FileExistsError: If the sheet exists and ``overwrite`` is False.
    """
    folder = pl.Path(folder)
    target = folder / filename

    if target.exists() and not overwrite:
        raise FileExistsError(
            f"{target} already exists. It records who is marking what, so it "
            "is not replaced by accident. Pass overwrite=True to replace it."
        )

    folder.mkdir(parents=True, exist_ok=True)
    # index=False on every path. The old overwrite branch omitted it and
    # added a phantom index column to the replaced file.
    d.to_excel(target, index=False)
    return target
