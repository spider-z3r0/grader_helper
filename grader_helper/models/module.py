#!/usr/bin/env python

from pydantic import BaseModel, NonNegativeInt, PositiveFloat, field_validator

def main():
    print("Hello from models.py")
    a_data = {
                "name":'qual',
                "weight":50.0,
                "graders":['kev']
              }
    c_data = {
        "name": "Advanced empirical psychology",
        "code":"PS40034",
        "model_leader": "Kevin O'Malley",
        "n_coursework":2,
        "n_exam":0,
        "n_quiz":0,
        "assignments": Coursework(**a_data)
    }
    m = Course(**c_data)

    print(m.model_dump_json(indent=2))
    pass


class Coursework(BaseModel):
    name: str
    weight: PositiveFloat
    graders: list[str]

class Exam(BaseModel):
    name: str | None = None
    final: bool
    weight: PositiveFloat

class Quiz(BaseModel):
    pass

class HandBook(BaseModel):
    pass


class Course(BaseModel):
    name: str
    code: str
    model_leader: str
    n_coursework: NonNegativeInt
    n_exam: NonNegativeInt
    n_quiz: NonNegativeInt
    assignments: Coursework |list[Coursework] | None = None
    exams :  Exam | list[Exam] | None = None
    quizzes : Quiz | list[Quiz] | None = None
    


if __name__ == '__main__':
    main()

