#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Collecting a term of weekly quizzes into one mark.

House convention: ``pl`` is pathlib, ``pr`` is polars.

The fixtures here write exports in the shape Brightspace actually produces,
because two of the defects these tests exist to catch live entirely in that
shape: the ``#`` on the username, and the leading space in the ``" %"``
column name. A tidied-up fixture would pass against code that handles
neither. That shape is defined once, in ``fake_module.write_quiz``.
"""

import pathlib as pl

import pandas as pd
import polars as pr
import pytest

from conftest import make_assessment
# write_quiz lives beside the submission-folder builder, so there is one
# definition of what a Brightspace export looks like rather than two.
from fake_module import write_quiz
from grader_helper.ingesting import (
    DuplicateAttemptError,
    collect_quiz_marks,
    quiz_name,
    read_quiz,
)

@pytest.fixture
def quiz_assessment():
    """Eleven weekly quizzes: one assessment, out of 10, worth 10.

    Carrying its own pass_mark, as it would in module.toml. Tests that want
    a different rule override it at the call, which is also the precedence
    being asserted further down.
    """
    return make_assessment(
        id="quizzes",
        type="quiz",
        name="Quizzes",
        marks_out_of=10,
        weight=10,
        pass_mark=80.0,
    )


@pytest.fixture
def quiz_folder(tmp_path):
    folder = tmp_path / "quizzes"
    folder.mkdir()
    return folder


# ---------------------------------------------------------------------------
# read_quiz
# ---------------------------------------------------------------------------


def test_read_quiz_strips_the_hash_from_the_username(quiz_folder):
    """Brightspace writes '#56170559'; the class list holds '56170559'.

    Left on, the join does not raise -- it matches nothing, and every student
    comes back twice with half their row empty. Which is worse than raising.
    """
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 90.0})

    frame = read_quiz(quiz_folder / "Quiz 1 - PS4001 - 12 January 2026.csv").collect()

    assert frame.get_column("Student ID").to_list() == ["23304301"]


def test_read_quiz_keeps_a_leading_zero_id(quiz_folder):
    """'00123456' inferred as a number reads back 123456."""
    write_quiz(quiz_folder, "Quiz 1", {"00123456": 90.0})

    frame = read_quiz(quiz_folder / "Quiz 1 - PS4001 - 12 January 2026.csv").collect()

    assert frame.get_column("Student ID").to_list() == ["00123456"]


def test_read_quiz_keeps_a_leading_zero_with_no_hash_to_protect_it(quiz_folder):
    """The '#' is what makes polars infer the username as text.

    Strip it in the export -- which is how the id reaches us from anywhere
    that writes the bare number -- and inference makes '00123456' an integer,
    and either 123456 or a crash on the string operations. Reading every
    column as text is what stops that, and this is the only test that says so:
    every other fixture here has the '#' doing the job by accident.
    """
    path = quiz_folder / "Quiz 1 - PS4001.csv"
    pd.DataFrame(
        {
            "Username": ["00123456"],
            "FirstName": ["A"],
            "LastName": ["B"],
            " %": ["90 %"],
        }
    ).to_csv(path, index=False)

    frame = read_quiz(path).collect()

    assert frame.get_column("Student ID").to_list() == ["00123456"]


def test_read_quiz_names_the_score_column_after_the_quiz(quiz_folder):
    write_quiz(quiz_folder, "Quiz 3", {"23304301": 90.0})

    frame = read_quiz(quiz_folder / "Quiz 3 - PS4001 - 12 January 2026.csv").collect()

    assert frame.columns == ["Student ID", "First Name", "Last Name", "Quiz 3 score"]
    assert frame.schema["Quiz 3 score"] == pr.Float64


def test_read_quiz_reads_the_percentage_not_the_raw_score(quiz_folder):
    """The threshold is a percentage, so 8/10 must arrive as 80.0."""
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 80.0})

    frame = read_quiz(quiz_folder / "Quiz 1 - PS4001 - 12 January 2026.csv").collect()

    assert frame.get_column("Quiz 1 score").to_list() == [80.0]


def test_read_quiz_refuses_a_second_row_for_one_student(quiz_folder):
    """Two attempts, and which one counts is the module's rule, not ours."""
    path = quiz_folder / "Quiz 1 - PS4001 - 12 January 2026.csv"
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 40.0})
    with path.open("a", encoding="utf-8") as f:
        f.write("23304301,#23304301,Surname01,First01,2,9.0,10,90 %\n")

    with pytest.raises(DuplicateAttemptError, match="23304301"):
        read_quiz(path)


