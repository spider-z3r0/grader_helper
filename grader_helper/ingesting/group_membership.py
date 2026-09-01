#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Who is in which group, when Brightspace is not the one who knows.

A module leader running group work either lets Brightspace manage the groups
-- in which case the class list export carries a group column and
:func:`~grader_helper.import_brightspace_classlist` with ``group=True`` is
the whole story -- or keeps the membership themselves in a spreadsheet.
This is the second case, and it exists so that the rest of the package
cannot tell the difference: both routes end in a class list with a ``Group``
column, checked the same way.

    >>> import pathlib as pl
    >>> from grader_helper import attach_groups, import_brightspace_classlist
    >>> students = import_brightspace_classlist(module.classlist_path)
    >>> grouped = attach_groups(students, module.groups_path)
    >>> assign_graders_groups(grouped, ["KOM", "SOB"])

**A student with no group is refused**, by the same check the Brightspace
route uses and for the same reason: a missing group is silently a group of
one, and that student's work is then marked apart from their team by a
grader who never saw the rest of it. A student who genuinely works alone is
written as ``SOLO`` and gets a group of their own.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl
import re

import pandas as pd

from .import_brightspace_classlist import (
    _check_for_missing_groups,
    _expand_solo_groups,
    find_group_column,
)

#: Column names accepted for the student id, ignoring case and punctuation.
ID_COLUMN_ALIASES = (
    "studentid",
    "username",
    "id",
    "studentnumber",
    "student",
)


def _normalise(name: str) -> str:
    return str(name).lower().replace(" ", "").replace("_", "")


def _find_id_column(columns, id_column: str | None = None) -> str:
    """The column holding the student id, matched leniently."""
    lookup = {_normalise(c): c for c in columns}

    if id_column is not None:
        found = lookup.get(_normalise(id_column))
        if found is not None:
            return found
        raise ValueError(
            f"No column named {id_column!r} in the groups file. "
            f"Columns present: {list(columns)}"
        )

    for alias in ID_COLUMN_ALIASES:
        if alias in lookup:
            return lookup[alias]

    raise ValueError(
        "Could not find a student id column in the groups file. Looked for "
        f"any of {list(ID_COLUMN_ALIASES)} (ignoring case, spaces and "
        f"underscores). Columns present: {list(columns)}."
    )


#: "Group 3", "Team 03", "3" -- all the same group written three ways.
_NUMBERED_GROUP = re.compile(r"^(?:team|group)?\s*0*(\d+)$")


def group_key(label) -> str:
    """A group label reduced to something two spellings of it share.

    Necessary because the two ends disagree by construction. The class list
    says whatever the leader typed -- "Group 3", "Team 3", "3" -- while a
    mark comes back named for the feedback sheet, and `catch_grades` takes
    that name as the **last space-separated token of the filename**. A sheet
    distributed to `Group 3`'s folder is `Feedback sheet Group 3.xlsx`, so
    the mark arrives keyed `3`.

    A numbered group becomes its number, so leading zeros and the word in
    front stop mattering. Anything else is compared case- and
    space-insensitively, so "Team Alpha" still matches "team alpha".
    """
    text = str(label).strip().casefold()
    numbered = _NUMBERED_GROUP.match(text)
    return numbered.group(1) if numbered else " ".join(text.split())


def load_group_membership(
    path: pl.Path,
    group_column: str | None = None,
    id_column: str | None = None,
) -> pd.DataFrame:
    """
    Read a hand-maintained groups file.

    Args:
    path (pl.Path): A CSV or xlsx with a student id column and a group
        column, in any order and under any reasonable name.
    group_column (str | None): The group column's name, when it is not one
        this recognises.
    id_column (str | None): The id column's name, likewise.

    Returns:
    pd.DataFrame: Two columns, ``Student ID`` and ``Group``. Ids are text
        with any leading ``#`` removed, because Brightspace writes the
        username as ``#56170559`` and everything downstream matches on the
        bare digits.

    Raises:
    FileNotFoundError: If the file is not there.
    ValueError: If it is not a CSV or xlsx, or if either column cannot be
        found. The message names the columns that *are* present.

    Example:
        >>> load_group_membership(pl.Path("groups.csv"))
    """
    path = pl.Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"No groups file at {path}. This is the spreadsheet of who is in "
            "which group, named as `groups` under [paths] in module.toml."
        )

    match path.suffix.lower():
        case ".csv":
            frame = pd.read_csv(path, dtype=str)
        case ".xlsx" | ".xlsm":
            frame = pd.read_excel(path, dtype=str)
        case _:
            raise ValueError(
                f"{path.name} must be a CSV or xlsx file, not {path.suffix!r}."
            )

    ids = _find_id_column(frame.columns, id_column)
    groups = find_group_column(frame.columns, group_column)

    membership = frame[[ids, groups]].rename(
        columns={ids: "Student ID", groups: "Group"}
    )
    # Read as text throughout: an id read as a number loses its leading zero
    # and then matches no submission folder and no class list row.
    membership["Student ID"] = (
        membership["Student ID"].astype(str).str.replace("#", "", regex=False).str.strip()
    )
    return membership


