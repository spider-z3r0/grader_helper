#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import pathlib as pl
import numpy as np


def main():
    # Test the import_brightspace_classlist function
    print("write a test for this Kev")


def import_brightspace_classlist(file: pl.Path, assignment_name: str | None = None, normalise: bool = False) -> pd.DataFrame | None:
    """
    Imports a Brightspace classlist from a CSV or xlsx
    file.

    Parameters
    ----------
    file : pathlib.Path
        The path to the CSV or xlsx file containing the Brightspace classlist.
    assignment_name : str
        The name of the assignment.

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

        match assignment_name:
            case str():
                if 'Group' in classlist_df.columns:
                    classlist_df = classlist_df.rename({'Group Name':'Group'}, axis=1)
                    classlist_df = classlist_df[
                        ["Username", "Last Name", "First Name", "Group", assignment_name]]
                else:
                    classlist_df = classlist_df[
                        ["Username", "Last Name", "First Name",  assignment_name]]
            case None:
                classlist_df['Score'] = np.nan
                if 'Group' in classlist_df.columns:
                    classlist_df = classlist_df.rename({'Group Name':'Group'}, axis=1)
                    classlist_df = classlist_df[
                        ["Username", "Last Name", "First Name", "Group", "Score"]]
                else:
                    classlist_df = classlist_df[
                        ["Username", "Last Name", "First Name",  "Score"]]

        # Clean the 'Username' column by renaming to 'Student ID' and dropping the '#' character
        classlist_df.rename(columns={"Username": "Student ID"}, inplace=True)
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
