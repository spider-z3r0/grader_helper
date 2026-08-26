#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A single piece of assessment within a module.

The central idea is that an assessment carries two numbers:

``marks_out_of``
    what the piece is marked on -- what a grader writes in the feedback
    sheet, and what the student is told they scored.
``weight``
    what it contributes to the module total, out of 100.

Every column in the departmental grade sheet falls out of those two, so the
code no longer has to infer a module's shape by pattern-matching column
names. Where they differ you get a raw column and a weighted one; where they
are equal there is nothing to weight, so there is a single column:

    Coursework 1, out of 100, worth 40  ->  "Coursework 1 (100)"
                                            "Coursework 1 (40)"
    MCQ, out of 10, worth 10            ->  "MCQ (10)"

Ten weekly quizzes, each pass worth 1%, are one assessment marked out of 10
and worth 10: the number of quizzes and the marks available are the same
number, so no separate count is needed.
"""

import pathlib as pl
from enum import Enum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .people import Person, as_person


class AssessmentType(str, Enum):
    """The kinds of assessment a module can carry.

    Deliberately a small closed set -- these are the vocabulary in use. Add
    to it and bump the schema version.
    """

    COURSEWORK = "coursework"
    EXAM = "exam"
    MCQ = "mcq"
    QUIZ = "quiz"


class AssessmentStatus(BaseModel):
    """Where an assessment has got to.

    State, not configuration. Kept beside the assessment rather than in a
    separate table so the file reads as one thing per piece of work.
    """

    model_config = ConfigDict(validate_assignment=True)

    sheets_distributed: bool = False
    graders_allocated: bool = False
    grades_collected: bool = False
    moderated: bool = False


class Assessment(BaseModel):
    """One piece of assessment: its shape, its files and its progress."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    id: str = Field(min_length=1, description="Short stable key, e.g. 'cw1'.")
    type: AssessmentType
    name: str = Field(
        min_length=1,
        description="Display name, and the stem of the grade sheet columns.",
    )
    marks_out_of: float = Field(gt=0, description="What the piece is marked on.")
    weight: float = Field(
        gt=0, le=100, description="Contribution to the module total, out of 100."
    )

    folder: str | None = Field(
        default=None, description="Submissions folder, relative to paths.assessments."
    )
    rubric: str | None = Field(
        default=None, description="Blank feedback sheet, relative to `folder`."
    )
    grade_cell: str | None = Field(
        default=None, description="Cell in the feedback sheet holding the mark."
    )

    graders: list[Person] = Field(default_factory=list)
    group: bool = Field(
        default=False, description="True where the work is submitted by a group."
    )
    due_date: str | None = None

    status: AssessmentStatus = Field(default_factory=AssessmentStatus)

    # ---------------------------------------------------------------- coercion

    @field_validator("graders", mode="before")
    @classmethod
    def _coerce_graders(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, (str, dict)):
            value = [value]
        return [as_person(v) for v in value]

    @model_validator(mode="after")
    def _graders_are_unique(self) -> Self:
        seen = [g.initials for g in self.graders]
        duplicates = {i for i in seen if seen.count(i) > 1}
        if duplicates:
            raise ValueError(
                f"Assessment {self.id!r} lists the same grader more than once: "
                f"{sorted(duplicates)}. Grader initials must be unique, because "
                "each grader gets one workbook named for them."
            )
        return self

    # ------------------------------------------------------------ grade sheet

    @property
    def raw_column(self) -> str:
        """The column holding the mark as awarded, e.g. 'Coursework 1 (100)'."""
        return f"{self.name} ({_tidy(self.marks_out_of)})"

    @property
    def weighted_column(self) -> str | None:
        """The column holding the contribution, e.g. 'Coursework 1 (40)'.

        ``None`` when the piece is already marked on its contribution -- an
        MCQ out of 10 worth 10 needs no second column, which is exactly what
        the departmental sheet does.
        """
        if self.marks_out_of == self.weight:
            return None
        return f"{self.name} ({_tidy(self.weight)})"

    @property
    def columns(self) -> list[str]:
        """The assessment's columns, raw first, in grade-sheet order."""
        weighted = self.weighted_column
        return [self.raw_column] if weighted is None else [self.raw_column, weighted]

    @property
    def needs_weighting(self) -> bool:
        return self.weighted_column is not None

    def weight_fraction(self) -> float:
        """The multiplier taking a raw mark to its contribution.

        A coursework marked out of 100 and worth 40 scales by 0.4. One marked
        out of 50 and worth 25 also scales by 0.5 -- the mark is halved
        because the scale is, not because the weight is.
        """
        return self.weight / self.marks_out_of

    # ------------------------------------------------------------------ paths

    def folder_path(self, assessments_root: pl.Path) -> pl.Path:
        """Where this assessment's submissions live."""
        return assessments_root / (self.folder or self.id)

    def rubric_path(self, assessments_root: pl.Path) -> pl.Path | None:
        if self.rubric is None:
            return None
        return self.folder_path(assessments_root) / self.rubric


def _tidy(value: float) -> str:
    """Render a weight the way the grade sheet does: 40, not 40.0."""
    return str(int(value)) if float(value).is_integer() else str(value)
