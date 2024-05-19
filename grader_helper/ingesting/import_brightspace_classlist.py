#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
    # Check if the file is a CSV file
    try:
        if file.suffix != ".csv":
            raise ValueError("File must be a CSV file.")

        # Read the CSV file and select the needed columns
        classlist_df = pd.read_csv(file)
        classlist_df = classlist_df[
            ["Username", "Last Name", "First Name", assignment_name]
        ]

        # Clean the 'Username' column by renaming to 'Student ID' and dropping the '#' character
        classlist_df.rename(columns={"Username": "Student ID"}, inplace=True)
        classlist_df["Student ID"] = classlist_df["Student ID"].str.replace("#", "")

        # Return the processed classlist DataFrame
        return classlist_df

    except Exception as e:
        print(f"Error occurred while importing Brightspace classlist: {e}")
        return None


if __name__ == "__main__":
    main()
