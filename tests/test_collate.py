#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Collating a whole module's marks into one frame.

The interesting case is the mixed module: a coursework whose marks live on
feedback sheets beside a quiz whose marks live in Brightspace exports, both
fetched in one call. Until this existed the only thing that walked a whole
module was a loop inside a test fixture, and that loop read every assessment
as if it were a coursework.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pandas as pd
import pytest

from grader_helper import (
    collate_module_marks,
    import_brightspace_classlist,
    prepare_data_for_departmental_template,
)
from grader_helper.models import load_module


@pytest.fixture
def quiz_module(tmp_path):
    """cw1, cw2 and eleven weekly quizzes, all marked."""
    from fake_module import make_fake_module

    return make_fake_module(tmp_path / "PS4001", quizzes=True)


def loaded(fake):
    """The module and its class list, as a caller would have them."""
    return load_module(fake.root), import_brightspace_classlist(fake.classlist)


# ---------------------------------------------------------------------------
# The mixed module
# ---------------------------------------------------------------------------


def test_coursework_and_quizzes_are_collated_in_one_call(quiz_module):
    """Two kinds of assessment, two entirely different sources, one frame.

    The set of columns, not their order: the weighted ones are appended as
    they are calculated, and putting them in departmental order is
    sort_order_columns' job, downstream of here.
    """
    module, class_list = loaded(quiz_module)

    marks = collate_module_marks(module, class_list, source="feedback")

    assert set(marks.columns) == {"Student ID", "Name"} | set(
        module.grade_sheet_columns
    )


def test_every_mark_survives_the_collation(quiz_module):
    """Against the fixture's own record of what it wrote.

    `expected` is built independently -- the quiz exports are generated
    backwards from its `mcq` column, and the feedback sheets are written
    from its cw columns -- so this checks the collation rather than
    restating it.
    """
    module, class_list = loaded(quiz_module)

    marks = collate_module_marks(module, class_list, source="feedback").set_index(
        "Student ID"
    )
    expected = quiz_module.expected.set_index("Student ID")

    assert marks["Coursework 1 (100)"].dropna().to_dict() == (
        expected["cw1"].drop(index="23304311").to_dict()
    )
    assert marks["Quizzes (10)"].to_dict() == expected["mcq"].to_dict()


def test_the_weighted_columns_are_calculated(quiz_module):
    module, class_list = loaded(quiz_module)

    marks = collate_module_marks(module, class_list, source="feedback")

    row = marks[marks["Student ID"] == "23304301"].iloc[0]
    assert row["Coursework 1 (40)"] == pytest.approx(row["Coursework 1 (100)"] * 0.4)


def test_the_totals_come_out_right(quiz_module):
    """The whole point: collate, then hand it to the departmental prep."""
    module, class_list = loaded(quiz_module)

    sheet = prepare_data_for_departmental_template(
        collate_module_marks(module, class_list, source="feedback"), module
    ).set_index("Student ID")
    expected = quiz_module.expected.set_index("Student ID")

    submitted = expected[expected["submitted"]].index
    assert sheet.loc[submitted, "Total % Grade"].to_dict() == (
        expected.loc[submitted, "Total % Grade"].to_dict()
    )
    assert sheet.loc[submitted, "Letter Grade"].to_dict() == (
        expected.loc[submitted, "Letter Grade"].to_dict()
    )


# ---------------------------------------------------------------------------
# The cohort
# ---------------------------------------------------------------------------


def test_the_class_list_decides_who_is_on_the_sheet(quiz_module):
    """Including the student who never submitted -- they still need a grade."""
    module, class_list = loaded(quiz_module)

    marks = collate_module_marks(module, class_list, source="feedback")

    assert set(marks["Student ID"]) == set(quiz_module.expected["Student ID"])
    assert marks[marks["Student ID"] == "23304311"]["Coursework 1 (100)"].isna().all()


def test_a_leading_zero_id_reaches_the_frame(quiz_module):
    """The id that Excel destroys if anything reads it as a number."""
    module, class_list = loaded(quiz_module)

    marks = collate_module_marks(module, class_list, source="feedback")

    row = marks[marks["Student ID"] == "00123456"]
    assert len(row) == 1
    assert row["Coursework 1 (100)"].notna().all()


