#!usr/bin/env/python

import pytest
from models.Documents import (
    ClassList, GradeFile, Calendar, HandBook, FileType
)
from models.CourseWork import (CourseWorkType, CourseWork)
from models.Course import Course

import datetime
import pathlib as pl

resources = pl.Path(__file__).parent/"resources"


@pytest.fixture
def dummy_classlist():
    return ClassList(
        path=pl.Path("/fake/path/to/classlist.xlsx"),
        type=FileType.XL,
        ready=False
    )


@pytest.fixture
def dummy_handbook():
    return HandBook(
        path=pl.Path("/fake/path/to/handbook.pdf"),
        ready=False

    )


@pytest.fixture
def example_graders_txt():
    return resources/"graders.txt"


@pytest.fixture
def dummy_gradefile():
    return GradeFile(
        path=resources/"fake_class_list.xlsx",
        ready=True,
        completed=False,
        type=FileType.XL
    )


@pytest.fixture
def dummy_calendar():
    return Calendar(
        path=pl.Path("/fake/path/to/calendar.ics"),
        ready=True
    )


@pytest.fixture
def dummy_coursework():
    return CourseWork(
        name="Dummy Assignment",
        root=pl.Path("/fake/path/to/coursework"),
        weight=50.0,
        graders=[],
        students=None,
        type="assignment",
        due_date=datetime.datetime(2025, 8, 1),
        rubric=pl.Path("/fake/path/to/rubric.pdf"),
        ready=False,
        feedback_sheet=pl.Path("/fake/path/to/feedback.xlsx"),
        completed=False
    )


@pytest.fixture
def dummy_course(dummy_handbook, dummy_gradefile, dummy_classlist):
    return Course(
        name="Intro to Testing",
        code="TS101",
        root=pl.Path("/fake/path/to/course"),
        model_leader="Kevin O'Malley",
        year="2025(26)",
        internal_moderator="Alice Smith",
        ready=False,
        handbook=dummy_handbook,
        coursework=[],
        classlist=dummy_classlist,
        departmental_gradefile=dummy_gradefile,
        completed=False
    )


@pytest.fixture
def minimal_dummy_course():
    return Course(
        name="Bare Bones Psychology",
        code="PS000",
        root=pl.Path("/path/to/nothing"),
        model_leader="Kevin O'Malley",
        year="2025(26)"
    )
