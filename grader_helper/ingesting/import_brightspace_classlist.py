#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import pathlib as pl
import numpy as np

def main():
    # Test the import_brightspace_classlist function
    print("write a test for this Kev")


#: The two names a group column may have, compared case-insensitively with
#: spaces and underscores collapsed -- so ``Group``, ``group`` and ``GROUP``
#: are all the group column, and ``Team`` likewise.
#:
#: **Exactly these two, and no combination of them or of anything else.**
#: A sheet carries several columns that read like the group without being it,
#: and the resemblance is the danger: a group code is produced elsewhere for
#: something else and only looks like the group because the group label is
#: built out of it -- ``2A_1`` contains ``2A``. Allocating on the wrong one
#: puts students who are not in a team together in front of one grader,
#: under team names that read perfectly.
#:
#: Anything else can still be used, by naming it: ``group_column=`` takes any
#: column in the sheet. What is restricted is what gets picked *for* you.
#: Brightspace's own group export heads the column ``Group Name``, which is
#: a combination and so is not found automatically -- name it, or rename it
#: to ``Group``.
GROUP_COLUMN_ALIASES = (
    "group",
    "team",
)


#: Values in the group column meaning "this student is working alone".
#: Matched case-insensitively. Each such student becomes their own group --
#: see _expand_solo_groups for why that matters.
SOLO_ALIASES = ("solo", "individual", "alone", "on their own")

#: Prefix given to the group of a student working alone.
SOLO_PREFIX = "SOLO"


class AmbiguousGroupError(ValueError):
    """Raised when several columns could be the group and they disagree.

    Its own type, and deliberately not resolved by alias order. Two columns
    that cut the cohort differently are two different answers to "who is in
    a team with whom", and the wrong one is silent: two teams reach one
    grader as one team, with one mark between them.
    """


class MissingGroupError(ValueError):
    """Raised when a group class list has students with no group.

    Deliberately its own type, and deliberately allowed to propagate rather
    than being folded into the generic "could not import" path, because it
    is a data problem the module leader must resolve before any marking can
    be allocated -- not a malformed file.
    """


def _normalise_column(name: str) -> str:
    return str(name).strip().lower().replace(" ", "").replace("_", "")


def _is_blank(value) -> bool:
    return pd.isna(value) or not str(value).strip()


def _check_for_missing_groups(df: pd.DataFrame) -> None:
    """Raise if any student has no group, naming every one of them."""
    blank = df[df["Group"].map(_is_blank)]
    if blank.empty:
        return

    listed = [
        f"  {row['Student ID']}  {row['First Name']} {row['Last Name']}"
        for _, row in blank.head(20).iterrows()
    ]
    if len(blank) > 20:
        listed.append(f"  ... and {len(blank) - 20} more")

    raise MissingGroupError(
        f"{len(blank)} student(s) in the class list have no group:\n"
        + "\n".join(listed)
        + "\n\nEvery student must be in a group before marking can be "
        "allocated, because a student with no group is silently treated as a "
        "group of one and their work is marked apart from their team.\n"
        "Either enter the group number in the class list, or -- if the "
        f"student really is working alone -- put '{SOLO_PREFIX}' in the group "
        "column and they will be given a group of their own."
    )


def _expand_solo_groups(df: pd.DataFrame) -> pd.DataFrame:
    """Give every student marked SOLO a group unique to them.

    Grader allocation gives one grader per distinct group value, so leaving
    every solo student on the literal string 'SOLO' would treat them as a
    single team and send them all to the same grader. Appending the student
    ID keeps the meaning ("this person worked alone") while making each one
    genuinely their own group.
    """
    solo = df["Group"].astype(str).str.strip().str.lower().isin(SOLO_ALIASES)
    df.loc[solo, "Group"] = [
        f"{SOLO_PREFIX} ({sid})" for sid in df.loc[solo, "Student ID"]
    ]
    return df