def test_read_quiz_names_the_missing_columns(quiz_folder):
    path = quiz_folder / "Not a quiz - PS4001.csv"
    pd.DataFrame({"Username": ["#23304301"], " %": ["90 %"]}).to_csv(path, index=False)

    with pytest.raises(ValueError, match="FirstName"):
        read_quiz(path)


def test_read_quiz_says_what_columns_it_found_when_the_percentage_is_missing(
    quiz_folder,
):
    path = quiz_folder / "Quiz 1 - PS4001.csv"
    pd.DataFrame(
        {"Username": ["#23304301"], "FirstName": ["A"], "LastName": ["B"]}
    ).to_csv(path, index=False)

    with pytest.raises(ValueError, match="Columns present"):
        read_quiz(path)


def test_read_quiz_refuses_a_non_csv(tmp_path):
    path = tmp_path / "Quiz 1.xlsx"
    path.write_bytes(b"")

    with pytest.raises(ValueError, match="not a .csv"):
        read_quiz(path)


def test_read_quiz_reports_a_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_quiz(tmp_path / "Quiz 1 - nothing here.csv")


def test_quiz_name_takes_everything_before_the_first_separator():
    assert quiz_name(pl.Path("Quiz 1 - PS4001 - 12 January 2026.csv")) == "Quiz 1"
    assert quiz_name(pl.Path("Week 3.csv")) == "Week 3"


# ---------------------------------------------------------------------------
# collect_quiz_marks
# ---------------------------------------------------------------------------


def collect(folder, assessment, class_list, **kwargs):
    return collect_quiz_marks(assessment, class_list, folder=folder, **kwargs)


def a_class_list(*ids) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Student ID": list(ids),
            "Last Name": [f"Surname{i[-2:]}" for i in ids],
            "First Name": [f"First{i[-2:]}" for i in ids],
            "Score": [""] * len(ids),
        }
    )


def test_the_mark_is_a_count_of_quizzes_passed(quiz_folder, quiz_assessment):
    for i in range(1, 4):
        write_quiz(quiz_folder, f"Quiz {i}", {"23304301": 90.0, "23304302": 40.0})

    marks = collect(quiz_folder, quiz_assessment, a_class_list("23304301", "23304302"))

    assert list(marks.columns) == ["Student ID", "Quizzes (10)"]
    assert marks.set_index("Student ID")["Quizzes (10)"].to_dict() == {
        "23304301": 3,
        "23304302": 0,
    }


def test_the_pass_mark_is_strict(quiz_folder, quiz_assessment):
    """Exactly 80% fails at pass_mark=80. The rule as the module states it."""
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 80.0, "23304302": 80.1})

    marks = collect(
        quiz_folder, quiz_assessment, a_class_list("23304301", "23304302")
    ).set_index("Student ID")["Quizzes (10)"]

    assert marks["23304301"] == 0
    assert marks["23304302"] == 1


def test_a_free_pass_forgives_one_bad_week(quiz_folder, quiz_assessment):
    """Nine passes out of eleven, plus the free pass, is full marks."""
    passed = {"23304301": 90.0}
    failed = {"23304301": 10.0}
    for i in range(1, 10):
        write_quiz(quiz_folder, f"Quiz {i:02d}", passed)
    for i in (10, 11):
        write_quiz(quiz_folder, f"Quiz {i}", failed)

    marks = collect(
        quiz_folder, quiz_assessment, a_class_list("23304301"), free_passes=1
    )

    assert marks["Quizzes (10)"].tolist() == [10]


def test_the_free_pass_cannot_take_a_student_over_the_marks_available(
    quiz_folder, quiz_assessment
):
    """Eleven passes plus a free one is 12, and the assessment is out of 10.

    The cell this was ported from added the point unconditionally, so a
    student who passed everything scored 12 out of 10 and carried 2% of
    somebody else's module into their total.
    """
    for i in range(1, 12):
        write_quiz(quiz_folder, f"Quiz {i:02d}", {"23304301": 90.0})

    marks = collect(
        quiz_folder, quiz_assessment, a_class_list("23304301"), free_passes=1
    )

    assert marks["Quizzes (10)"].tolist() == [10]


