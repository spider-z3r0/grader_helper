#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Fold a folder of the module leader's group sheets into one table.

A Brightspace-managed group assessment needs none of this: the groups were
made in Brightspace, so they come down **in the class list** as a group
column and ``import_brightspace_classlist(group=True)`` is the whole story.

A leader-managed one does not have that. The groups live in sheets the
leader made -- one per team, or one workbook with a tab per team -- and
nothing downstream can use them in that shape, because allocation needs one
row per student saying which group they are in. So this is a fold, the same
shape as :func:`collect_quiz_marks`: many files in, one two-column frame
out.

    groups/
        Team 1.xlsx       a sheet of student ids
        Team 2.xlsx
        Team 3.xlsx
                      ->  Student ID | Group
                          23304301   | Team 1
                          23304302   | Team 1
                          ...

**The group name comes from the sheet, not from a column, unless the sheet
says otherwise.** A file called ``Team 1.xlsx`` is Team 1; a tab called
``Team 1`` in a combined workbook is Team 1. A group column inside the sheet
wins over both, because a leader who wrote one meant it.

House convention::

    import pathlib as pl        # pl is pathlib
    import polars as pr         # pr is polars
"""

import warnings

from ..dependencies import pd, pl
from .import_brightspace_classlist import (
    MissingGroupError,
    _check_for_missing_groups,
    _expand_solo_groups,
    _normalise_column,
    find_group_column,
)

#: Column names accepted as "the student id", compared case-insensitively
#: with spaces and underscores collapsed. A leader's own sheet is a hand-made
#: thing and may call the column almost anything; ``Username`` and
#: ``OrgDefinedId`` are here because a leader who built the sheets by pasting
#: from a Brightspace export will have those headings.
STUDENT_ID_ALIASES = (
    "studentid",
    "studentnumber",
    "id",
    "idnumber",
    "username",
    "orgdefinedid",
    "student",
)

#: Sheet formats a group sheet may be written in.
GROUP_SHEET_SUFFIXES = (".csv", ".xlsx", ".xlsm")


class ConflictingGroupsError(ValueError):
    """Raised when the group sheets put one student in two groups.

    Its own type, and never resolved by taking the last one seen. A student
    in two groups is a mistake in the sheets -- usually a copy-paste when the
    teams were rearranged -- and picking one silently marks that student's
    work with a team they were not in.
    """


def _find_student_id_column(columns, id_column: str | None = None) -> str:
    """Return the column in `columns` holding the student id."""
    lookup = {_normalise_column(c): c for c in columns}

    if id_column is not None:
        found = lookup.get(_normalise_column(id_column))
        if found is not None:
            return found
        raise ValueError(
            f"No column named {id_column!r} in the group sheet. "
            f"Columns present: {list(columns)}"
        )

    for alias in STUDENT_ID_ALIASES:
        if alias in lookup:
            return lookup[alias]

    raise ValueError(
        "Could not find a student id column in the group sheet. Looked for "
        f"any of {list(STUDENT_ID_ALIASES)} (ignoring case, spaces and "
        f"underscores). Columns present: {list(columns)}. Either head the "
        "column 'Student ID' or pass id_column='<your column>'."
    )


def _sheets_in(path: pl.Path) -> dict[str, pd.DataFrame]:
    """Every sheet in one file, keyed by the group name it implies.

    A single-sheet file is named by its stem: a workbook saved from a
    template is called ``Sheet1`` inside however carefully the file itself
    was named. A workbook with several sheets is named by its tabs, because
    that is a leader who put every team in one file.
    """
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            return {path.stem: pd.read_csv(path, dtype=str)}
        except pd.errors.EmptyDataError:
            # A team with nobody in it yet. Not a reason to refuse to read
            # the other teams; if they are *all* empty, the caller says so.
            return {path.stem: pd.DataFrame()}

    sheets = pd.read_excel(path, sheet_name=None, dtype=str)
    if len(sheets) == 1:
        return {path.stem: next(iter(sheets.values()))}
    return sheets


def _group_sheet_files(source: pl.Path) -> list[pl.Path]:
    """The group sheets under `source`, whether it is a file or a folder."""
    source = pl.Path(source)
    if not source.exists():
        raise FileNotFoundError(
            f"No group sheets at {source}. This should be the folder holding "
            "your own group sheets -- one per team, or one workbook with a "
            "tab per team."
        )
    if source.is_file():
        return [source]

    found = sorted(
        p
        for p in source.iterdir()
        if p.is_file()
        and p.suffix.lower() in GROUP_SHEET_SUFFIXES
        # Excel's lock files for an open workbook. Reading one raises, and
        # "someone has the sheet open" is not a data problem.
        and not p.name.startswith("~$")
    )
    if not found:
        raise ValueError(
            f"No group sheets in {source}. Looked for "
            f"{list(GROUP_SHEET_SUFFIXES)} files. Put one sheet per team in "
            "there, named for the team, or one workbook with a tab per team."
        )
    return found


def _read_one(
    frame: pd.DataFrame,
    implied_group: str,
    where: str,
    id_column: str | None,
    group_column: str | None,
) -> pd.DataFrame:
    """One sheet as Student ID / Group rows."""
    if not len(frame.columns):
        return pd.DataFrame(columns=["Student ID", "Group"])

    try:
        ids = _find_student_id_column(frame.columns, id_column)
    except ValueError as exc:
        raise ValueError(f"{where}: {exc}") from exc

    # A group column inside the sheet wins over the sheet's own name: a
    # leader who wrote one meant it, and it is the only way to express two
    # teams in one tab.
    try:
        groups = find_group_column(frame.columns, group_column)
    except ValueError:
        if group_column is not None:
            raise
        groups = None

    out = pd.DataFrame(
        {
            "Student ID": frame[ids].astype(str).str.strip().str.replace("#", ""),
            "Group": (
                frame[groups].astype(str).str.strip()
                if groups is not None
                else implied_group.strip()
            ),
        }
    )
    # Hand-made sheets carry trailing blank rows and the odd blank line
    # between teams. Those are not students.
    blank = out["Student ID"].isin(["", "nan", "None"]) | out["Student ID"].isna()
    return out.loc[~blank].reset_index(drop=True)


def collect_group_membership(
    source: pl.Path,
    *,
    id_column: str | None = None,
    group_column: str | None = None,
) -> pd.DataFrame:
    """
    Collect the module leader's group sheets into one student-id-to-group table.

    Parameters
    ----------
    source : pathlib.Path
        The folder of group sheets, or a single file. One sheet per team
        named for the team, or one workbook with a tab per team; either way
        a group column inside a sheet overrides the name.
    id_column : str, optional
        The column holding the student id, when it is not one of the names
        recognised automatically -- see ``STUDENT_ID_ALIASES``.
    group_column : str, optional
        The column holding the group, for sheets that carry one. Given
        explicitly, every sheet must have it.

    Returns
    -------
    pandas DataFrame
        Two columns, ``Student ID`` and ``Group``, one row per student.
        Student ids are text, with any leading ``#`` stripped, so the frame
        merges against the class list.

    Raises
    ------
    FileNotFoundError
        If ``source`` does not exist.
    ValueError
        If there are no group sheets, or a sheet has no student id column.
    ConflictingGroupsError
        If a student appears in two different groups.

    Examples
    --------
    ::

        import pathlib as pl        # pl is pathlib

        membership = collect_group_membership(pl.Path("assessments/cw1/groups"))

    Notes
    -----
    A student listed twice in the *same* group is one student, and the
    duplicate row is dropped. A student listed in two *different* groups is
    a mistake in the sheets and raises.
    """
    files = _group_sheet_files(source)

    frames = []
    for path in files:
        for sheet_name, frame in _sheets_in(path).items():
            where = (
                f"{path.name}"
                if sheet_name == path.stem
                else f"{path.name} [{sheet_name}]"
            )
            frames.append(_read_one(frame, sheet_name, where, id_column, group_column))

    membership = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["Student ID", "Group"]
    )
    if membership.empty:
        raise ValueError(
            f"The group sheets in {source} name no students. Every sheet was "
            "read, and every one of them was empty."
        )

    # Same student, same group, listed twice: one student.
    membership = membership.drop_duplicates(ignore_index=True)

    counts = membership.groupby("Student ID")["Group"].nunique()
    conflicted = sorted(counts[counts > 1].index)
    if conflicted:
        listed = "\n".join(
            f"  {sid}: "
            + ", ".join(
                sorted(membership.loc[membership["Student ID"] == sid, "Group"])
            )
            for sid in conflicted[:20]
        )
        if len(conflicted) > 20:
            listed += f"\n  ... and {len(conflicted) - 20} more"
        raise ConflictingGroupsError(
            f"{len(conflicted)} student(s) are in more than one group:\n"
            + listed
            + "\n\nWhich group a student is in decides who marks their work, "
            "so this is not something to resolve by taking the last one "
            "seen. Fix the sheets."
        )

    return membership.sort_values(["Group", "Student ID"], ignore_index=True)


def attach_group_membership(
    class_list: pd.DataFrame,
    membership: pd.DataFrame,
) -> pd.DataFrame:
    """
    Put a ``Group`` column on a class list, from collected group membership.

    The point of this function is that afterwards there is **one shape**: a
    class list with a ``Group`` column, exactly what
    ``import_brightspace_classlist(group=True)`` returns for a
    Brightspace-managed assessment. Everything downstream -- allocation
    especially -- then stops caring which kind of group assessment it is.

    The same two rules apply as on a Brightspace group class list, and for
    the same reasons: a student with no group cannot be allocated, and a
    student marked ``SOLO`` gets a group of their own rather than being
    lumped in with every other solo student.

    Parameters
    ----------
    class_list : pandas DataFrame
        As ``import_brightspace_classlist`` returns it. **This decides the
        cohort.**
    membership : pandas DataFrame
        ``Student ID`` and ``Group``, as ``collect_group_membership``
        returns it.

    Returns
    -------
    pandas DataFrame
        A copy of the class list with ``Group`` filled in.

    Raises
    ------
    MissingGroupError
        If any enrolled student is in no group, naming every one of them.

    Warns
    -----
    UserWarning
        If the sheets name students who are not in the class list. Usually a
        mistyped id -- which shows up twice, once as a student with no group
        and once here.
    """
    needed = ["Student ID", "First Name", "Last Name"]
    absent = [c for c in needed if c not in class_list.columns]
    if absent:
        raise ValueError(
            f"The class list is missing {absent}. Columns present: "
            f"{list(class_list.columns)}. import_brightspace_classlist "
            "produces the right shape."
        )
    for column in ("Student ID", "Group"):
        if column not in membership.columns:
            raise ValueError(
                f"The group membership has no {column!r} column. Columns "
                f"present: {list(membership.columns)}. "
                "collect_group_membership produces the right shape."
            )

    enrolled = set(class_list["Student ID"].astype(str))
    strangers = sorted(set(membership["Student ID"].astype(str)) - enrolled)
    if strangers:
        warnings.warn(
            f"The group sheets name {len(strangers)} student(s) who are not "
            f"in the class list: {strangers[:20]}"
            + (" ..." if len(strangers) > 20 else "")
            + ". They have been ignored. A mistyped id shows up here and "
            "again as a student with no group, so check those first.",
            stacklevel=2,
        )

    out = class_list.copy()
    out["Student ID"] = out["Student ID"].astype(str)
    lookup = dict(
        zip(membership["Student ID"].astype(str), membership["Group"].astype(str))
    )
    # Insert Group where the Brightspace group class list has it -- after the
    # names, before Score -- so the two kinds really do come out the same.
    group = out["Student ID"].map(lookup)
    if "Group" in out.columns:
        out["Group"] = group
    elif "Score" in out.columns:
        out.insert(out.columns.get_loc("Score"), "Group", group)
    else:
        out["Group"] = group

    _check_for_missing_groups(out)
    return _expand_solo_groups(out)


__all__ = [
    "ConflictingGroupsError",
    "MissingGroupError",
    "STUDENT_ID_ALIASES",
    "attach_group_membership",
    "collect_group_membership",
]
