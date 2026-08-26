#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Golden tests against the 2026 departmental grade sheet.

tests/resources/gradetemplate_samples.csv holds the 20 sample rows from the
GradeTemplate tab, with the values Excel itself computed: the raw marks, the
weighted components, the total and the letter grade.

The departmental sheet is the source of truth precisely because it is
verifiable outside this code -- anyone can open it and read the grades. So
these tests assert that our arithmetic reproduces it exactly, rather than
asserting that our arithmetic is internally consistent.

The rounding policy is the point. The sheet leaves each weighted component
exact and rounds only the total:

    D = C/100*40        ->  29.6, not 30
    F = E/2             ->  33.25, not 33
    H = ROUND(SUM(D,F,G), 0)

Rounding components instead moves the total and can change the letter grade
at a band boundary. It also keeps the student's reported mark and the
audited mark in step: a student told they scored 66.5 has 66.5 carried into
the grade sheet.
"""

import csv

import pandas as pd
import pytest

from grader_helper import calculate_weighted_score, excel_round, make_letter_grade

CW1_WEIGHT = 0.4  # GradeTemplate: D = C/100*40
CW2_WEIGHT = 0.5  # GradeTemplate: F = E/2


@pytest.fixture(scope="module")
def samples(request):
    path = (
        request.config.rootpath / "tests" / "resources"
        / "gradetemplate_samples.csv"
    )
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows, "golden sample data is missing"
    return [
        {k: (float(v) if v not in ("", None) and k != "letter" else v)
         for k, v in row.items()}
        for row in rows
    ]


def test_golden_data_is_present(samples):
    assert len(samples) == 20


def test_weighted_components_match_the_sheet_exactly(samples):
    """Our weighted values must equal the sheet's, to the float.

    This is what fails if component rounding is reintroduced: the sheet has
    29.6 where a rounding implementation has 30.
    """
    df = pd.DataFrame(
        {
            "Coursework 1 (100)": [r["cw1_100"] for r in samples],
            "Coursework 2 (100)": [r["cw2_100"] for r in samples],
        }
    )

    assert calculate_weighted_score(df, "Coursework 1 (100)", CW1_WEIGHT) is None
    assert calculate_weighted_score(df, "Coursework 2 (100)", CW2_WEIGHT) is None

    for ours, theirs in zip(df["Coursework 1 (40)"], [r["cw1_40"] for r in samples]):
        assert ours == pytest.approx(theirs, abs=1e-9)
    for ours, theirs in zip(df["Coursework 2 (50)"], [r["cw2_50"] for r in samples]):
        assert ours == pytest.approx(theirs, abs=1e-9)


def test_weighted_components_are_not_rounded(samples):
    """Belt and braces: at least one component must be fractional."""
    df = pd.DataFrame({"Coursework 1 (100)": [r["cw1_100"] for r in samples]})
    calculate_weighted_score(df, "Coursework 1 (100)", CW1_WEIGHT)

    fractional = [v for v in df["Coursework 1 (40)"] if v != round(v)]
    assert fractional, "weighted components look rounded; the sheet does not round them"


def test_totals_match_the_sheet(samples):
    """Sum the exact components, then round once -- as the sheet does.

    excel_round, not Python's round: two sample rows land on an exact half
    (60.5 and 64.5) where banker's rounding disagrees with Excel.
    """
    for row in samples:
        total = excel_round(
            row["cw1_100"] * CW1_WEIGHT
            + row["cw2_100"] * CW2_WEIGHT
            + row["mcq_10"]
        )
        assert total == row["total"], f"row {int(row['row'])}"


def test_pythons_round_disagrees_with_the_sheet_on_halves(samples):
    """Document why excel_round exists, using the sheet's own data."""
    disagreements = []
    for row in samples:
        exact = (
            row["cw1_100"] * CW1_WEIGHT
            + row["cw2_100"] * CW2_WEIGHT
            + row["mcq_10"]
        )
        if round(exact) != row["total"]:
            disagreements.append((int(row["row"]), exact, round(exact), row["total"]))

    assert disagreements, "expected banker's rounding to disagree somewhere"
    for _, exact, python_result, sheet in disagreements:
        # Every disagreement should be an exact half, not a real error.
        assert exact % 1 == 0.5, f"{exact} is not a half"
        assert abs(python_result - sheet) == 1


def test_a_half_mark_can_change_the_letter_grade(samples):
    """Row 35 totals 64.5: Excel says 65 (B2), Python says 64 (B3)."""
    row = next(r for r in samples if int(r["row"]) == 35)
    exact = (
        row["cw1_100"] * CW1_WEIGHT + row["cw2_100"] * CW2_WEIGHT + row["mcq_10"]
    )
    assert exact == 64.5
    assert make_letter_grade(excel_round(exact)) == "B2" == row["letter"]
    assert make_letter_grade(round(exact)) == "B3"


def test_letter_grades_match_the_sheet(samples):
    for row in samples:
        assert make_letter_grade(row["total"]) == row["letter"], (
            f"row {int(row['row'])}: total {row['total']}"
        )


def test_rounding_each_component_would_change_grades(samples):
    """Document the harm, so nobody reintroduces it as a tidy-up.

    Rounding each weighted component before summing disagrees with the
    sheet on its own sample data, and some disagreements cross a band
    boundary.
    """
    changed_total = 0
    changed_letter = 0
    for row in samples:
        early = excel_round(
            excel_round(row["cw1_100"] * CW1_WEIGHT)
            + excel_round(row["cw2_100"] * CW2_WEIGHT)
            + row["mcq_10"]
        )
        if early != row["total"]:
            changed_total += 1
        if make_letter_grade(early) != row["letter"]:
            changed_letter += 1

    # Measured against this fixture: rows 34 and 47 shift, and row 47
    # crosses a boundary (C1 -> B3). Asserted exactly rather than as a
    # threshold, so a change in either direction is visible.
    assert changed_total == 2
    assert changed_letter == 1
