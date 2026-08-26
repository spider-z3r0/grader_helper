#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Check that every assessment needing a weighted column has one."""

from ..models import Module


def check_for_weighted_columns(
    columns, module: Module
) -> tuple[bool, list[str]]:
    """
    Check a grade sheet's columns for the weighted columns the module needs.

    An assessment marked on its own contribution -- an MCQ out of 10 worth 10 --
    needs no weighted column, and is not reported missing. Only an assessment
    whose ``marks_out_of`` and ``weight`` differ has one to look for.

    Args:
    columns: The column names to check, e.g. ``df.columns``.
    module (Module): The module whose assessments say what is expected.

    Returns:
    tuple[bool, list[str]]: Whether every expected weighted column is present,
    and the names of those that are not.

    Note:
        The missing names are the real column names -- "Coursework 1 (40)" --
        because the module knows the weight. The previous implementation
        counted how many columns shared a trailing number and could only
        report "Coursework 1", leaving the reader to work out the rest.
    """
    present = set(columns)
    missing = [
        assessment.weighted_column
        for assessment in module.assessments
        if assessment.needs_weighting and assessment.weighted_column not in present
    ]
    return not missing, missing
