#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Combine completed grader files into a single DataFrame.

The :func:`ingest_completed_graderfiles` function reads individual grader
spreadsheets (CSV or Excel) and concatenates them, optionally writing the merged
result back to disk.
"""

from ..dependencies import pd, pl


def ingest_completed_graderfiles(
    folder: pl.Path, grader: list[str], type: str = "csv", save: bool = False
) -> pd.DataFrame:
    """
    This imports the completed grader file for each grader and then concatenates them into a single DataFrame.

    Args:
    folder (Path): The folder where the grader files are saved.
    grader (list[str]): The list of graders.
    type (str): The type of grader file. This can be 'excel' or 'csv'. Default is 'csv'.
    save (bool): If True, save the concatenated DataFrame to the same foler and type.

    Returns:
    pd.DataFrame: The concatenated DataFrame.
    """

    # Check graders is a list of strings
    if not all(isinstance(i, str) for i in grader):
        raise ValueError("All elements in the list must be strings.")

    # Check type is a string
    if not isinstance(type, str):
        raise ValueError("Type must be a string.")

    # Check save is a boolean
    if not isinstance(save, bool):
        raise ValueError("Save must be a boolean.")

    # Check folder is a Path
    if not isinstance(folder, pl.Path):
        raise ValueError("Folder must be a Path.")

    # check that type is either 'excel' or 'csv'
    if type not in ["excel", "csv"]:
        raise ValueError("Type must be either 'excel' or 'csv'.")

    # try to create a list of DataFrames
    dfs = []
    for g in grader:
        try:
            if type == "excel":
                df = pd.read_excel(folder / f"{g}.xlsx")
            else:
                df = pd.read_csv(folder / f"{g}.csv")
            dfs.append(df)
        except FileNotFoundError:
            print(f"{g}.{type} not found.")
        # check for pandas errors
        except pd.errors.ParserError as e:
            print(
                f"Error reading {g}.{type}. {e}"
            )  # I know that this is too general, but I'm not sure what specific errors to expect

    # try to concatenate the DataFrames
    try:
        df = pd.concat(dfs, ignore_index=True)
    except pd.errors.MergeError as e:
        print(f"Error concatenating DataFrames. {e}")

    # save the concatenated DataFrame if save is True
    save_path = folder / f"completed_grades.{type}"
    if save and not save_path.exists():
        if type == "excel":
            df.to_excel(folder / "completed_grades.xlsx", index=False)
        else:
            df.to_csv(folder / "completed_grades.csv", index=False)
    elif save and save_path.exists():
        choice = input(
            f"{save_path} already exists. Do you want to overwrite it? (y/n): "
        )
        if choice.lower() == "y":
            if type == "excel":
                df.to_excel(folder / "completed_grades.xlsx", index=False)
            else:
                df.to_csv(folder / "completed_grades.csv", index=False)
        else:
            print("Operation cancelled.")

    return df
