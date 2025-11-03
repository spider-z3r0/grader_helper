#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import pathlib as pl
import numpy as np


def main():
    # Test the import_brightspace_classlist function
    print("write a test for this Kev")


def import_brightspace_classlist(file: pl.Path, group: bool = False, normalise: bool = False) -> pd.DataFrame | None:
    """
    Imports a Brightspace classlist from a CSV or xlsx
    file.

    Parameters
    ----------
    file : pathlib.Path
        The path to the CSV or xlsx file containing the Brightspace classlist.

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
            classlist_df = classlist_df.rename(columns={'Group Name':'Group'})
            classlist_df = classlist_df[
                ["Student ID", "Last Name", "First Name", "Group", "Score"]]
            # Clean the 'Username' column by renaming to 'Student ID' and dropping the '#' character
            classlist_df.rename(columns={"Username": "Student ID"}, inplace=True)
        else:
            classlist_df = classlist_df[
                ["Student ID", "Last Name", "First Name", "Score"]]
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