def _named(columns, group_column: str) -> str:
    """One explicitly named column, matched leniently."""
    lookup = {_normalise_column(c): c for c in columns}
    found = lookup.get(_normalise_column(group_column))
    if found is not None:
        return found
    raise ValueError(
        f"No column named {group_column!r} in the class list. "
        f"Columns present: {list(columns)}"
    )


def _candidates(columns) -> list[str]:
    """Every column that could be the group, in alias order."""
    lookup = {_normalise_column(c): c for c in columns}
    return [lookup[alias] for alias in GROUP_COLUMN_ALIASES if alias in lookup]


def find_group_column(columns, group_column: str | None = None) -> str:
    """Return the column in `columns` that holds the group/team name.

    Names only. Where the frame is to hand, prefer
    :func:`resolve_group_column`, which can also tell two candidate columns
    apart -- something no amount of looking at names can do.

    Parameters
    ----------
    columns
        The class list's column names.
    group_column
        An explicit name to use. Matched leniently, so capitalisation and
        spacing do not have to be exact.

    Raises
    ------
    ValueError
        If no candidate is found. The message names the columns that *are*
        present, so the user can see what to rename.
    """
    if group_column is not None:
        return _named(columns, group_column)

    found = _candidates(columns)
    if found:
        return found[0]

    raise ValueError(
        "Could not find a group column. It has to be called "
        f"{' or '.join(repr(a.title()) for a in GROUP_COLUMN_ALIASES)} "
        "(ignoring case, spaces and underscores), and nothing else is picked "
        f"automatically. Columns present: {list(columns)}.\n"
        "Either rename the column -- Brightspace's group function exports it "
        "as 'Group Name', which is a combination and so is not one of the "
        "two -- or pass group_column='<your column>', which takes any of "
        "them."
    )


def _partition_size(frame: pd.DataFrame, columns: list[str]) -> int:
    """How many groups these columns cut the frame into."""
    return frame.groupby(columns, dropna=False).ngroups


def resolve_group_column(
    frame: pd.DataFrame, group_column: str | None = None
) -> str:
    """Decide which column holds the group -- reading the data.

    ``find_group_column`` sees only names, and names are not enough. A
    module leader's own group sheet routinely carries both:

        Name   Student Id   Team   Cohort   Group
        ...    12345678     1      2A       2A_1
        ...    12345681     1      2B       2B_1

    ``Team`` and ``Group`` are both the group column by name, and **they are
    not the same partition**: on ``Team`` those two students are one team, on
    ``Group`` they are two. Picking by alias order would get the right answer
    here only because "group" happens to precede "team" in a tuple, and the
    wrong one is silent -- two teams marked as one, by one grader, at one
    mark.

    So when the two disagree, this refuses and says to name one. When they
    agree it does not matter which is used, and it does not ask.

    Parameters
    ----------
    frame
        The class list or group sheet. Read, not modified.
    group_column
        An explicit answer: the name of any column in the frame. Only
        automatic detection is restricted to ``Group`` and ``Team``.

    Returns
    -------
    str
        The column holding the group. Hand it to :func:`group_key`.

    Raises
    ------
    ValueError
        If a named column is absent, or none is found at all.
    AmbiguousGroupError
        If both ``Group`` and ``Team`` are there and they disagree about who
        is in a team with whom.
    """
    if group_column is not None:
        return _named(frame.columns, group_column)

    found = _candidates(frame.columns)
    if not found:
        # Same message, and the same advice, as the names-only path.
        return find_group_column(frame.columns)
    if len(found) == 1:
        return found[0]

    # Both are here. They only matter if they disagree: two columns cut the
    # frame the same way iff their common refinement is no finer than either.
    together = _partition_size(frame, found)
    sizes = {column: _partition_size(frame, [column]) for column in found}
    if all(size == together for size in sizes.values()):
        return found[0]

    listed = "\n".join(
        f"  {column!r} makes {size} group(s)" for column, size in sizes.items()
    )
    finest = max(sizes, key=sizes.get)
    raise AmbiguousGroupError(
        "Both columns could be the group, and they disagree:\n"
        + listed
        + f"\n  together they make {together}\n\n"
        "Which one decides who is in a team with whom is not something to "
        "guess: the wrong choice puts two teams in front of one grader as "
        "one team, with one mark between them, and nothing about the result "
        "looks wrong. Say which you mean:\n"
        f"  group_column={finest!r}\n\n"
        f"Columns here: {list(frame.columns)}\n"
        "For an assessment, set `group_column` in module.toml and it is "
        "answered once."
    )


