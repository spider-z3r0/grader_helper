#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Put a grade sheet's columns into departmental order.

The order is *declared*, not inferred. A :class:`~grader_helper.models.Module`
knows its assessments, and each assessment derives its own column names from
``marks_out_of`` and ``weight``, so this function is told the layout rather
than guessing it from column-name regexes.

The old implementation matched ``r"Coursework (\\d+) \\((\\d+)\\)"`` and
returned only what matched, prefixed by a hardcoded ``["Name", "Student ID"]``.
Anything else -- ``MCQ (10)``, ``Total % Grade``, ``Letter Grade``,
``Comments`` -- was silently dropped, which is four of the departmental
sheet's ten columns.
"""

from ..models import Module

#: The departmental sheet's identifying columns, in its own order.
LEADING_COLUMNS: tuple[str, ...] = ("Name", "Student ID")

#: The columns derived from the assessment block, after it.
TRAILING_COLUMNS: tuple[str, ...] = ("Total % Grade", "Letter Grade", "Comments")


def sort_order_columns(columns, module: Module) -> list[str]:
    """
    Order a grade sheet's columns as the departmental template expects.

    Args:
    columns: The column names to order, e.g. ``df.columns``.
    module (Module): The module whose shape defines the assessment block.

    Returns:
    list[str]: The column names in departmental order.

    Note:
        Nothing is ever dropped. A column the module does not account for is
        appended at the end in its original position rather than discarded --
        silently losing columns is the defect this function was rewritten to
        fix, so the replacement is lossless by construction.

        Equally, a column the module declares but the frame does not have is
        left out, because reindexing onto it would manufacture a column of
        NaN.

    Example:
        >>> final_columns_order = sort_order_columns(df.columns, module)
        >>> df = df.reindex(columns=final_columns_order)
    """
    present = list(columns)
    known = [
        *LEADING_COLUMNS,
        *module.grade_sheet_columns,
        *TRAILING_COLUMNS,
    ]

    ordered = [col for col in known if col in present]
    seen = set(ordered)
    # Whatever the module does not describe keeps its relative order and
    # rides along at the end.
    ordered.extend(col for col in present if col not in seen)

    return ordered