def test_a_class_list_whose_ids_are_numbers_still_matches(quiz_module):
    """import_brightspace_classlist hands back text, but nothing guarantees
    the caller used it.

    A class list read with a plain pd.read_excel has an int64 id column, and
    merging int64 against the text ids that come off the feedback sheets
    matches nothing at all -- every mark silently absent, every total wrong,
    no error anywhere. Forcing the column to text is the whole defence, and
    this is the only test that reaches it.
    """
    module, class_list = loaded(quiz_module)
    # 00123456 has to come out first: an int64 column cannot hold a leading
    # zero, which is the same bug from the other end. Dropping them means the
    # quiz collector rightly warns that a student sat a quiz and is not in
    # the class list, so the test says so rather than leaving it as noise.
    as_numbers = class_list[class_list["Student ID"] != "00123456"].copy()
    as_numbers["Student ID"] = as_numbers["Student ID"].astype("int64")

    with pytest.warns(UserWarning, match="00123456"):
        marks = collate_module_marks(module, as_numbers, source="feedback")

    assert marks["Coursework 1 (100)"].notna().any()
    assert marks.set_index("Student ID")["Coursework 1 (100)"]["23304301"] == 74


def test_an_alphabetised_coursework_is_not_mistaken_for_a_quiz(quiz_module):
    """`alphabetise_folders` writes its rename log INTO the submissions
    folder, so every alphabetised coursework has a .csv sitting beside the
    submission folders.

    Read that as a quiz export and the coursework goes down the quiz path,
    where it dies complaining that cw1 has no pass mark -- an error about
    the wrong assessment entirely, in a step the reader was not thinking
    about. Found by running the walkthrough, which alphabetises; no test
    reached it, because the fake module never leaves a log behind.
    """
    module, class_list = loaded(quiz_module)
    cw1 = module.assessment("cw1")
    (cw1.submissions_path / "folder_rename_log.csv").write_text(
        "Original Name,New Name\n", encoding="utf-8"
    )

    marks = collate_module_marks(module, class_list, source="feedback")

    assert marks.set_index("Student ID")["Coursework 1 (100)"]["23304301"] == 74


# ---------------------------------------------------------------------------
# The two records
# ---------------------------------------------------------------------------


def collate_the_grader_files(fake, module):
    """Do what the graders and the leader do: fill in the grader workbooks
    and collate them, so `completed_grades.xlsx` exists to be read."""
    from grader_helper import (
        assign_graders_individual,
        ingest_completed_graderfiles,
        save_grader_sheets,
    )

    for assessment in module.assessments:
        if assessment.grade_cell is None:
            continue
        graders = [g.initials for g in assessment.graders]
        allocation = assign_graders_individual(
            import_brightspace_classlist(fake.classlist), graders
        )
        save_grader_sheets(
            allocation, assessment.grading_output_path, graders, overwrite=True
        )
        # Only the students who actually submitted. A grader cannot copy a
        # mark for a submission that is not there, and writing one anyway
        # made the two records disagree -- which is the fixture lying, not
        # the code failing.
        submitted = fake.expected[fake.expected["submitted"]]
        written = submitted.set_index("Student ID")[assessment.id].to_dict()
        for initials in graders:
            path = assessment.grading_output_path / f"{initials}.xlsx"
            sheet = pd.read_excel(path, dtype={"Student ID": str})
            sheet["Mark"] = [written.get(sid) for sid in sheet["Student ID"]]
            sheet.to_excel(path, index=False)
        ingest_completed_graderfiles(
            assessment.grading_output_path, graders, file_type="excel",
            save=True, overwrite=True,
        )


def test_the_two_records_agree(quiz_module):
    """The step-7 invariant, stated as a test.

    The feedback sheets are what the students received; the collated file is
    what the department receives. `catch_grades` and
    `ingest_completed_graderfiles` exist to check that a human copying a
    number between them got it right. Collating from either must therefore
    give the same marks -- and where it does not, one of those two records is
    wrong, which is exactly what the reconciliation is for.
    """
    module, class_list = loaded(quiz_module)
    collate_the_grader_files(quiz_module, module)

    from_feedback = collate_module_marks(module, class_list, source="feedback")
    from_collated = collate_module_marks(module, class_list, source="collated")

    pd.testing.assert_frame_equal(
        from_feedback.sort_values("Student ID").reset_index(drop=True),
        from_collated.sort_values("Student ID").reset_index(drop=True),
        check_dtype=False,
    )


