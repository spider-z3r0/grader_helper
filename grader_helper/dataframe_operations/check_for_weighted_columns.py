#!/usr/bin/env python
# -*- coding: utf-8 -*-

from collections import Counter

def check_for_weighted_columns(col_list: list[str]) -> bool:
    """
    Checks a list of columns to see if the weighted columns are present.
    If the weighted columns are not present, the function will return False and list the pieces of coursework that are missing weighted columns.
    If the weighted columns are present, the function will return True and an empty list.

    Parameters:
    col_list (list of str): List of column names to check.

    Returns:
    tuple: A boolean indicating if all weighted columns are present, and a list of missing weighted columns.
    """
    coursework_numbers = [int(col.split(" (")[0].split(" ")[-1]) for col in col_list if col.split(" (")[0].split(" ")[-1].isdigit()]
    counts = Counter(coursework_numbers)
    missing_weighted_columns = [f"Coursework {num}" for num, count in counts.items() if count < 2]
    return not missing_weighted_columns, missing_weighted_columns