#!/usr/bin/env python

from pydantic import BaseModel, NonNegativeInt, PositiveFloat, field_validator, ValidationError
from enum import Enum
from ..dependencies import pl
from typing import Self
import datetime


class CourseworkType(Enum):
    Exam = 'exam'
    Assignment = 'assignment'
    Online_MCQ = 'online_mcq'
    InPerson_MCQ = 'inperson_mcq'


class Coursework(BaseModel):
    name: str
    root: pl.Path
    weight: PositiveFloat
    graders: list[str]
    type: CourseworkType
    due_date: datetime.datetime
    rubric: pl.Path
    feedback_sheet: pl.Path


class GradeFile(BaseModel):
    path: pl.Path
    completed: bool


class Calendar(BaseModel):
    path: pl.Path
    complete: bool


class HandBook(BaseModel):
    path: pl.Path
    completed: bool


class Course(BaseModel):
    name: str
    code: str
    root: pl.Path
    model_leader: str
    year: str  # This will be in the format 20xx(xy)
    internal_moderator: str
    handbook: HandBook
    coursework: Coursework | list[Coursework]
    departmental_gradefile: GradeFile

    def set_coursework(self, cw: list[Coursework] | Coursework) -> Self:
        try:
            if isinstance(cw, Coursework):
                self.coursework.append(cw)
            elif isinstance(cw, list):
                self.coursework.extend(cw)
        except Exception as e:
            raise e


def main():
    print("Hello from models.py")

    def test_coursework_creation():
        cw = Coursework(
            name="Essay 1",
            root=pl.Path("/fake/path"),
            weight=50.0,
            graders=["Kev"],
            type=CourseworkType.Assignment,
            due_date=datetime.datetime(2025, 8, 1),
            rubric=pl.Path("/fake/rubric.pdf"),
            feedback_sheet=pl.Path("/fake/feedback.xlsx")
        )
        assert cw.name == "Essay 1"
        assert cw.weight == 50.0
        print("passed")
    test_coursework_creation()


if __name__ == '__main__':
    main()
