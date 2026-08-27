#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A whole module whose quizzes are collected from Brightspace exports.

The unit tests in test_quiz_marks.py build a folder of CSVs by hand. This
one goes the whole way: a module.toml on disk that records its own quiz
rules, eleven exports where the download would be, and marks collected
using nothing the test hands in.

That is the distinction worth having. A test that passes `pass_mark=80.0`
proves the arithmetic; only a test that reads it out of the file proves the
module *records* it.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pytest

from grader_helper.dataframe_operations import excel_round_series
from grader_helper.ingesting import collect_quiz_marks, import_brightspace_classlist
from grader_helper.models import load_module


@pytest.fixture
def quiz_module(tmp_path):
    """The fake module with its MCQ replaced by eleven weekly quizzes."""
    from fake_module import make_fake_module

    return make_fake_module(tmp_path / "PS4001", quizzes=True)


# ---------------------------------------------------------------------------
# The default module is untouched
# ---------------------------------------------------------------------------


def test_the_default_module_has_no_quizzes(fake_module):
    """The flag is off by default, so every other test sees what it saw.

    Worth asserting rather than assuming: this fixture is what
    test_end_to_end.py drives, and a quiz assessment appearing in it would
    send catch_grades looking for feedback sheets that do not exist.
    """
    module = load_module(fake_module.root)

    assert [a.id for a in module.assessments] == ["cw1", "cw2", "mcq"]
    assert module.grade_sheet_columns[-1] == "MCQ (10)"
    assert fake_module.quiz_exports == {}


def test_the_quiz_module_keeps_the_same_weights(quiz_module):
    """The quiz takes the MCQ's slot rather than joining it, which is what
    keeps every total in `expected` -- and the golden data behind it --
    exactly where it was."""
    module = load_module(quiz_module.root)

    assert [a.id for a in module.assessments] == ["cw1", "cw2", "quizzes"]
    assert [a.weight for a in module.assessments] == [40, 50, 10]
    assert module.grade_sheet_columns[-1] == "Quizzes (10)"


# ---------------------------------------------------------------------------
# What the file records
# ---------------------------------------------------------------------------


def test_the_module_file_records_the_quiz_rules(quiz_module):
    quizzes = load_module(quiz_module.root).assessment("quizzes")

    assert quizzes.pass_mark == 80.0
    assert quizzes.free_passes == 1


def test_the_exports_land_where_the_download_would(quiz_module):
    """A quiz has no submissions to mark, so Brightspace's exports are what
    goes in the submissions folder -- no new path to configure."""
    quizzes = load_module(quiz_module.root).assessment("quizzes")
    exports = sorted(quizzes.submissions_path.glob("*.csv"))

    assert len(exports) == 11
    assert quiz_module.quiz_exports["quizzes"] == exports


def test_a_quiz_assessment_has_no_rubric_or_graders(quiz_module):
    """Nobody marks a quiz. Giving it a feedback sheet and a grader would
    be modelling a workflow that does not happen."""
    quizzes = load_module(quiz_module.root).assessment("quizzes")

    assert quizzes.rubric is None
    assert quizzes.grade_cell is None
    assert quizzes.graders == []


# ---------------------------------------------------------------------------
# Collecting
# ---------------------------------------------------------------------------


def test_marks_are_collected_using_only_what_the_module_records(quiz_module):
    """The call passes no policy at all. If the rules are not in the file,
    this raises rather than quietly using someone else's threshold."""
    module = load_module(quiz_module.root)
    class_list = import_brightspace_classlist(quiz_module.classlist)

    marks = collect_quiz_marks(module.assessment("quizzes"), class_list)

    expected = quiz_module.expected.set_index("Student ID")["mcq"]
    got = marks.set_index("Student ID")["Quizzes (10)"]
    assert got.to_dict() == expected.to_dict()


def test_the_non_participant_is_not_given_the_free_pass(quiz_module):
    """Jack Joyce scored 0 throughout and sat no quiz, so he appears in no
    export at all. The departmental sheet awards him NG rather than F, and
    it can only do that while his total is exactly zero -- one free mark
    here would quietly make him a fail."""
    module = load_module(quiz_module.root)
    class_list = import_brightspace_classlist(quiz_module.classlist)

    marks = collect_quiz_marks(module.assessment("quizzes"), class_list)

    assert marks.set_index("Student ID")["Quizzes (10)"]["23304309"] == 0


def test_full_marks_come_from_ten_of_eleven(quiz_module):
    """Iseult Ivers passes nine and is given the tenth by the free pass.

    The case the ported cell got wrong in the other direction: her mark is
    10, not 10 plus a bonus.
    """
    module = load_module(quiz_module.root)
    class_list = import_brightspace_classlist(quiz_module.classlist)

    marks = collect_quiz_marks(module.assessment("quizzes"), class_list)

    assert marks.set_index("Student ID")["Quizzes (10)"]["23304308"] == 10


def test_the_totals_are_the_same_as_the_mcq_module(quiz_module):
    """The whole point of swapping rather than adding: a student's module
    total does not depend on which shape the fixture was built in."""
    module = load_module(quiz_module.root)
    class_list = import_brightspace_classlist(quiz_module.classlist)
    marks = collect_quiz_marks(module.assessment("quizzes"), class_list)

    merged = quiz_module.expected.merge(marks, on="Student ID")
    totals = excel_round_series(
        merged["cw1"] * 0.4 + merged["cw2"] * 0.5 + merged["Quizzes (10)"]
    )

    assert totals.tolist() == merged["Total % Grade"].tolist()
