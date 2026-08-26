#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""One assessment, from unzipped download to departmental grade sheet.

Every other test in this suite exercises a piece. This one exercises the
joins -- and the joins are where the untested parts were. In particular the
feedback sheets here are real workbooks with real numbers in them, so
``extract_studentid_grade`` actually opens a file and reads a cell rather
than being mocked away.

The fixture holds the marks it wrote, so this asserts the pipeline gives
back what went in, not merely that it runs.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pandas as pd
import pytest

from grader_helper import (
    calculate_weighted_score,
    catch_grades,
    import_brightspace_classlist,
    load_module,
    prepare_data_for_departmental_template,
    scan_multiple_subs,
)


@pytest.fixture
def departmental_sheet(fake_module):
    """Drive the whole pipeline, and return what comes out the end."""
    module = load_module(fake_module.root)
    classlist = import_brightspace_classlist(fake_module.classlist)

    df = classlist[["Student ID", "Last Name", "First Name"]].copy()
    df["Name"] = df["First Name"] + " " + df["Last Name"]
    df = df[["Student ID", "Name"]]

    for assessment in module.assessments:
        marks = catch_grades(
            fake_module.submissions[assessment.id], fake_module.grade_cell
        ).rename(columns={"grade": assessment.raw_column})
        df = df.merge(marks, on="Student ID", how="left")

    for assessment in module.assessments:
        if assessment.needs_weighting:
            assert calculate_weighted_score(
                df, assessment.raw_column, assessment.weight_fraction()
            ) is None

    return prepare_data_for_departmental_template(df, module)


# ---------------------------------------------------------------------------
# The pipeline runs
# ---------------------------------------------------------------------------


def test_the_module_loads_from_its_own_file(fake_module):
    module = load_module(fake_module.root)

    assert module.code == "PS4001"
    assert [a.id for a in module.assessments] == ["cw1", "cw2", "mcq"]


def test_the_class_list_keeps_ids_as_text(fake_module):
    """A leading zero survives, and the '#' is stripped."""
    classlist = import_brightspace_classlist(fake_module.classlist)

    assert classlist["Student ID"].dtype == object
    assert "00123456" in classlist["Student ID"].tolist()
    assert not any("#" in i for i in classlist["Student ID"])


def test_marks_are_read_out_of_real_workbooks(fake_module):
    """Not a mock. openpyxl opens the file and reads D30.

    Everywhere else in the suite extract_studentid_grade is monkeypatched
    out, so this is the only place the Excel read itself is exercised.
    """
    marks = catch_grades(fake_module.submissions["cw1"], fake_module.grade_cell)

    expected = fake_module.expected
    submitted = expected.loc[expected["submitted"]]

    assert len(marks) == len(submitted)
    got = dict(zip(marks["Student ID"], marks["grade"]))
    for _, row in submitted.iterrows():
        assert got[row["Student ID"]] == row["cw1"], row["Student ID"]


def test_a_resubmission_is_found(fake_module):
    repeated = scan_multiple_subs(fake_module.submissions["cw1"])

    assert list(repeated) == ["23304307"]
    assert len(repeated["23304307"]) == 2


def test_incidental_folders_do_not_become_students(fake_module):
    """__MACOSX and index.html are in every real download."""
    marks = catch_grades(fake_module.submissions["cw1"], fake_module.grade_cell)

    assert not marks["Student ID"].isin(["__MACOSX", "index"]).any()


# ---------------------------------------------------------------------------
# And produces the right sheet
# ---------------------------------------------------------------------------


def test_the_sheet_has_the_departmental_columns(departmental_sheet):
    assert list(departmental_sheet.columns) == [
        "Name",
        "Student ID",
        "Coursework 1 (100)",
        "Coursework 1 (40)",
        "Coursework 2 (100)",
        "Coursework 2 (50)",
        "MCQ (10)",
        "Total % Grade",
        "Letter Grade",
    ]


def test_every_student_reaches_the_sheet(departmental_sheet, fake_module):
    """Including the one who never submitted -- they still need a grade."""
    assert len(departmental_sheet) == len(fake_module.expected)
    assert set(departmental_sheet["Student ID"]) == set(
        fake_module.expected["Student ID"]
    )


def test_every_total_and_grade_matches_what_was_marked(
    departmental_sheet, fake_module
):
    """The assertion the whole fixture exists for."""
    got = departmental_sheet.set_index("Student ID")
    expected = fake_module.expected.set_index("Student ID")

    for sid, row in expected.iterrows():
        if not row["submitted"]:
            continue
        assert got.loc[sid, "Total % Grade"] == row["Total % Grade"], sid
        assert got.loc[sid, "Letter Grade"] == row["Letter Grade"], sid


def test_a_half_mark_rounds_the_departments_way(departmental_sheet):
    """Eimear Egan totals exactly 64.5.

    Excel rounds half away from zero and gives 65, a B2. Python rounds half
    to even and gives 64, a B3. A student on an exact half must not be
    graded differently by this package than by the sheet the department
    reads.
    """
    row = departmental_sheet.set_index("Student ID").loc["23304305"]

    assert row["Total % Grade"] == 65
    assert row["Letter Grade"] == "B2"


def test_a_leading_zero_survives_the_whole_pipeline(departmental_sheet):
    ids = departmental_sheet["Student ID"].tolist()

    assert "00123456" in ids
    assert 123456 not in ids


def test_zero_throughout_is_no_participation_not_a_fail(departmental_sheet):
    """NG, not F. The sheet distinguishes absence from a bad mark."""
    row = departmental_sheet.set_index("Student ID").loc["23304309"]

    assert row["Total % Grade"] == 0
    assert row["Letter Grade"] == "NG"


def test_a_student_who_never_submitted_still_gets_a_row(departmental_sheet):
    """Their marks are blank, which sums to zero, which reads as NG.

    Worth knowing: this is indistinguishable on the sheet from a student who
    submitted and scored zero. Both are NG, which is what the departmental
    sheet does -- but it means the sheet alone cannot tell you which
    happened.
    """
    row = departmental_sheet.set_index("Student ID").loc["23304311"]

    assert row["Letter Grade"] == "NG"
