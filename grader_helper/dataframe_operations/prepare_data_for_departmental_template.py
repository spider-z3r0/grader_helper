#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Turn a marks frame into the departmental grade sheet's layout."""

from ..dependencies import pd
from ..models import Module
from .calculate_total_module_score import TOTAL_COLUMN, calculate_total_module_score
from .check_for_weighted_columns import check_for_weighted_columns
from .make_letter_grade import make_letter_grade
from .sort_order_columns import sort_order_columns

#: The departmental sheet's name for the letter grade (GradeTemplate row 29).
LETTER_COLUMN = "Letter Grade"


def prepare_data_for_departmental_template(
    df: pd.DataFrame, module: Module, fail_threshold: int = 35
) -> pd.DataFrame:
    """
    Prepare a marks frame for the departmental template.

    Orders the columns as the template expects, totals the module, and
    converts each total to a letter grade.

    Args:
    df (pd.DataFrame): DataFrame holding 'Name', 'Student ID' and the
        module's assessment columns.
    module (Module): The module whose assessments define the sheet's shape.
    fail_threshold (int): The mark below which the grade is F. Defaults to 35.

    Returns:
    pd.DataFrame: A new DataFrame in departmental order, with 'Total % Grade'
    and 'Letter Grade' added.

    Note:
        This does not save anything. It expects the marks from each piece of
        assessment already brought into one frame, with the weighted columns
        calculated by calculate_weighted_score. What the columns must be
        called is not a convention to remember -- it falls out of each
        assessment's marks_out_of and weight, so `module.grade_sheet_columns`
        will tell you.

    Raises:
    ValueError: If the frame is empty, is missing required or assessment
        columns, or holds non-numeric marks.

    Example:
        >>> module = load_module("module.toml")
        >>> df = prepare_data_for_departmental_template(df, module)
    """
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a pandas DataFrame")

    if not isinstance(module, Module):
        raise ValueError(
            "module must be a Module. Load it with load_module(), which reads "
            "module.toml and tells this function the module's shape rather "
            "than leaving it to guess from the column names."
        )

    if df.empty:
        raise ValueError("DataFrame is empty")

    required_columns = ["Student ID", "Name"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"DataFrame is missing columns: {', '.join(missing_columns)}")

    if not module.assessments:
        raise ValueError(
            f"Module {module.code} declares no assessments, so there is no "
            "grade sheet to build. Add an [[assessment]] to module.toml."
        )

    # The raw columns are the marks as awarded; without them there is nothing
    # to work from, whatever else the frame happens to carry.
    missing_raw = [
        a.raw_column for a in module.assessments if a.raw_column not in df.columns
    ]
    if missing_raw:
        raise ValueError(
            f"DataFrame is missing the marks for: {', '.join(missing_raw)}.\n"
            f"Module {module.code} declares "
            f"{len(module.assessments)} assessment(s), so the sheet needs "
            f"these columns: {', '.join(module.grade_sheet_columns)}."
        )

    weighted_present, missing_weighted = check_for_weighted_columns(
        df.columns, module
    )
    if not weighted_present:
        raise ValueError(
            f"""DataFrame is missing weighted columns: {', '.join(missing_weighted)}
            An assessment marked out of more than it is worth needs two columns: the mark
            as awarded, and its contribution to the module total. Coursework 1 marked out
            of 100 and worth 40 needs 'Coursework 1 (100)' and 'Coursework 1 (40)'.
            Use `calculate_weighted_score` to create the second from the first before
            calling this function. An assessment already marked on its contribution -- an
            MCQ out of 10 worth 10 -- needs only the one column and is not listed here."""
        )

    for col in module.grade_sheet_columns:
        if df[col].dtype not in ["int64", "float64"]:
            raise ValueError(
                f"""Column {col} is not numeric, and only numeric columns can be totalled.
                This usually means there are non-numeric values in it. Inspect the column
                before doing anything: if you are satisfied the values really are marks,
                `pd.to_numeric(errors='coerce')` will convert it, turning anything it
                cannot read into a missing value. MAKE SURE YOU UNDERSTAND THE DATA FIRST."""
            )

    df = df.reindex(columns=sort_order_columns(df.columns, module))

    error = calculate_total_module_score(df, module)
    if error is not None:
        raise ValueError(error)

    # make_letter_grade takes one score, not a frame -- so map it over the
    # totals. Calling it with the DataFrame raised
    # ValueError("Score must be an integer or float.") every time, which made
    # this function unusable end to end.
    df[LETTER_COLUMN] = df[TOTAL_COLUMN].map(
        lambda score: make_letter_grade(score, fail_threshold=fail_threshold)
    )

    # Total and Letter Grade were added after the reindex, so put the whole
    # sheet into departmental order once everything exists.
    return df.reindex(columns=sort_order_columns(df.columns, module))