def test_ten_passes_plus_a_free_one_is_still_ten(quiz_folder, quiz_assessment):
    for i in range(1, 11):
        write_quiz(quiz_folder, f"Quiz {i:02d}", {"23304301": 90.0})
    write_quiz(quiz_folder, "Quiz 11", {"23304301": 10.0})

    marks = collect(
        quiz_folder, quiz_assessment, a_class_list("23304301"), free_passes=1
    )

    assert marks["Quizzes (10)"].tolist() == [10]


def test_a_student_who_sat_nothing_scores_zero_not_the_free_pass(
    quiz_folder, quiz_assessment
):
    """NG, not F.

    The departmental sheet awards NG where the module total is zero, and
    excludes it from the average QPV. Handing a student who never appeared
    1% would make that total non-zero and quietly turn their NG into a fail.
    """
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 90.0})

    marks = collect(
        quiz_folder,
        quiz_assessment,
        a_class_list("23304301", "23304309"),
        free_passes=1,
    ).set_index("Student ID")["Quizzes (10)"]

    assert marks["23304309"] == 0
    assert marks["23304301"] == 2


def test_a_student_who_sat_and_failed_still_gets_the_free_pass(
    quiz_folder, quiz_assessment
):
    """The distinction that makes the test above a rule rather than an accident."""
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 10.0})

    marks = collect(
        quiz_folder, quiz_assessment, a_class_list("23304301"), free_passes=1
    )

    assert marks["Quizzes (10)"].tolist() == [1]


def test_the_free_pass_needs_a_score_and_not_merely_a_row(
    quiz_folder, quiz_assessment
):
    """Opened the quiz, never submitted: a row, but no percentage.

    Brightspace still exports the student, so the class-list default that
    protects the wholly absent student does not reach them. Without the
    check on having sat something, they take the free pass and their NG
    becomes an F -- by the same route, and just as quietly.
    """
    write_quiz(quiz_folder, "Quiz 1", {"23304301": None, "23304302": 10.0})

    marks = collect(
        quiz_folder,
        quiz_assessment,
        a_class_list("23304301", "23304302"),
        free_passes=1,
    ).set_index("Student ID")["Quizzes (10)"]

    assert marks["23304301"] == 0
    assert marks["23304302"] == 1


def test_every_student_in_the_class_list_gets_a_row(quiz_folder, quiz_assessment):
    """A missing row is a dropped component, and a total missing a component
    is still a plausible number."""
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 90.0})

    marks = collect(
        quiz_folder, quiz_assessment, a_class_list("23304301", "23304302", "00123456")
    )

    assert marks["Student ID"].tolist() == ["23304301", "23304302", "00123456"]


def test_a_student_missing_from_one_quiz_keeps_the_others(
    quiz_folder, quiz_assessment
):
    """The join has to be a full outer one: sat quiz 1, missed quiz 2."""
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 90.0, "23304302": 90.0})
    write_quiz(quiz_folder, "Quiz 2", {"23304302": 90.0})

    marks = collect(
        quiz_folder, quiz_assessment, a_class_list("23304301", "23304302")
    ).set_index("Student ID")["Quizzes (10)"]

    assert marks["23304301"] == 1
    assert marks["23304302"] == 2


def test_a_student_not_in_the_class_list_is_dropped_with_a_warning(
    quiz_folder, quiz_assessment
):
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 90.0, "99999999": 90.0})

    with pytest.warns(UserWarning, match="99999999"):
        marks = collect(quiz_folder, quiz_assessment, a_class_list("23304301"))

    assert marks["Student ID"].tolist() == ["23304301"]


def test_two_exports_for_one_quiz_are_refused(quiz_folder, quiz_assessment):
    """Otherwise the same quiz is counted twice and everyone gains a mark."""
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 90.0})
    (quiz_folder / "Quiz 1 - PS4001 - 13 January 2026.csv").write_text(
        (quiz_folder / "Quiz 1 - PS4001 - 12 January 2026.csv").read_text(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Quiz 1"):
        collect(quiz_folder, quiz_assessment, a_class_list("23304301"))


def test_an_empty_folder_is_refused(quiz_folder, quiz_assessment):
    with pytest.raises(FileNotFoundError, match="No .csv quiz exports"):
        collect(quiz_folder, quiz_assessment, a_class_list("23304301"))


def test_a_fractional_marks_out_of_is_refused(quiz_folder):
    """A count of quizzes cannot produce 7.5."""
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 90.0})
    assessment = make_assessment(
        id="quizzes",
        type="quiz",
        name="Quizzes",
        marks_out_of=7.5,
        weight=10,
        pass_mark=80.0,
    )

    with pytest.raises(ValueError, match="cannot be fractional"):
        collect(quiz_folder, assessment, a_class_list("23304301"))


