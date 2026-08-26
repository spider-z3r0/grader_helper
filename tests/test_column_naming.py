#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The coursework column-naming contract.

Three functions share an implicit convention for coursework column names,
and they disagree about it. The docstrings across the package state the
intended form as ``"Coursework 1 (40)"`` -- one space, integer weight, no
percent sign:

  - calculate_weighted_score  WRITES the weighted column
  - sort_order_columns        READS it via r"Coursework (\\d+) \\((\\d+)\\)"
  - check_for_weighted_columns READS it by splitting on " ("

These tests pin the convention down before the polars migration, because
the migration has to preserve or deliberately fix it, and it cannot do
either while the contract is undocumented.
"""

import pandas as pd
import pytest

from grader_helper import (
    calculate_weighted_score,
    check_for_weighted_columns,
    sort_order_columns,
)

INTENDED_WEIGHTED_NAME = "Coursework 1 (40)"


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
    """The maths is right even though the label is not."""
    calculate_weighted_score(scored, "Coursework 1 (100)", 0.4)
    produced = [c for c in scored.columns if "%" in c][0]
    assert scored[produced].tolist() == [28.0, 32.0]


def test_weighted_column_name_as_currently_produced(scored):
    """Characterisation: the name actually produced today.

    ``col_name.split('(')[0]`` keeps the trailing space, and
    ``str(weight * 100)`` renders a float -- so 0.4 becomes "40.0", not
    "40". Hence a double space and a decimal point.
    """
    calculate_weighted_score(scored, "Coursework 1 (100)", 0.4)
    assert "Coursework 1  (40.0%)" in scored.columns


@pytest.mark.xfail(
    reason=(
        "calculate_weighted_score writes 'Coursework 1  (40.0%)' but every "
        "reader expects 'Coursework 1 (40)'. Fix the producer to match the "
        "documented convention."
    ),
    strict=True,
)
def test_weighted_column_name_should_match_documented_convention(scored):
    calculate_weighted_score(scored, "Coursework 1 (100)", 0.4)
    assert INTENDED_WEIGHTED_NAME in scored.columns


@pytest.mark.xfail(
    reason=(
        "sort_order_columns silently DROPS the weighted columns because its "
        "regex cannot match the name calculate_weighted_score produces. "
        "prepare_data_for_departmental_template reindexes on this result, so "
        "the weighted scores are discarded from the departmental grade file."
    ),
    strict=True,
)
def test_sort_order_columns_keeps_the_weighted_columns(scored):
    calculate_weighted_score(scored, "Coursework 1 (100)", 0.4)
    calculate_weighted_score(scored, "Coursework 2 (100)", 0.6)

    ordered = sort_order_columns(scored.columns)

    weighted = [c for c in scored.columns if "%" in c]
    missing = [c for c in weighted if c not in ordered]
    assert not missing, f"sort_order_columns dropped {missing}"


@pytest.mark.xfail(
    reason=(
        "check_for_weighted_columns reports the weighted columns missing "
        "immediately after calculate_weighted_score created them, so "
        "prepare_data_for_departmental_template raises 'DataFrame is missing "
        "weighted columns' on the documented workflow."
    ),
    strict=True,
)
def test_check_for_weighted_columns_sees_freshly_created_columns(scored):
    calculate_weighted_score(scored, "Coursework 1 (100)", 0.4)
    calculate_weighted_score(scored, "Coursework 2 (100)", 0.6)

    present, missing = check_for_weighted_columns(list(scored.columns))

    assert present, f"reported missing: {missing}"


def test_readers_agree_on_the_intended_convention():
    """Both readers must accept the documented form.

    This one passes today: it is the anchor that says what the producer
    should be fixed *to*, rather than changing the readers to accept the
    malformed name.
    """
    columns = [
        "Name",
        "Student ID",
        "Coursework 1 (100)",
        "Coursework 1 (40)",
        "Coursework 2 (100)",
        "Coursework 2 (60)",
    ]

    ordered = sort_order_columns(columns)
    assert "Coursework 1 (40)" in ordered
    assert "Coursework 2 (60)" in ordered

    present, missing = check_for_weighted_columns(columns)
    assert present, f"reported missing: {missing}"


def test_sort_order_columns_orders_by_number_then_weight_descending():
    """Characterisation of the intended ordering."""
    columns = [
        "Name",
        "Student ID",
        "Coursework 2 (60)",
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
        "Coursework 2 (60)",
    ]