def test_a_missing_collated_file_names_both_ways_out(quiz_module):
    """It does not quietly read the other record instead."""
    module, class_list = loaded(quiz_module)

    with pytest.raises(FileNotFoundError, match="source='feedback'"):
        collate_module_marks(module, class_list, source="collated")


def test_two_collated_files_are_refused(quiz_module):
    """Two records of the department's marks, and no way to tell which."""
    module, class_list = loaded(quiz_module)
    output = module.assessment("cw1").grading_output_path
    (output / "completed_grades.xlsx").write_bytes(b"")
    (output / "completed_grades.csv").write_text("Student ID,Mark\n")

    with pytest.raises(ValueError, match="two collated grade files"):
        collate_module_marks(module, class_list, source="collated")


def test_an_unknown_source_is_refused(quiz_module):
    module, class_list = loaded(quiz_module)

    with pytest.raises(ValueError, match="source must be one of"):
        collate_module_marks(module, class_list, source="whichever")


# ---------------------------------------------------------------------------
# Marks that come from outside
# ---------------------------------------------------------------------------


def test_marks_can_be_handed_in_for_an_mcq_sat_on_paper(quiz_module):
    """The case with no digital record at all: read the class list, type the
    marks in. An in-person MCQ is still `type = "mcq"`, which is why the
    dispatch asks what an assessment *has* rather than what it *is*."""
    module, class_list = loaded(quiz_module)
    by_hand = quiz_module.expected.set_index("Student ID")["mcq"].to_dict()

    marks = collate_module_marks(
        module, class_list, source="feedback", marks={"quizzes": by_hand}
    )

    assert marks.set_index("Student ID")["Quizzes (10)"].to_dict() == by_hand


def test_handed_in_marks_beat_the_exports(quiz_module):
    """Precedence, stated. The leader correcting a mark must win."""
    module, class_list = loaded(quiz_module)

    marks = collate_module_marks(
        module, class_list, source="feedback", marks={"quizzes": {"23304301": 3}}
    )

    assert marks.set_index("Student ID")["Quizzes (10)"]["23304301"] == 3


def test_marks_may_be_handed_in_as_a_frame(quiz_module):
    module, class_list = loaded(quiz_module)
    frame = pd.DataFrame({"Student ID": ["23304301"], "whatever": [9]})

    marks = collate_module_marks(
        module, class_list, source="feedback", marks={"quizzes": frame}
    )

    assert marks.set_index("Student ID")["Quizzes (10)"]["23304301"] == 9


def test_marks_for_an_unknown_assessment_are_refused(quiz_module):
    module, class_list = loaded(quiz_module)

    with pytest.raises(ValueError, match="not in module"):
        collate_module_marks(
            module, class_list, source="feedback", marks={"cw3": {"23304301": 5}}
        )


def test_an_assessment_with_no_marks_anywhere_warns_and_is_kept(tmp_path):
    """Empty and named, never dropped.

    A vanished assessment takes a component out of every student's total,
    and the total is still a plausible number.
    """
    from fake_module import make_fake_module

    fake = make_fake_module(tmp_path / "PS4001")
    module, class_list = loaded(fake)
    # An MCQ sat in a lecture theatre: no exports, no feedback sheets, no
    # grade cell. Nothing on disk points at a mark for it.
    module.assessment("mcq").grade_cell = None

    with pytest.warns(UserWarning, match="mcq"):
        marks = collate_module_marks(module, class_list, source="feedback")

    assert "MCQ (10)" in marks.columns
    assert marks["MCQ (10)"].isna().all()


# ---------------------------------------------------------------------------
# Refusals on the way in
# ---------------------------------------------------------------------------


def test_a_class_list_missing_names_is_refused(quiz_module):
    module, _ = loaded(quiz_module)

    with pytest.raises(ValueError, match="First Name"):
        collate_module_marks(
            module, pd.DataFrame({"Student ID": ["23304301"]}), source="feedback"
        )


def test_something_that_is_not_a_module_is_refused(quiz_module):
    _, class_list = loaded(quiz_module)

    with pytest.raises(ValueError, match="load_module"):
        collate_module_marks({"code": "PS4001"}, class_list)
