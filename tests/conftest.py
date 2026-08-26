#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Shared fixtures for the grader_helper test suite.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl
import sys

import pytest

REPO_ROOT = pl.Path(__file__).parent.parent


@pytest.fixture
def repo_root() -> pl.Path:
    """The repository root, i.e. the directory holding pyproject.toml."""
    return REPO_ROOT


@pytest.fixture
def resources_dir() -> pl.Path:
    """Static test assets that ship with the suite."""
    return pl.Path(__file__).parent / "resources"


@pytest.fixture
def feedback_sheet_tree(tmp_path) -> pl.Path:
    """A minimal submissions tree containing one feedback sheet.

    The files are empty -- these fixtures exist to exercise the *discovery*
    and *delegation* logic, not the Excel reading itself. Tests that need
    real workbooks are marked ``excel``.
    """
    student = tmp_path / "OMALLEY, KEVIN(12345678)"
    student.mkdir()
    (student / "Feedback sheet 12345678.xlsx").write_bytes(b"")
    return tmp_path


def pytest_report_header(config):
    return f"grader_helper: platform={sys.platform}"


# ---------------------------------------------------------------------------
# Fake Brightspace submissions
# ---------------------------------------------------------------------------
#
# Real folder name, confirmed against a live download:
#
#     "27236-46025 - 23304308 Angood - 05 March 2026 612 PM"
#      |             |        |        |
#      |             |        |        submission timestamp
#      |             |        student surname
#      |             student ID  <-- everything orients on this
#      Brightspace's own id, changes per assignment
#
# The student ID is the first token after the first " - ".

ASSIGNMENT_ID = "27236-46025"


def brightspace_folder_name(
    student_id: str,
    last_name: str,
    when: str = "05 March 2026 612 PM",
    assignment_id: str = ASSIGNMENT_ID,
) -> str:
    """Build a folder name in Brightspace's download format."""
    return f"{assignment_id} - {student_id} {last_name} - {when}"


@pytest.fixture
def fake_students():
    """A deterministic cohort: list of (student_id, first, last)."""
    from faker import Faker

    fake = Faker("en_IE")
    Faker.seed(20260305)
    return [
        (f"2330{4300 + i}", fake.first_name(), fake.last_name())
        for i in range(6)
    ]


@pytest.fixture
def classlist(fake_students):
    """The class list frame as import_brightspace_classlist would return it."""
    import pandas as pd

    return pd.DataFrame(
        {
            "Student ID": [sid for sid, _, _ in fake_students],
            "Last Name": [last for _, _, last in fake_students],
            "First Name": [first for _, first, _ in fake_students],
            "Score": [""] * len(fake_students),
        }
    )


@pytest.fixture
def brightspace_tree(tmp_path, fake_students):
    """An unzipped Brightspace download: one folder per student."""
    subs = tmp_path / "Assignment 1 Download 05 March 2026"
    subs.mkdir()
    for i, (sid, _, last) in enumerate(fake_students):
        when = f"0{i + 1} March 2026 {600 + i * 11} PM"
        (subs / brightspace_folder_name(sid, last, when)).mkdir()
    return subs


@pytest.fixture
def folder_name():
    """The Brightspace folder-name builder, for tests that add submissions."""
    return brightspace_folder_name


# ---------------------------------------------------------------------------
# Modules
# ---------------------------------------------------------------------------
#
# The grade-sheet functions are told a module's shape rather than inferring it
# from column names, so most of them need a Module. These build one without
# each test restating the parts it does not care about.


def make_assessment(**overrides):
    """One assessment, defaulting to Coursework 1 out of 100 worth 40."""
    from grader_helper.models import Assessment

    defaults = dict(
        id="cw1",
        type="coursework",
        name="Coursework 1",
        marks_out_of=100,
        weight=40,
    )
    return Assessment(**{**defaults, **overrides})


def make_module(assessments=None, **overrides):
    """A module, defaulting to one coursework worth the whole 100."""
    from grader_helper.models import Module

    defaults = dict(
        code="PS4001",
        name="Advanced Research Methods",
        year="2025/26",
        leader="KOM",
        assessments=assessments
        if assessments is not None
        else [make_assessment(weight=100)],
    )
    return Module(**{**defaults, **overrides})


#: The module the 2026 departmental sample data describes: two courseworks
#: marked out of 100 and worth 40 and 50, and an MCQ marked out of 10 and
#: worth 10. The MCQ is the case that matters -- marked on its own
#: contribution, so it has one column, and it is the component the old
#: "Coursework"-substring code dropped from every total.
DEPARTMENTAL_ASSESSMENTS = [
    dict(id="cw1", type="coursework", name="Coursework 1", marks_out_of=100, weight=40),
    dict(id="cw2", type="coursework", name="Coursework 2", marks_out_of=100, weight=50),
    dict(id="mcq", type="mcq", name="MCQ", marks_out_of=10, weight=10),
]


@pytest.fixture
def departmental_module():
    """The module behind tests/resources/gradetemplate_samples.csv."""
    return make_module(
        assessments=[make_assessment(**spec) for spec in DEPARTMENTAL_ASSESSMENTS]
    )


@pytest.fixture
def two_coursework_module():
    """Two courseworks out of 100, worth 40 and 60."""
    return make_module(
        assessments=[
            make_assessment(id="cw1", name="Coursework 1", weight=40),
            make_assessment(id="cw2", name="Coursework 2", weight=60),
        ]
    )


@pytest.fixture
def fake_module(tmp_path):
    """A whole module on disk: class list, submissions, marked feedback sheets.

    See tests/fake_module.py. The feedback sheets are real workbooks with
    real numbers in them, so this exercises the Excel reading that mocked
    fixtures skip.
    """
    from fake_module import make_fake_module

    return make_fake_module(tmp_path / "PS4001")
