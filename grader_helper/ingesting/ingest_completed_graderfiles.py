#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Read the graders' completed workbooks back into one frame.

The defect worth knowing about is silent and destroys data. A student id is
a string of digits -- the whole package treats it that way, which is why
``import_brightspace_classlist`` strips the ``#`` and keeps the rest as text
-- but Excel and CSV both store it as a number, and pandas reads it back as
one::

    written:  ['23304308', '00123456']   object
    read:     [ 23304308 ,   123456 ]    int64

The leading zeros are gone, and merging the result against the class list
does not quietly mismatch, it raises: "You are trying to merge on object and
int64 columns". So the id columns are read as text, explicitly.
"""

import warnings

from ..dependencies import pd, pl

#: Columns read as text rather than numbers. A student id that goes through
#: int loses its leading zeros and stops matching the class list.
ID_COLUMNS: tuple[str, ...] = ("Student ID", "OrgDefinedId", "Username")

_SUFFIX = {"excel": "xlsx", "csv": "csv"}


def _columns_in(path: pl.Path, file_type: str) -> list[str]:
    """The file's header, read without the body."""
    if file_type == "excel":
        return list(pd.read_excel(path, nrows=0).columns)
    return list(pd.read_csv(path, nrows=0).columns)


def _read(path: pl.Path, file_type: str) -> pd.DataFrame:
    """Read one grader file, keeping id columns as text."""
    # Only name columns the file actually has: pandas raises on a dtype key
    # that is not there.
    as_text = {c: str for c in _columns_in(path, file_type) if c in ID_COLUMNS}
    if file_type == "excel":
        return pd.read_excel(path, dtype=as_text)
    return pd.read_csv(path, dtype=as_text)


def ingest_completed_graderfiles(
    folder: pl.Path,
    grader: list[str],
    file_type: str = "csv",
    save: bool = False,
    overwrite: bool = False,
    require_all: bool = True,
) -> pd.DataFrame:
    """
    Read each grader's completed file and concatenate them.

    Args:
    folder (pl.Path): Where the grader files are.
    grader (list[str]): The graders whose files to read.
    file_type (str): "excel" or "csv". Defaults to "csv".
    save (bool): Also write the combined frame to the same folder.
    overwrite (bool): Replace an existing combined file. Defaults to False.
    require_all (bool): Refuse if any grader's file is missing. Defaults to
        True -- a missing file means missing marks, which is not something to
        discover later.

    Returns:
    pd.DataFrame: Every grader's rows, concatenated.

    Raises:
    ValueError: On a bad argument, or if no grader file could be read.
    FileNotFoundError: If a grader's file is missing and ``require_all``.
    FileExistsError: If saving would replace a file and ``overwrite`` is False.

    Note:
        Student id columns are read as text. Left to pandas they come back as
        integers, which drops leading zeros and makes the result unmergeable
        with the class list.

        ``file_type`` was called ``type``, which shadowed the builtin.
    """
    folder = pl.Path(folder)

    if not isinstance(folder, pl.Path):
        raise ValueError("Folder must be a Path.")
    if not all(isinstance(i, str) for i in grader):
        raise ValueError("All elements in the list must be strings.")
    if not isinstance(file_type, str):
        raise ValueError("file_type must be a string.")
    if file_type not in _SUFFIX:
        raise ValueError("file_type must be either 'excel' or 'csv'.")
    if not isinstance(save, bool):
        raise ValueError("Save must be a boolean.")

    suffix = _SUFFIX[file_type]

    paths = {g: folder / f"{g}.{suffix}" for g in grader}
    missing = sorted(g for g, path in paths.items() if not path.exists())
    if missing and require_all:
        raise FileNotFoundError(
            f"No {suffix} file for: {', '.join(missing)} in {folder}. Missing "
            "files mean missing marks, so nothing has been read. Pass "
            "require_all=False to ingest the graders who have returned theirs."
        )
    if missing:
        warnings.warn(
            f"Ingesting without {', '.join(missing)} -- their marks are not "
            "in the result.",
            stacklevel=2,
        )

    frames = [_read(path, file_type) for g, path in paths.items() if g not in missing]
    if not frames:
        # pd.concat([]) raises ValueError, which the old code did not catch,
        # and then returned an unbound name.
        raise ValueError(
            f"No grader files were read from {folder}, so there is nothing to "
            f"concatenate. Expected {suffix} files named for each grader: "
            f"{', '.join(f'{g}.{suffix}' for g in grader)}."
        )

    df = pd.concat(frames, ignore_index=True)

    if save:
        target = folder / f"completed_grades.{suffix}"
        if target.exists() and not overwrite:
            raise FileExistsError(
                f"{target} already exists. Pass overwrite=True to replace it."
            )
        if file_type == "excel":
            df.to_excel(target, index=False)
        else:
            df.to_csv(target, index=False)

    return df
