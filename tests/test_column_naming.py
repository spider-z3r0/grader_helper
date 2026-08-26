#!/usr/bin/env python
# -*- coding: utf-8 -*-

r"""The coursework column-naming contract.

Three functions share a convention for coursework column names:

  - calculate_weighted_score   WRITES the weighted column
  - sort_order_columns         READS it via r"Coursework (\d+) \((\d+)\)"
  - check_for_weighted_columns READS it by splitting on " ("

The source of truth is the 2026 departmental grade sheet, whose header row
(GradeTemplate row 29) is:

    Name | Student ID | Coursework 1 (100) | Coursework 1 (40) |
    Coursework 2 (100) | Coursework 2 (50) | MCQ (10) |
    Total % Grade | Letter Grade | Comments

So the form is "<component> (<weight>)": one space, integer weight, no
percent sign. calculate_weighted_score used to produce
"Coursework 1  (40.0%)" instead, which neither reader could match.
"""

import pandas as pd
import pytest

from grader_helper import (
    calculate_weighted_score,
    check_for_weighted_columns,
    sort_order_columns,
)
from grader_helper.dataframe_operations.calculate_weighted_score import (
    weighted_column_name,
)

#: GradeTemplate row 29, verbatim.
DEPARTMENTAL_HEADERS = [
    "Name",
    "Student ID",
    "Coursework 1 (100)",
    "Coursework 1 (40)",
    "Coursework 2 (100)",
    "Coursework 2 (50)",
    "MCQ (10)",
    "Total % Grade",
    "Letter Grade",
    "Comments",
]


@pytest.fixture
def scored():
    return pd.DataFrame(
        {
            "Name": ["Anna", "Ben"],
            "Student ID": ["12345678", "87654321"],
            "Coursework 1 (100)": [70, 80],
            "Coursework 2 (100)": [60, 90],
        }
    )


def test_weighted_score_arithmetic_is_correct(scored):
    calculate_weighted_score(scored, "Coursework 1 (100)", 0.4)
    assert scored["Coursework 1 (40)"].tolist() == [28.0, 32.0]


@pytest.mark.parametrize(
    "weight,expected",
    [
        (0.4, "Coursework 1 (40)"),
        (0.5, "Coursework 1 (50)"),
        (0.6, "Coursework 1 (60)"),
        (0.1, "Coursework 1 (10)"),
        (0.125, "Coursework 1 (12.5)"),
    ],
)
def test_weighted_column_name(weight, expected):
    assert weighted_column_name("Coursework 1 (100)", weight) == expected


def test_weighted_column_name_matches_the_departmental_sheet(scored):
    calculate_weighted_score(scored, "Coursework 1 (100)", 0.4)
    calculate_weighted_score(scored, "Coursework 2 (100)", 0.5)

    assert "Coursework 1 (40)" in scored.columns
    assert "Coursework 2 (50)" in scored.columns


def test_a_full_weight_would_overwrite_the_raw_marks(scored):
    """Guard against a silent overwrite rather than doing it."""
    error = calculate_weighted_score(scored, "Coursework 1 (100)", 1.0)

    assert error is not None
    assert "overwrite" in error
    assert scored["Coursework 1 (100)"].tolist() == [70, 80]


def test_sort_order_columns_keeps_the_weighted_columns(scored):
    calculate_weighted_score(scored, "Coursework 1 (100)", 0.4)
    calculate_weighted_score(scored, "Coursework 2 (100)", 0.6)

    ordered = sort_order_columns(scored.columns)

    weighted = ["Coursework 1 (40)", "Coursework 2 (60)"]
    missing = [c for c in weighted if c not in ordered]
    assert not missing, f"sort_order_columns dropped {missing}"


def test_check_for_weighted_columns_sees_freshly_created_columns(scored):
    calculate_weighted_score(scored, "Coursework 1 (100)", 0.4)
    calculate_weighted_score(scored, "Coursework 2 (100)", 0.6)

    present, missing = check_for_weighted_columns(list(scored.columns))

    assert present, f"reported missing: {missing}"


def test_readers_accept_the_departmental_convention():
    columns = [
        "Name",
        "Student ID",
        "Coursework 1 (100)",
        "Coursework 1 (40)",
        "Coursework 2 (100)",
        "Coursework 2 (50)",
    ]

    ordered = sort_order_columns(columns)
    assert "Coursework 1 (40)" in ordered
    assert "Coursework 2 (50)" in ordered

    present, missing = check_for_weighted_columns(columns)
    assert present, f"reported missing: {missing}"


def test_sort_order_columns_orders_by_number_then_weight_descending():
    columns = [
        "Name",
        "Student ID",
        "Coursework 2 (50)",
        "Coursework 1 (40)",
        "Coursework 2 (100)",
        "Coursework 1 (100)",
    ]
    assert sort_order_columns(columns) == [
        "Name",
        "Student ID",
        "Coursework 1 (100)",
        "Coursework 1 (40)",
        "Coursework 2 (100)",
        "Coursework 2 (50)",
    ]


@pytest.mark.xfail(
    reason=(
        "sort_order_columns only recognises components literally named "
        "'Coursework N', and hardcodes the non-component columns as "
        "['Name', 'Student ID']. The departmental sheet also carries "
        "'MCQ (10)', 'Total % Grade', 'Letter Grade' and 'Comments', all of "
        "which it silently drops. Generalising it needs a decision about "
        "what counts as a component and how components are ordered when "
        "they are not numbered."
    ),
    strict=True,
)
def test_sort_order_columns_handles_the_full_departmental_layout():
    ordered = sort_order_columns(DEPARTMENTAL_HEADERS)
    dropped = [c for c in DEPARTMENTAL_HEADERS if c not in ordered]
    assert not dropped, f"dropped {dropped}"
