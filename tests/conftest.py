#!/usr/bin/env python

import datetime
import pytest
from grader_helper.models import (
    ClassList, GradeFile, Calendar, HandBook, FileType,
    CourseWorkType, CourseWork, Course
)
from grader_helper.dependencies import pl, pd


@pytest.fixture
def resources_dir():
    return pl.Path(__file__).parent / "resources"


@pytest.fixture
def output_dir():
    return pl.Path(__file__).parent / "output"


@pytest.fixture
def example_graders_txt(resources_dir, tmp_path):
    # ensure file exists even if resources/graders.txt isn’t present on CI
    p = resources_dir / "graders.txt"
    if not p.exists():
        resources_dir.mkdir(parents=True, exist_ok=True)
        p.write_text("alice\nbob\ncharlie\n", encoding="utf-8")
    return p


@pytest.fixture
def dummy_coursework_min(tmp_path):
    # create an empty xlsx to act as the class list for minimal CW if needed
    # not used unless tests call load_students()
    (tmp_path / "dummy.xlsx").write_bytes(b"")
    return CourseWork(
        name="Test Assignment",
        root=tmp_path,
        weight=50.0,
        type=CourseWorkType.Assignment,
        due_date=datetime.datetime(2025, 12, 15, 17, 0),
        rubric=tmp_path / "rubric.pdf",
        feedback_sheet=tmp_path / "feedback.xlsx",
        class_list_path=tmp_path / "dummy.xlsx",
    )


@pytest.fixture
def dummy_cw_full(tmp_path, example_graders_txt):
    # real class list Excel with a few rows
    df = pd.DataFrame(
        {"student_id": [101, 102, 103], "name": ["Anna", "Ben", "Cara"]})
    xlsx = tmp_path / "classlist.xlsx"
    df.to_excel(xlsx, index=False)

    cw = CourseWork(
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
        class_list_path=xlsx,
    )
    # tests can call cw.load_students() before assigners
    return cw


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
    # updated: remove 'students', provide class_list_path
    df = pd.DataFrame({"student_id": [101], "name": ["Anna"]})
    xlsx = tmp_path / "cw_dict_classlist.xlsx"
    df.to_excel(xlsx, index=False)
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
        "class_list_path": xlsx,
    }


# path-string fixtures unchanged from earlier suggestion
@pytest.fixture
def existing_xlsx_path_str(tmp_path):
    p = tmp_path / "test.xlsx"
    p.touch()
    return str(p)


@pytest.fixture
def existing_csv_path_str(tmp_path):
    p = tmp_path / "test.csv"
    p.touch()
    return str(p)


@pytest.fixture
def existing_docx_path_str(tmp_path):
    p = tmp_path / "test.docx"
    p.touch()
    return str(p)


@pytest.fixture
def nonexistent_file_path_str(tmp_path):
    return str(tmp_path / "missing.xlsx")


@pytest.fixture
def existing_dir_path_str(tmp_path):
    return str(tmp_path)


@pytest.fixture
def nonexistent_dir_path_str(tmp_path):
    return str(tmp_path / "missing_dir")


@pytest.fixture
def fake_classlist_df():
    """Synthetic Brightspace-style gradebook DataFrame for testing."""
    data = {
        "orgdefinedid": [f"{56000000 + i}" for i in range(1, 21)],
        "username": [f"user{i}" for i in range(1, 21)],
        "last_name": [
            "Smith", "Jones", "Taylor", "Brown", "Williams",
            "Johnson", "Davis", "Miller", "Wilson", "Moore",
            "Anderson", "Thomas", "Jackson", "White", "Harris",
            "Martin", "Thompson", "Garcia", "Martinez", "Robinson"
        ],
        "first_name": [
            "Alice", "Bob", "Charlie", "Diana", "Ethan",
            "Fiona", "George", "Hannah", "Ian", "Julia",
            "Kevin", "Laura", "Michael", "Nina", "Oscar",
            "Paula", "Quinn", "Rachel", "Steven", "Tina"
        ],
        "email": [f"user{i}@studentmail.ul.ie" for i in range(1, 21)],
        "end_of_line_indicator": ["#"] * 20
    }
    return pd.DataFrame(data)
