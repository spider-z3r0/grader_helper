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
from conftest import make_assessment, make_module

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


def test_sort_order_columns_keeps_the_weighted_columns(
    scored, two_coursework_module
):
    calculate_weighted_score(scored, "Coursework 1 (100)", 0.4)
    calculate_weighted_score(scored, "Coursework 2 (100)", 0.6)

    ordered = sort_order_columns(scored.columns, two_coursework_module)

    weighted = ["Coursework 1 (40)", "Coursework 2 (60)"]
    missing = [c for c in weighted if c not in ordered]
    assert not missing, f"sort_order_columns dropped {missing}"


def test_check_for_weighted_columns_sees_freshly_created_columns(
    scored, two_coursework_module
):
    calculate_weighted_score(scored, "Coursework 1 (100)", 0.4)
    calculate_weighted_score(scored, "Coursework 2 (100)", 0.6)

    present, missing = check_for_weighted_columns(
        scored.columns, two_coursework_module
    )

    assert present, f"reported missing: {missing}"


def test_readers_accept_the_departmental_convention():
    module = make_module(
        assessments=[
            make_assessment(id="cw1", name="Coursework 1", weight=40),
            make_assessment(id="cw2", name="Coursework 2", weight=60),
        ]
    )
    columns = [
        "Name",
        "Student ID",
        "Coursework 1 (100)",
        "Coursework 1 (40)",
        "Coursework 2 (100)",
        "Coursework 2 (60)",
    ]

    ordered = sort_order_columns(columns, module)
    assert "Coursework 1 (40)" in ordered
    assert "Coursework 2 (60)" in ordered

    present, missing = check_for_weighted_columns(columns, module)
    assert present, f"reported missing: {missing}"


def test_sort_order_columns_follows_the_modules_declared_order():
    """Raw column then weighted, assessments in the order module.toml lists.

    This replaces an ordering rule of "coursework number ascending, weight
    descending", which could only ever apply to components literally named
    "Coursework N". The author's declared order is the honest rule, and for
    the departmental layout the two agree.
    """
    module = make_module(
        assessments=[
            make_assessment(id="cw1", name="Coursework 1", weight=40),
            make_assessment(id="cw2", name="Coursework 2", weight=60),
        ]
    )
    columns = [
        "Name",
        "Student ID",
        "Coursework 2 (60)",
        "Coursework 1 (40)",
        "Coursework 2 (100)",
        "Coursework 1 (100)",
    ]
    assert sort_order_columns(columns, module) == [
        "Name",
        "Student ID",
        "Coursework 1 (100)",
        "Coursework 1 (40)",
        "Coursework 2 (100)",
        "Coursework 2 (60)",
    ]


def test_sort_order_columns_never_drops_a_column(departmental_module):
    """Anything the module does not describe rides along at the end.

    Silently dropping columns is the defect this function was rewritten to
    fix, so an unrecognised column must survive rather than vanish.
    """
    columns = [*DEPARTMENTAL_HEADERS, "Moderator note", "Extension?"]

    ordered = sort_order_columns(columns, departmental_module)

    assert set(ordered) == set(columns)
    assert ordered[-2:] == ["Moderator note", "Extension?"]


def test_sort_order_columns_omits_columns_the_frame_does_not_have(
    departmental_module,
):
    """Reindexing onto an absent column would manufacture a column of NaN."""
    columns = ["Name", "Student ID", "Coursework 1 (100)", "Coursework 1 (40)"]

    assert sort_order_columns(columns, departmental_module) == columns


def test_sort_order_columns_handles_the_full_departmental_layout(
    departmental_module,
):
    """The whole of GradeTemplate row 29, in its own order.

    Previously xfailed: sort_order_columns recognised only components
    literally named "Coursework N" and dropped 'MCQ (10)', 'Total % Grade',
    'Letter Grade' and 'Comments' -- four of the ten. Being told the shape by
    the module rather than inferring it from the names resolves that.
    """
    ordered = sort_order_columns(DEPARTMENTAL_HEADERS, departmental_module)

    dropped = [c for c in DEPARTMENTAL_HEADERS if c not in ordered]
    assert not dropped, f"dropped {dropped}"
    assert ordered == DEPARTMENTAL_HEADERS
