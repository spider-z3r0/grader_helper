#!/usr/bin/env python

import pytest
from grader_helper.models import (
    ClassList, GradeFile, Calendar, HandBook, FileType,
    CourseWorkType, CourseWork, Course
)
from grader_helper.dependencies import pl, pd
import datetime


@pytest.fixture
def resources_dir():
    return pl.Path(__file__).parent / "resources"


@pytest.fixture
def output_dir():
    return pl.Path(__file__).parent / "output"


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
def example_graders_txt(resources_dir):
    return resources_dir / "graders.txt"


@pytest.fixture
def dummy_gradefile(resources_dir):
    return GradeFile(
        path=resources_dir / "fake_class_list.xlsx",
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
def dummy_coursework_min():
    return CourseWork(
        name="Test Assignment",
        root=pl.Path("/fake/path/to/coursework"),
        weight=50.0,
        type=CourseWorkType.Assignment,
        due_date=datetime.datetime(2025, 12, 15, 17, 0),
        rubric=pl.Path("/fake/path/to/rubric.pdf"),
        feedback_sheet=pl.Path("/fake/path/to/feedback.xlsx")
    )


@pytest.fixture
def dummy_cw_full(tmp_path):
    return CourseWork(
        name="Advanced Quant Methods",
        root=tmp_path,
        weight=50.0,
        type=CourseWorkType.Exam,
        due_date=datetime.datetime(2025, 11, 30, 13, 0),
        rubric=tmp_path / "rubric.pdf",
        feedback_sheet=tmp_path / "feedback.xlsx",
        graders=["alice", "bob", "charlie"],
        ready=True,
        completed=False,
        students=pd.DataFrame({
            "student_id": [101, 102, 103],
            "name": ["Anna", "Ben", "Cara"],
            "grader": ["alice", "bob", "charlie"]
        })
    )


@pytest.fixture
def dummy_course(dummy_handbook, dummy_gradefile, dummy_classlist):
    return Course(
        name="Intro to Testing",
        code="TS101",
        root=pl.Path("/fake/path/to/course"),
        module_leader="Kevin O'Malley",
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
def dummy_course_full(dummy_cw_full, tmp_path):
    return Course(
        name="Psych 401",
        code="PSY401",
        root=tmp_path,
        module_leader=" Kevin O'Malley",
        year="2025(26)",
        internal_moderator=" Alice Smith",
        ready=True,
        completed=False,
        handbook=HandBook(path=tmp_path / "handbook.pdf", ready=True),
        classlist=ClassList(path=tmp_path / "classlist.xlsx",
                            ready=True, type=FileType.XL),
        departmental_gradefile=GradeFile(
            path=tmp_path / "gradefile.xlsx", ready=True, completed=False, type=FileType.XL),
        coursework=[dummy_cw_full]
    )


@pytest.fixture
def minimal_dummy_course():
    return Course(
        name="Bare Bones Psychology",
        code="PS000",
        root=pl.Path("/path/to/nothing"),
        module_leader="Kevin O'Malley",
        year="2025(26)"
    )


@pytest.fixture
def dummy_course_dict(tmp_path):
    return {
        "name": "Psych 401",
        "code": "PSY401",
        "root": tmp_path,
        "module_leader": "Dr. Kevin O'Malley",
        "year": "2025(26)",
        "internal_moderator": "Dr. Alice Smith",
        "ready": True,
        "completed": False,
        "handbook": {
            "path": tmp_path / "handbook.pdf",
            "ready": True
        },
        "classlist": {
            "path": tmp_path / "classlist.xlsx",
            "type": FileType.XL,
            "ready": True
        },
        "departmental_gradefile": {
            "path": tmp_path / "gradefile.xlsx",
            "type": FileType.XL,
            "ready": True,
            "completed": False
        },
        "coursework": []
    }


@pytest.fixture
def dummy_cw_dict(tmp_path):
    return {
        "name": "Advanced Quant Methods",
        "root": tmp_path,
        "weight": 50.0,
        "type": CourseWorkType.Exam,
        "due_date": datetime.datetime(2025, 11, 30, 13, 0),
        "rubric": tmp_path / "rubric.pdf",
        "feedback_sheet": tmp_path / "feedback.xlsx",
        "graders": ["alice", "bob", "charlie"],
        "ready": True,
        "completed": False,
        "students": pd.DataFrame([
            {"student_id": 101, "name": "Anna", "grader": "alice"},
            {"student_id": 102, "name": "Ben", "grader": "bob"},
            {"student_id": 103, "name": "Cara", "grader": "charlie"}
        ])
    }