def attach_groups(
    class_list: pd.DataFrame,
    membership: "pd.DataFrame | pl.Path | str",
    group_column: str | None = None,
    id_column: str | None = None,
) -> pd.DataFrame:
    """
    Put a ``Group`` column on a class list from a membership the leader keeps.

    Args:
    class_list (pd.DataFrame): The class list, as
        `import_brightspace_classlist` returns it.
    membership (pd.DataFrame | pl.Path | str): Either a loaded membership or
        the path to one, which is loaded for you.
    group_column (str | None): Passed to `load_group_membership`.
    id_column (str | None): Passed to `load_group_membership`.

    Returns:
    pd.DataFrame: The class list with a ``Group`` column, solo students
        expanded into groups of their own -- the same shape
        `import_brightspace_classlist(group=True)` returns, so nothing
        downstream can tell which route the groups came by.

    Raises:
    MissingGroupError: If any student on the class list has no group. Every
        one of them is named. A student with no group is silently a group of
        one, and would be marked apart from their team.
    ValueError: If the class list has no ``Student ID`` column.

    Example:
        >>> attach_groups(students, module.groups_path)
    """
    if "Student ID" not in class_list.columns:
        raise ValueError(
            "The class list has no 'Student ID' column, so groups cannot be "
            f"matched to it. Columns present: {list(class_list.columns)}."
        )

    if not isinstance(membership, pd.DataFrame):
        membership = load_group_membership(membership, group_column, id_column)

    # Left join: the class list decides who is on the module. A student in
    # the groups file who is not enrolled has left, or was mistyped, and
    # either way is not ours to add -- while a student on the module with no
    # group is a problem, and the check below names them.
    joined = class_list.merge(
        membership[["Student ID", "Group"]], on="Student ID", how="left"
    )
    _check_for_missing_groups(joined)
    return _expand_solo_groups(joined)


def spread_group_marks(
    group_marks: pd.DataFrame,
    class_list: pd.DataFrame,
    key_column: str = "Student ID",
    mark_column: str = "grade",
) -> pd.DataFrame:
    """
    Turn one mark per group into one mark per student.

    Where a group hands in a single piece of work there is a single feedback
    sheet, so the marks come back keyed by the group rather than by anybody
    in it. The departmental sheet has a row per student, so the group's mark
    has to reach every member.

    Args:
    group_marks (pd.DataFrame): Marks keyed by group. ``key_column`` is
        whichever column holds the group label -- `catch_grades` calls it
        ``Student ID`` whatever the folder was actually named, so that is
        the default.
    class_list (pd.DataFrame): The class list *with* its ``Group`` column,
        from `attach_groups` or `import_brightspace_classlist(group=True)`.
    key_column (str): The group label's column in ``group_marks``.
    mark_column (str): The mark's column in ``group_marks``.

    Returns:
    pd.DataFrame: ``Student ID`` and ``mark_column``, one row per student on
        the class list. A group with no mark leaves its members' marks blank
        rather than dropping them: a student missing from the sheet has no
        grade at all, which nobody notices, while a blank is visible.

    Raises:
    KeyError: If either frame is missing the column named.
    ValueError: If a mark is keyed to a group nobody is in -- a sheet was
        marked for a group that is not on this module, so either the
        membership or the folder name is wrong, and quietly dropping the
        mark would lose somebody's work.

    Example:
        >>> spread_group_marks(catch_grades(subs, "B12"), grouped)
    """
    for frame, name, needed in (
        (group_marks, "group_marks", (key_column, mark_column)),
        (class_list, "class_list", ("Student ID", "Group")),
    ):
        missing = [c for c in needed if c not in frame.columns]
        if missing:
            raise KeyError(
                f"{name} has no {missing} column. Columns present: "
                f"{list(frame.columns)}."
            )

    spread = class_list[["Student ID", "Group"]].copy()
    spread["_key"] = spread["Group"].map(group_key)

    # Two groups the module treats as different must not become one key, or
    # one group's mark would be handed to both.
    collapsed = (
        spread.groupby("_key")["Group"]
        .agg(lambda names: sorted(set(names)))
        .loc[lambda s: s.map(len) > 1]
    )
    if not collapsed.empty:
        raise ValueError(
            "These group names cannot be told apart once matched to a "
            f"feedback sheet: {list(collapsed)}. A sheet named for one of "
            "them would give its mark to both. Name them distinctly in the "
            "class list or the groups file."
        )

    marks = group_marks[[key_column, mark_column]].copy()
    marks["_key"] = marks[key_column].map(group_key)

    orphans = sorted(
        set(marks.loc[~marks["_key"].isin(spread["_key"]), key_column].astype(str))
    )
    if orphans:
        raise ValueError(
            f"These marks are for groups nobody on this module is in: "
            f"{orphans}. Groups on the module: "
            f"{sorted(set(class_list['Group'].astype(str)))}. Either the "
            "membership is wrong or the feedback sheet was named for "
            "something else -- dropping the marks quietly would lose "
            "somebody's work."
        )

    return spread.merge(marks[["_key", mark_column]], on="_key", how="left")[
        ["Student ID", mark_column]
    ]
