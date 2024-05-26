#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ..dependencies import pd


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

    # if the weight is not a float return an error
    if not isinstance(weight, float):
        return f"""Weight {weight} is not a float value.
        Please make sure the weight is a float value between 0 and 1.
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
        df[f"{col_name.split('(')[0]} ({str(weight*100)}%)"] = df[col_name] * weight
        # round the result to the nearest whole number
        df[f"{col_name.split('(')[0]} ({str(weight*100)}%)"] = df[
            f"{col_name.split('(')[0]} ({str(weight*100)}%)"
        ].round()
        return None
    # If the column does not exist in the DataFrame, print an error message and return the error
    except KeyError as e:
        print(f"Column {col_name} does not exist in the DataFrame")
        print(
            "Please check the column names (with something like `df.columns`) and try again"
        )
        return e
