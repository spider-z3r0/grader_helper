#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ..dependencies import pd



def weighted_column_name(col_name: str, weight: float) -> str:
    """Build the weighted column's name from the raw column's.

    The 2026 departmental grade sheet names these columns
    "Coursework 1 (100)" and "Coursework 1 (40)" -- one space, an integer
    weight, no percent sign (GradeTemplate row 29). sort_order_columns and
    check_for_weighted_columns both parse that form.

    This previously produced "Coursework 1  (40.0%)": a double space,
    because splitting on "(" keeps the raw column's trailing space, and
    "40.0" because str(weight * 100) renders a float. Neither reader could
    match it, so sort_order_columns silently dropped every weighted column
    and check_for_weighted_columns reported them missing immediately after
    they had been created.

    >>> weighted_column_name("Coursework 1 (100)", 0.4)
    'Coursework 1 (40)'
    """
    stem = col_name.split("(")[0].strip()
    percentage = weight * 100
    rounded = round(percentage)
    # Keep a fractional weight readable rather than silently rounding it.
    label = rounded if abs(percentage - rounded) < 1e-9 else round(percentage, 2)
    return f"{stem} ({label})"


def calculate_weighted_score(
    df: pd.DataFrame, col_name: str, weight: float
) -> None | str:
    """
    Calculate the weighted score of a column in a DataFrame

    Args:
    df (pd.DataFrame): DataFrame containing the column to calculate the weighted score
    col_name (str): Name of the column to calculate the weighted score
    weight (float): Weight to apply to the column

    Returns:
    None|str: None if the operation was successful, an error message if the operation failed
    """

    # if the weight is not a number return an error
    if not isinstance(weight, (int, float)) or isinstance(weight, bool):
        return f"""Weight {weight} is not a numeric value.
        Please make sure the weight is a value between 0 and 1.
        """

    # if the weight is not between 0 and 1 return an error
    if weight < 0 or weight > 1:
        return f"Weight {weight} is not between 0 and 1"

    # if the col_name isn't a string return an error
    if not isinstance(col_name, str):
        return f"Column name {col_name} is not a string"

    # Check if the col_name is in the required format
    if "Coursework" not in col_name and "(" not in col_name:
        return f"""Column name {col_name} is not in the required format.
        It should be in the format 'Coursework n (weight) where n is the 
        number of the coursework and weight is the weight of the coursework as a whole number
        (e.g. 'Coursework 1 (40)'). This often happens because the column name is still in the version from the brightspace classlist.
        you could fix this by using the pandas rename function to rename the column to the correct format: 
        i.e. `df.rename(columns={'old_name': 'new_name'}, inplace=True)`"""

    try:
        # if the column isn't numeric return an error
        if df[col_name].dtype not in ["int64", "float64"]:
            return f"""Column {col_name} is not numeric
            , you can only calculate the weighted score of numeric columns.
            This might be because there are non-numeric values in the column.
            Try using the `pd.to_numeric(errors='coerce')` function to convert the column to numeric values.
            MAKE SURE YOU UNDERSTAND THE DATA BEFORE DOING THIS!"""
    except KeyError as e:
        return f"Column {col_name} does not exist in the DataFrame"

    #  Try to calculate the weighted score of the column
    try:
        new_col = weighted_column_name(col_name, weight)
        if new_col == col_name:
            return (
                f"A weight of {weight} would name the weighted column "
                f"{new_col!r}, which is the raw column itself -- writing it "
                "would overwrite the raw marks. A single component worth the "
                "whole module needs no weighting; calculate_total_module_score "
                "handles that case directly."
            )
        df[new_col] = (df[col_name] * weight).round()
        return None
    # If the column does not exist in the DataFrame, print an error message and return the error
    except KeyError as e:
        print(f"Column {col_name} does not exist in the DataFrame")
        print(
            "Please check the column names (with something like `df.columns`) and try again"
        )
        return e