def test_a_class_list_without_student_ids_is_refused(quiz_folder, quiz_assessment):
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 90.0})

    with pytest.raises(ValueError, match="no 'Student ID' column"):
        collect(quiz_folder, quiz_assessment, pd.DataFrame({"Username": ["x"]}))


def test_the_column_name_comes_from_the_assessment(quiz_folder):
    """Not hardcoded. An MCQ out of 10 worth 10 is 'MCQ (10)'."""
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 90.0})
    assessment = make_assessment(
        id="mcq", type="mcq", name="MCQ", marks_out_of=10, weight=10, pass_mark=80.0
    )

    marks = collect(quiz_folder, assessment, a_class_list("23304301"))

    assert list(marks.columns) == ["Student ID", "MCQ (10)"]


def test_the_folder_defaults_to_the_assessments_submissions(tmp_path, quiz_assessment):
    """For a quiz the Brightspace download is the submissions, so there is no
    new folder to configure."""
    root = tmp_path / "assessments"
    submissions = root / "quizzes" / "submissions"
    submissions.mkdir(parents=True)
    write_quiz(submissions, "Quiz 1", {"23304301": 90.0})
    quiz_assessment.bind(root)

    marks = collect_quiz_marks(quiz_assessment, a_class_list("23304301"))

    assert marks["Quizzes (10)"].tolist() == [1]


# ---------------------------------------------------------------------------
# Where the policy comes from
# ---------------------------------------------------------------------------


def test_the_pass_mark_is_taken_from_the_assessment(quiz_folder):
    """The point of putting it in module.toml: the call does not restate it."""
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 60.0})
    assessment = make_assessment(
        id="quizzes",
        type="quiz",
        name="Quizzes",
        marks_out_of=10,
        weight=10,
        pass_mark=50.0,
    )

    marks = collect(quiz_folder, assessment, a_class_list("23304301"))

    assert marks["Quizzes (10)"].tolist() == [1]


def test_the_free_passes_are_taken_from_the_assessment(quiz_folder):
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 10.0})
    assessment = make_assessment(
        id="quizzes",
        type="quiz",
        name="Quizzes",
        marks_out_of=10,
        weight=10,
        pass_mark=80.0,
        free_passes=1,
    )

    marks = collect(quiz_folder, assessment, a_class_list("23304301"))

    assert marks["Quizzes (10)"].tolist() == [1]


def test_the_argument_overrides_the_assessment(quiz_folder, quiz_assessment):
    """A one-off -- checking what a different threshold would have done --
    without editing the module's recorded rule."""
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 60.0})

    assert collect(quiz_folder, quiz_assessment, a_class_list("23304301"))[
        "Quizzes (10)"
    ].tolist() == [0]
    assert collect(
        quiz_folder, quiz_assessment, a_class_list("23304301"), pass_mark=50.0
    )["Quizzes (10)"].tolist() == [1]


def test_no_pass_mark_anywhere_is_refused(quiz_folder):
    """Not defaulted to 80. A threshold nobody chose is invisible policy."""
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 90.0})
    assessment = make_assessment(
        id="quizzes", type="quiz", name="Quizzes", marks_out_of=10, weight=10
    )

    with pytest.raises(ValueError, match="no pass_mark"):
        collect(quiz_folder, assessment, a_class_list("23304301"))


def test_a_free_pass_of_zero_is_not_mistaken_for_unset(quiz_folder):
    """0 and None differ: an assessment that forgives nothing must not fall
    back to anything else."""
    write_quiz(quiz_folder, "Quiz 1", {"23304301": 10.0})
    assessment = make_assessment(
        id="quizzes",
        type="quiz",
        name="Quizzes",
        marks_out_of=10,
        weight=10,
        pass_mark=80.0,
        free_passes=3,
    )

    marks = collect(
        quiz_folder, assessment, a_class_list("23304301"), free_passes=0
    )

    assert marks["Quizzes (10)"].tolist() == [0]
