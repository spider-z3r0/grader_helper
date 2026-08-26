#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import pathlib as pl
import numpy as np


def main():
    # Test the import_brightspace_classlist function
    print("write a test for this Kev")


#: Column names accepted as "the group column", compared case-insensitively
#: with spaces and underscores collapsed. A group column reaches the class
#: list either from Brightspace's own group function, which exports it as
#: "Group Name", or from the module leader adding it by hand -- in which case
#: it could be called almost anything. Pass `group_column=` for a name not
#: listed here.
GROUP_COLUMN_ALIASES = (
    "groupname",
    "group",
    "groups",
    "team",
    "teams",
    "teamname",
    "grouping",
)


def _normalise_column(name: str) -> str:
    return str(name).strip().lower().replace(" ", "").replace("_", "")


def find_group_column(columns, group_column: str | None = None) -> str:
    """Return the column in `columns` that holds the group/team name.

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
    lookup = {_normalise_column(c): c for c in columns}

    if group_column is not None:
        found = lookup.get(_normalise_column(group_column))
        if found is not None:
            return found
        raise ValueError(
            f"No column named {group_column!r} in the class list. "
            f"Columns present: {list(columns)}"
        )

    for alias in GROUP_COLUMN_ALIASES:
        if alias in lookup:
            return lookup[alias]

    raise ValueError(
        "Could not find a group column in the class list. Looked for any of "
        f"{list(GROUP_COLUMN_ALIASES)} (ignoring case, spaces and "
        f"underscores). Columns present: {list(columns)}. "
        "Either export the class list using Brightspace's group function, "
        "which adds a 'Group Name' column, add one yourself, or pass "
        "group_column='<your column>'."
    )


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
        The name of the column holding the group. Only needed when it is not
        one of the names recognised automatically -- see
        GROUP_COLUMN_ALIASES.

    Returns
    -------
    pandas DataFrame
        The Brightspace classlist.
    """
    # Check if the file is a CSV file
    print('Testing the ingestion')
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
            found = find_group_column(classlist_df.columns, group_column)
            classlist_df = classlist_df.rename(columns={found: 'Group'})
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


        if normalise:
            classlist_df.columns = [i.lower().replace(' ', '_')
                                    for i in classlist_df.columns]

        # Return the processed classlist DataFrame
        return classlist_df

    except FileNotFoundError:
        print(f"Can not find file at {file.absolute()}")
        return None
    except Exception as e:
        print(f"Error occurred while importing Brightspace classlist: {e}")
        return None


if __name__ == "__main__":
    main()
