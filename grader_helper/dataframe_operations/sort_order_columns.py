#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re


def sort_order_columns(columns: list[str]) -> list[str]:
    """
    Order the columns in a list of column names.

    The function separates non-coursework columns from coursework columns, extracts the coursework number and weight
    from the coursework columns, and sorts the coursework columns by coursework number (ascending) and then by weight
    the non-coursework columns are placed first in the final list.

    Args:
    columns (list[str]): List of column names to order

    Returns:
    list[str]: List of ordered column names

    Example:
        # example of valid column names as input:
        ['Name', 'Student ID', 'Coursework 1 (100)', 'Coursework 2 (100)', 'Coursework 1 (40)', 'Coursework 2 (60)']


        # example of valid output:
        ['Name', 'Student ID', 'Coursework 1 (100)', 'Coursework 1 (40)', 'Coursework 2 (100)', 'Coursework 2 (60)']

        # usage
        final_columns_order = sort_order_columns(df.columns)
        df = df.reindex(columns=final_columns_order)



    Note:
        This requires that the dataframe has already been cleaned and the coursework columns are no longer in the format of the brightspace
        gradebook. This essentially means that you've already megrged the dataframes from each individual piece of coursework into one dataframe,
        calculated the weighted grade for each piece of coursework.


    """

    # Separate non-coursework columns
    non_coursework_cols = ["Name", "Student ID"]

    # Extract coursework information and sort
    coursework_info = []
    for col in columns:
        match = re.match(r"Coursework (\d+) \((\d+)\)", col)
        if match:
            coursework_number = int(match.group(1))
            weight = int(match.group(2))
            coursework_info.append((coursework_number, weight, col))

    # Sort coursework columns by coursework number (ascending) and then by weight (descending)
    sorted_coursework_cols = sorted(coursework_info, key=lambda x: (x[0], -x[1]))

    # Flatten the sorted list to get sorted column names
    sorted_coursework_col_names = [col[2] for col in sorted_coursework_cols]

    # Combine non-coursework columns with sorted coursework columns
    final_columns_order = non_coursework_cols + sorted_coursework_col_names

    return final_columns_order
