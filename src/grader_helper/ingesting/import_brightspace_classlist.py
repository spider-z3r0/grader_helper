#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Utilities for reading Brightspace classlist CSV exports.

The module exposes :func:`import_brightspace_classlist`, which converts a
Brightspace CSV export into a tidy :class:`pandas.DataFrame` of student
identifiers and assignment grades.
"""

import pandas as pd
import pathlib as pl


def main():
    # Test the import_brightspace_classlist function
    print("write a test for this Kev")


def import_brightspace_classlist(file: pl.Path, assignment_name: str) -> pd.DataFrame:
    """
    Imports a Brightspace classlist from a CSV file.

    Parameters
    ----------
    file : pathlib.Path
        The path to the CSV file containing the Brightspace classlist.
    assignment_name : str
        The name of the assignment.

    Returns
    -------
    pandas DataFrame
        The Brightspace classlist.
    """
    if file.suffix != ".csv":
        raise ValueError("File must be a CSV file.")

    try:
        classlist_df = pd.read_csv(file)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Classlist CSV file not found: {file}") from exc
    except pd.errors.ParserError as exc:
        raise pd.errors.ParserError(
            f"Could not parse Brightspace classlist CSV: {file}"
        ) from exc

    classlist_df = classlist_df[
        ["Username", "Last Name", "First Name", assignment_name]
    ]

    # Clean the 'Username' column by renaming to 'Student ID' and dropping the '#' character
    classlist_df.rename(columns={"Username": "Student ID"}, inplace=True)
    classlist_df["Student ID"] = classlist_df["Student ID"].str.replace("#", "")

    # Return the processed classlist DataFrame
    return classlist_df


if __name__ == "__main__":
    main()