def group_key(frame: pd.DataFrame, column: str) -> pd.Series:
    """The group label for each row, as text, with blanks left blank.

    Not simply ``frame[column].astype(str)``: that turns a missing group into
    the string ``"nan"``, which is not blank, so the missing-group refusal
    never fires and every student without a group is allocated together as a
    team called ``nan`` -- one grader, one mark, no error anywhere. A student
    with no group has to stay visibly without one.
    """
    values = frame[column]
    blank = values.isna() | values.astype(str).str.strip().eq("")
    return values.astype(str).str.strip().mask(blank)


def import_brightspace_classlist(
    file: pl.Path,
    group: bool = False,
    normalise: bool = False,
    group_column: str | None = None,
) -> pd.DataFrame | None:
    """
    Imports a Brightspace classlist from a CSV or xlsx
    file.

    Parameters
    ----------
    file : pathlib.Path
        The path to the CSV or xlsx file containing the Brightspace classlist.
    group : bool
        If True, keep the group/team column, renamed to 'Group'.
    normalise : bool
        If True, lowercase the column names and replace spaces with
        underscores.
    group_column : str | None
        The column holding the group. Only needed when it is not called
        `Group` or `Team` -- see GROUP_COLUMN_ALIASES -- or when both are
        there and they disagree.

    Returns
    -------
    pandas DataFrame
        The Brightspace classlist.
    """
    # Check if the file is a CSV file
    try:
        match file.suffix:
            case '.csv':
                classlist_df = pd.read_csv(file)
            case '.xlsx':
                classlist_df = pd.read_excel(file)
            case _:
                raise ValueError("File must be a CSV, or xlsx file.")

        
        # Read the CSV file and select the needed columns
        # depending on the filetype

        # rename the 'Username column' to 'Student ID'
        classlist_df.rename(columns={"Username": "Student ID"}, inplace=True)
        # add the "Score" column
        classlist_df["Score"] = ""
        if group:
            # resolve_group_column, not find_group_column: it can see the
            # data, so it can tell two candidate columns apart -- and refuse
            # when they disagree -- which names alone cannot.
            found = resolve_group_column(classlist_df, group_column)
            classlist_df["Group"] = group_key(classlist_df, found)
            classlist_df = classlist_df[
                ["Student ID", "Last Name", "First Name", "Group", "Score"]]
        else:
            classlist_df = classlist_df[
                ["Student ID", "Last Name", "First Name", "Score"]]

        # Brightspace writes the username as "#56170559". Every downstream
        # consumer matches on the bare digits parsed out of a submission
        # folder name, so the '#' has to go in both modes -- the group branch
        # previously skipped this and nothing matched.
        classlist_df["Student ID"] = classlist_df["Student ID"].str.replace(
            "#", "")

        if group:
            _check_for_missing_groups(classlist_df)
            classlist_df = _expand_solo_groups(classlist_df)


        if normalise:
            classlist_df.columns = [i.lower().replace(' ', '_')
                                    for i in classlist_df.columns]

        # Return the processed classlist DataFrame
        return classlist_df

    except (MissingGroupError, AmbiguousGroupError):
        # Data problems for the module leader to fix, not import failures.
        raise
    except FileNotFoundError:
        print(f"Can not find file at {file.absolute()}")
        return None
    except Exception as e:
        print(f"Error occurred while importing Brightspace classlist: {e}")
        return None


if __name__ == "__main__":
    main()
