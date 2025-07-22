#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ..dependencies import pd
from . import (
    calculate_total_module_score,
    make_letter_grade,
    check_for_weighted_columns,
    sort_order_columns,
)


def prepare_data_for_departmental_template(
    df: pd.DataFrame, fail_threshold: int = 35
) -> pd.DataFrame:
    """
    Uses the other dataframe operations to prepare the data for the departmental template.
    This includes calculating the weighted scores, total module score, and letter grades.

    Args:
    df (pd.DataFrame): DataFrame containing the columns to prepare for the departmental template

    Returns:
    pd.DataFrame: DataFrame with the columns prepared for the departmental template

    Note:
    This function does not save the DataFrame to a file, it only prepares the data for the departmental template.
    It requires that you have already brought the data from each piece of coursework (assignments, exams, etc.) into a single DataFrame,
    and that you have already changed the name of the columns to the required format (e.g. "Coursework 1 (100)", "Coursework 2 (100)", etc.).
    The Brightspace gradebook will have the columns named after the assignment name on brightspace, so you will need to rename them to the required format.
    It also requires that the dataframe has a 'Student ID' and 'Name' column, which should be the case if you have used the 'ingesting' functions
    to read in the data from each individual assignment.

    Example:
        # usage
        df = prepare_data_for_departmental_template(df)

    Raises:
    ValueError: If the DataFrame is empty, missing required columns, or missing weighted columns
    """
    # check to make sure df is a DataFrame\
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a pandas DataFrame")

    # check if the DataFrame is empty
    if df.empty:
        raise ValueError("DataFrame is empty")

    # check if the DataFrame has the required columns
    required_columns = ["Student ID", "Name"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"DataFrame is missing columns: {', '.join(missing_columns)}")

    # Check that there is at least one column call 'Coursework 1 (100)'
    coursework_100_columns = [
        col for col in df.columns if "Coursework" in col and "(100)" in col
    ]
    if not coursework_100_columns:
        raise ValueError("DataFrame is missing coursework columns")
    elif len(coursework_100_columns) == 1 and "Total % Grade" not in df.columns:
        # if there is only one coursework column, we can calculate the total module score
        calculate_total_module_score(df)
    elif len(coursework_100_columns) > 1:
        # if there is more than one coursework column, we need to check for the weighted columns
        weighted_columns_present, missing_weighted_columns = check_for_weighted_columns(
            coursework_100_columns
        )
        if weighted_columns_present == False:
            raise ValueError(
                f"""DataFrame is missing weighted columns: {', '.join(missing_weighted_columns)}
                             You need to have two columns for each piece of coursework, one for the raw score and one for the weighted score.
                             The raw score should be out of 100 and the weighted score should be out of the total marks for that piece of coursework.
                             For example, if you have a piece of coursework worth 40 marks, you should have two columns: 'Coursework 1 (100)' and 'Coursework 1 (40)' 
                             You can use the `calculate_weighted_score` function to calculate the weighted score from the raw score, before calling this function."""
            )

    # check that all the coursework columns are numeric
    for col in coursework_100_columns:
        if df[col].dtype not in ["int64", "float64"]:
            raise ValueError(
                f"""Column {col} is not numeric, you can only calculate the weighted score of numeric columns.
                             This might be because there are non-numeric values in the column. Please inspect the column 
                             and make sure it only contains numeric values. If it doesn't, you can convert the column to numeric with
                            `pd.to_numeric(errors='coerce')` but make sure you understand the data before doing this!"""
            )

    # sort the columns in the correct order
    try:
        df = df.reindex(columns=sort_order_columns(df))
    except Exception as e:
        raise ValueError(f"Error sorting columns: {e}")

    # calculate the total module score
    calculate_total_module_score(df)

    # calculate the letter grades
    make_letter_grade(df, fail_threshold=fail_threshold)

    return df
