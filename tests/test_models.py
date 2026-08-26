#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The module domain model.

The central rule is that an assessment carries two numbers -- what it is
marked out of, and what it contributes -- and every grade-sheet column falls
out of those. That is what lets the code stop inferring a module's shape
from column-name regexes.
"""

import pathlib as pl

import pytest
from pydantic import ValidationError

from grader_helper.models import (
    Assessment,
    AssessmentType,
    Module,
    ModuleFile,
    Person,
)


def make_assessment(**overrides):
    defaults = dict(
        id="cw1",
        type="coursework",
        name="Coursework 1",
        marks_out_of=100,
        weight=40,
    )
    return Assessment(**{**defaults, **overrides})


def make_module(assessments=None, **overrides):
    defaults = dict(
        code="PS4001",
        name="Advanced Research Methods",
        year="2025/26",
        leader="KOM",
        assessments=assessments
        if assessments is not None
        else [make_assessment(weight=100, marks_out_of=100, name="Coursework 1")],
    )
    return Module(**{**defaults, **overrides})


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------


def test_initials_are_upper_cased():
    """They are matched against grader workbook filenames."""
    assert Person(initials="kom").initials == "KOM"


def test_a_person_can_be_written_as_bare_initials():
    module = make_module(leader="kom")
    assert module.leader.initials == "KOM"


def test_bare_initials_serialise_back_to_a_string():
    """So graders = ["KOM"] is not rewritten as a table on save."""
    assert Person(initials="KOM").model_dump() == "KOM"


def test_a_person_with_detail_serialises_as_a_table():
    dumped = Person(initials="KOM", name="Kevin O Malley").model_dump()
    assert dumped == {"initials": "KOM", "name": "Kevin O Malley"}


# ---------------------------------------------------------------------------
# The two-numbers rule
# ---------------------------------------------------------------------------


def test_differing_numbers_give_a_raw_and_a_weighted_column():
    a = make_assessment(marks_out_of=100, weight=40)
    assert a.raw_column == "Coursework 1 (100)"
    assert a.weighted_column == "Coursework 1 (40)"
    assert a.columns == ["Coursework 1 (100)", "Coursework 1 (40)"]


def test_equal_numbers_give_one_column():
    """An MCQ out of 10 worth 10 has nothing to weight.

    This is what the departmental sheet does: MCQ (10) appears once.
    """
    a = make_assessment(id="mcq", type="mcq", name="MCQ", marks_out_of=10, weight=10)
    assert a.weighted_column is None
    assert a.columns == ["MCQ (10)"]
    assert not a.needs_weighting


def test_ten_weekly_quizzes_need_no_extra_field():
    """Each pass is worth 1%, so the mark IS the number passed."""
    a = make_assessment(
        id="quizzes", type="quiz", name="Quizzes", marks_out_of=10, weight=10
    )
    assert a.columns == ["Quizzes (10)"]


def test_weights_render_as_integers():
    """The sheet says (40), not (40.0)."""
    assert make_assessment(weight=40.0).weighted_column == "Coursework 1 (40)"


def test_a_fractional_weight_is_kept():
    assert make_assessment(weight=12.5).weighted_column == "Coursework 1 (12.5)"


def test_weight_fraction_scales_the_raw_mark():
    assert make_assessment(marks_out_of=100, weight=40).weight_fraction() == 0.4
    # Marked out of 50 but worth 25: halved because the scale is halved.
    assert make_assessment(marks_out_of=50, weight=25).weight_fraction() == 0.5


def test_the_departmental_layout_is_reproduced():
    """The exact assessment block of GradeTemplate row 29."""
    module = make_module(
        assessments=[
            make_assessment(id="cw1", name="Coursework 1", marks_out_of=100, weight=40),
            make_assessment(id="cw2", name="Coursework 2", marks_out_of=100, weight=50),
            make_assessment(
                id="mcq", type="mcq", name="MCQ", marks_out_of=10, weight=10
            ),
        ]
    )
    assert module.grade_sheet_columns == [
        "Coursework 1 (100)",
        "Coursework 1 (40)",
        "Coursework 2 (100)",
        "Coursework 2 (50)",
        "MCQ (10)",
    ]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_weights_must_sum_to_one_hundred():
    """The single most valuable check: a wrong total for every student."""
    with pytest.raises(ValidationError, match="sum to"):
        make_module(
            assessments=[
                make_assessment(id="cw1", weight=40),
                make_assessment(id="cw2", name="Coursework 2", weight=50),
            ]
        )


def test_weights_summing_to_one_hundred_are_accepted():
    module = make_module(
        assessments=[
            make_assessment(id="cw1", weight=40),
            make_assessment(id="cw2", name="Coursework 2", weight=60),
        ]
    )
    assert len(module.assessments) == 2


def test_thirds_are_tolerated():
    """33.33 x 3 is 99.99; that is a rounding artefact, not a mistake."""
    module = make_module(
        assessments=[
            make_assessment(id=f"cw{i}", name=f"Coursework {i}", weight=33.33)
            for i in (1, 2, 3)
        ]
    )
    assert len(module.assessments) == 3


def test_duplicate_assessment_ids_are_rejected():
    with pytest.raises(ValidationError, match="[Dd]uplicate"):
        make_module(
            assessments=[
                make_assessment(id="cw1", weight=50),
                make_assessment(id="cw1", name="Coursework 2", weight=50),
            ]
        )


def test_two_assessments_cannot_claim_the_same_column():
    with pytest.raises(ValidationError, match="both produce the column"):
        make_module(
            assessments=[
                make_assessment(id="a", name="Coursework 1", weight=50),
                make_assessment(id="b", name="Coursework 1", weight=50),
            ]
        )


def test_duplicate_graders_are_rejected():
    """Each grader gets one workbook named for them."""
    with pytest.raises(ValidationError, match="more than once"):
        make_assessment(graders=["KOM", "kom"])


def test_a_zero_weight_is_rejected():
    with pytest.raises(ValidationError):
        make_assessment(weight=0)


def test_an_unknown_assessment_type_is_rejected():
    with pytest.raises(ValidationError):
        make_assessment(type="dissertation")


def test_known_types():
    assert {t.value for t in AssessmentType} == {
        "coursework",
        "exam",
        "mcq",
        "quiz",
    }


def test_looking_up_an_unknown_assessment_says_what_exists():
    module = make_module()
    with pytest.raises(KeyError, match="Known ids"):
        module.assessment("nope")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def test_paths_resolve_against_the_module_root(tmp_path):
    module = make_module(root=tmp_path)
    module.paths.classlist = "classlist.csv"
    assert module.classlist_path == (tmp_path / "classlist.csv").resolve()
    assert module.assessments_dir == (tmp_path / "assessments").resolve()


def test_an_assessment_folder_defaults_to_its_id(tmp_path):
    module = make_module(root=tmp_path)
    a = module.assessments[0]
    assert a.folder_path(module.assessments_dir).name == a.id


def test_resolving_without_a_root_says_why():
    module = make_module()
    with pytest.raises(ValueError, match="load_module"):
        _ = module.assessments_dir
