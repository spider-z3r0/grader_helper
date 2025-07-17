#!usr/bin/env python


from grader_helper.models.module import Course, Coursework, GradeFile, HandBook
import datetime
from pathlib import Path


def test_coursework_creation():
    cw = Coursework(
        name="Essay 1",
        root=Path("/fake/path"),
        weight=50.0,
        graders=["Kev"],
        type="assignment",
        due_date=datetime.datetime(2025, 8, 1),
        rubric=Path("/fake/rubric.pdf"),
        feedback_sheet=Path("/fake/feedback.xlsx")
    )
    assert cw.name == "Essay 1"
    assert cw.weight == 50.0
