#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The two lists that get read off the finished sheet and acted on.

Repeats and borderlines were both being worked out by eye, off eighty rows.
Neither list is a decision -- they are the students a decision is due about,
written down so it is made from a list rather than from a scroll.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pandas as pd
import pytest

from grader_helper import (
    students_on_a_boundary,
    students_to_repeat,
    write_outcomes,
)
from grader_helper.recording import evidence_for


@pytest.fixture
def sheet():
    """A prepared marks frame, one student per interesting case."""
    return pd.DataFrame(
        {
            "Name": ["Failed", "Absent", "Passed", "OneOff", "TwoOff", "Top"],
            "Student ID": [f"2330430{i}" for i in range(6)],
            "Coursework 1 (100)": [30, 0, 62, 39, 37, 92],
            "Total % Grade": [30.0, 0.0, 62.0, 39.0, 37.0, 92.0],
            "Letter Grade": ["F", "NG", "B3", "D1", "D1", "A1"],
        }
    )


# ---------------------------------------------------------------------------
# Who has to repeat
# ---------------------------------------------------------------------------


def test_both_kinds_of_not_passing_are_on_the_list(sheet):
    """NG is no participation and F is work that did not pass. Different
    things, same conversation."""
    repeats = students_to_repeat(sheet)

    assert repeats["Name"].tolist() == ["Failed", "Absent"]


def test_whole_rows_come_back(sheet):
    """The per-assessment marks are what say WHY they did not pass, and a
    repeat conversation starting from a total alone starts by going back to
    the sheet."""
    repeats = students_to_repeat(sheet)

    assert list(repeats.columns) == list(sheet.columns)
    assert repeats.iloc[0]["Coursework 1 (100)"] == 30


def test_a_passing_cohort_gives_an_empty_list(sheet):
    passing = sheet[~sheet["Letter Grade"].isin(["F", "NG"])]

    assert students_to_repeat(passing).empty


def test_the_grades_that_count_can_be_changed(sheet):
    """A programme where D1 is not a pass is somebody else's rule, not this
    package's to hard-code."""
    repeats = students_to_repeat(sheet, grades=("F", "NG", "D1"))

    assert len(repeats) == 4


def test_a_sheet_with_no_grade_column_says_which_step_adds_it(sheet):
    with pytest.raises(ValueError, match="prepare_data_for_departmental_template"):
        students_to_repeat(sheet.drop(columns=["Letter Grade"]))


# ---------------------------------------------------------------------------
# Who is one mark short
# ---------------------------------------------------------------------------


def test_a_student_one_mark_short_is_flagged(sheet):
    """39 is a D1; 40 is a C3. One more mark is a different degree class."""
    on_it = students_on_a_boundary(sheet)

    assert "OneOff" in on_it["Name"].tolist()
    row = on_it.loc[on_it["Name"] == "OneOff"].iloc[0]
    assert row["Next Grade"] == "C3"
    assert row["Points To Next"] == 1.0


def test_a_student_three_marks_short_is_not(sheet):
    on_it = students_on_a_boundary(sheet)

    assert "TwoOff" not in on_it["Name"].tolist()


def test_the_nearest_come_first(sheet):
    """The list is read top-down by somebody deciding who to look at again."""
    on_it = students_on_a_boundary(sheet, tolerance=5)

    assert on_it["Points To Next"].is_monotonic_increasing


def test_the_top_band_is_never_borderline(sheet):
    on_it = students_on_a_boundary(sheet, tolerance=50)

    assert "Top" not in on_it["Name"].tolist()


def test_the_tolerance_can_be_widened(sheet):
    assert len(students_on_a_boundary(sheet, tolerance=3)) > len(
        students_on_a_boundary(sheet, tolerance=1)
    )


# ---------------------------------------------------------------------------
# Writing them down
# ---------------------------------------------------------------------------


@pytest.fixture
def module(tmp_path):
    import sys

    sys.path.insert(0, "tests")
    from conftest import make_module

    return make_module(root=tmp_path)


def test_both_lists_are_written_beside_the_module(module, sheet, tmp_path):
    outcomes = write_outcomes(module, sheet)

    assert outcomes.repeats_path == tmp_path / "PS4001 repeats.csv"
    assert outcomes.borderline_path == tmp_path / "PS4001 borderline.csv"
    assert outcomes.repeats_path.exists()
    assert outcomes.borderline_path.exists()


def test_the_files_are_named_for_the_module(module, sheet):
    """These get attached to emails, and "repeats.csv" tells the reader
    nothing about which module's repeats."""
    outcomes = write_outcomes(module, sheet)

    assert outcomes.repeats_path.name.startswith(module.code)


def test_what_was_written_is_what_was_worked_out(module, sheet):
    outcomes = write_outcomes(module, sheet)

    written = pd.read_csv(outcomes.repeats_path, dtype={"Student ID": str})
    assert written["Name"].tolist() == outcomes.repeats["Name"].tolist()


def test_neither_is_replaced_by_accident(module, sheet):
    write_outcomes(module, sheet)

    with pytest.raises(FileExistsError):
        write_outcomes(module, sheet)


@pytest.mark.parametrize("gone", ["PS4001 repeats.csv", "PS4001 borderline.csv"])
def test_a_refusal_leaves_neither_half_rewritten(module, sheet, tmp_path, gone):
    """One list current and the other from the last run is worse than
    neither being written -- and it has to hold whichever of the two is the
    one still sitting there, so both directions are driven."""
    write_outcomes(module, sheet)
    (tmp_path / gone).unlink()

    with pytest.raises(FileExistsError):
        write_outcomes(module, sheet)

    assert not (tmp_path / gone).exists()


def test_overwrite_replaces_them(module, sheet):
    write_outcomes(module, sheet)

    outcomes = write_outcomes(module, sheet, overwrite=True)

    assert outcomes.repeats_path.exists()


def test_the_lists_can_be_worked_out_without_writing(module, sheet):
    outcomes = write_outcomes(module, sheet, save=False)

    assert outcomes.repeats_path is None
    assert not outcomes.repeats.empty


def test_a_module_with_no_root_says_so(sheet):
    import sys

    sys.path.insert(0, "tests")
    from conftest import make_module

    with pytest.raises(ValueError, match="nowhere to write"):
        write_outcomes(make_module(), sheet)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def test_writing_the_lists_is_evidence_the_step_ran(module, sheet):
    outcomes = write_outcomes(module, sheet)

    assert evidence_for(outcomes) == ("outcomes_written", True, "module")


def test_a_cohort_where_nobody_failed_still_counts(module, sheet):
    """Nobody to repeat and nobody on a boundary is a fine result, and the
    step still ran. Counting it as not-done would leave a tick missing on a
    module that is finished."""
    passing = sheet[sheet["Letter Grade"] == "B3"]

    outcomes = write_outcomes(module, passing)

    assert outcomes.repeats.empty
    assert evidence_for(outcomes) == ("outcomes_written", True, "module")


def test_working_them_out_without_writing_is_not_evidence(module, sheet):
    outcomes = write_outcomes(module, sheet, save=False)

    assert evidence_for(outcomes) == ("outcomes_written", False, "module")
