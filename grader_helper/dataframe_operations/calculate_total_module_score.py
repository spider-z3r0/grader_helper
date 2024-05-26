#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ..dependencies import pd


def calculate_total_module_score(df: pd.DataFrame) -> None | str:
    """
    Calculate the total module score of a DataFrame

    Args:
    df (pd.DataFrame): DataFrame containing the columns to calculate the total module score

    Returns:
    None | str: None if the operation was successful, an error message if the operation failed
    """

    # Check if the DataFrame is empty
    if df.empty:
        return "DataFrame is empty"

    # Check for required columns
    required_columns = ["Student ID", "Name"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        return f"DataFrame is missing columns: {', '.join(missing_columns)}"

    # Check for at least one coursework column with '(100)' in its name
    coursework_columns = [
        col for col in df.columns if "Coursework" in col and "(100)" in col
    ]
    if not coursework_columns:
        return "DataFrame is missing a coursework column"

    # Calculate the total module score
    if len(coursework_columns) == 1:
        df["Total % Grade"] = df[coursework_columns[0]]
    else:
        try:
            weighted_cols = [
                col for col in df.columns if "Coursework" in col and "100" not in col
            ]
            df["Total % Grade"] = df[weighted_cols].sum(axis=1)
        except KeyError:
            return (
                "It looks like there is something wrong with the column names in the DataFrame. "
                "This may be because the column names are not in the required format, or because you have not yet used the "
                "calculate_weighted_score function to calculate the weighted scores of the coursework columns (which is required "
                "to calculate the total module score). Check your dataframe by running something like `df.head()` or `print(df.columns)`."
            )
    return None
