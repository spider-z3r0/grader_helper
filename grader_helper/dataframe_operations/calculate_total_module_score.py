#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The module total: sum each assessment's contribution, then round once."""

from ..dependencies import pd
from ..models import Module
from .rounding import excel_round_series

#: The departmental sheet's name for the total (GradeTemplate row 29).
TOTAL_COLUMN = "Total % Grade"


def contribution_columns(module: Module) -> list[str]:
    """The one column per assessment that carries its contribution.

    For a coursework marked out of 100 and worth 40 that is the weighted
    column, "Coursework 1 (40)". For an MCQ marked out of 10 and worth 10
    there is no weighted column, so the raw column *is* the contribution.

    This is where the old implementation went wrong: it collected columns
    whose name contained "Coursework", so "MCQ (10)" was left out of every
    total. On the departmental sample data that turns 70 into 63 -- a B1
    reported as a B3.
    """
    return [a.weighted_column or a.raw_column for a in module.assessments]


def calculate_total_module_score(df: pd.DataFrame, module: Module) -> None | str:
    """
    Calculate the total module score of a DataFrame.

    Args:
    df (pd.DataFrame): DataFrame holding the module's assessment columns.
    module (Module): The module whose assessments define what to sum.

    Returns:
    None | str: None if the operation was successful, an error message if not.

    Note:
        The departmental sheet rounds here and only here:
        H = ROUND(SUM(D, F, G), 0), with the weighted components left exact.
        Rounding the components instead shifts the total and can cross a band
        boundary -- see tests/test_departmental_golden.py.

        A blank mark counts as zero, because that is what Excel's SUM does in
        the sheet. A student blank throughout therefore totals 0, which
        make_letter_grade reports as "NG" -- no participation, which is what a
        row of blanks means.
    """
    if df.empty:
        return "DataFrame is empty"

    required_columns = ["Student ID", "Name"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        return f"DataFrame is missing columns: {', '.join(missing_columns)}"

    if not module.assessments:
        return (
            f"Module {module.code} declares no assessments, so there is "
            "nothing to total. Add an [[assessment]] to module.toml."
        )

    wanted = contribution_columns(module)
    absent = [col for col in wanted if col not in df.columns]
    if absent:
        return (
            f"DataFrame is missing the columns that carry each assessment's "
            f"contribution to the module total: {', '.join(absent)}. "
            "Weighted columns are created by calculate_weighted_score; check "
            "the column names against module.toml with `print(df.columns)`."
        )

    # Sum the exact components, then round once. skipna is pandas' default
    # and is deliberate here -- see the note above.
    df[TOTAL_COLUMN] = excel_round_series(df[wanted].sum(axis=1))
    return None
