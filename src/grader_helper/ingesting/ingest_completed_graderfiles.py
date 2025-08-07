#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Combine completed grader files into a single DataFrame.

The :func:`ingest_completed_graderfiles` function reads individual grader
spreadsheets (CSV or Excel) and concatenates them, optionally writing the merged
result back to disk.
"""

import logging

from ..dependencies import pd, pl

logger = logging.getLogger(__name__)


def ingest_completed_graderfiles(
    folder: pl.Path, grader: list[str], type: str = "csv", save: bool = False
) -> pd.DataFrame:
    """Ingest and combine individual grader spreadsheets.

    Args:
        folder (Path): Directory containing grader files.
        grader (list[str]): List of grader identifiers.
        type (str): File type of grader files (``"excel"`` or ``"csv"``).
        save (bool): When ``True``, write the concatenated DataFrame to disk.

    Returns:
        pd.DataFrame: Combined DataFrame with shape ``(n, m)`` where ``n`` is the
            total number of rows across all successfully ingested grader files and
            ``m`` is the number of columns in those files.

    Raises:
        ValueError: If provided arguments are of incorrect type or ``type`` is not
            ``"excel"`` or ``"csv"``.
        FileNotFoundError: If a grader file cannot be located.
        pd.errors.ParserError: If a grader file cannot be parsed. Check that the
            file is a valid CSV/Excel document with the expected structure.
        pd.errors.MergeError: If the DataFrames cannot be concatenated, typically
            due to mismatched columns.
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
        file_path = folder / (f"{g}.xlsx" if type == "excel" else f"{g}.csv")
        try:
            if type == "excel":
                df = pd.read_excel(file_path)
            else:
                df = pd.read_csv(file_path)
            dfs.append(df)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Expected file '{file_path}' for grader '{g}' not found. "
                "Verify the grader name and that the file exists with the correct extension."
            ) from e
        except pd.errors.ParserError as e:  # pandas parsing errors
            raise pd.errors.ParserError(
                f"Could not parse '{file_path}'. Ensure it is a valid {type.upper()} file "
                "with the expected structure."
            ) from e

    # try to concatenate the DataFrames
    try:
        df = pd.concat(dfs, ignore_index=True)
    except pd.errors.MergeError as e:
        raise pd.errors.MergeError(
            f"Error concatenating DataFrames. Ensure files have compatible structures. {e}"
        ) from e

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
            logger.info("Operation cancelled. Existing file was not overwritten.")

    return df
