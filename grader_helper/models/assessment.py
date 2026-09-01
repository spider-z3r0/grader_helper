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

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

from .people import Person, as_person

#: What ``build_group_membership`` writes into ``grading_output``. CSV rather
#: than xlsx because it is a two-column lookup table that wants reading in a
#: diff, not a workbook.
GROUP_MEMBERSHIP_FILENAME = "group_membership.csv"


class AssessmentType(str, Enum):
    """The kinds of assessment a module can carry.

    Deliberately a small closed set -- these are the vocabulary in use. Add
    to it and bump the schema version.
    """

    COURSEWORK = "coursework"
    EXAM = "exam"
    MCQ = "mcq"
    QUIZ = "quiz"


#: The types whose marks are collected from Brightspace's own exports, and
#: so the only ones for which ``pass_mark`` and ``free_passes`` mean
#: anything. Named rather than left inline in the validator so that a form
#: offering those fields and the model accepting them cannot drift apart.
COLLECTED_TYPES = (AssessmentType.QUIZ, AssessmentType.MCQ)


class GroupSource(str, Enum):
    """Where a group assessment's group membership comes from.

    The two kinds look nothing like each other on disk, and neither is
    guessable from the download, so the module has to say which it is.

    ``BRIGHTSPACE``
        The groups were made in Brightspace. They arrive **in the class
        list**, as a group column, and the download has **one folder per
        group** -- one feedback sheet, one mark, shared by the whole team.

    ``MODULE_LEADER``
        The groups were made by the module leader, in sheets of their own.
        They have to be collected into one student-id-to-group table before
        anything can be allocated. The download is the *individual* shape --
        one folder per student, one feedback sheet each, and marks that may
        legitimately differ within a group.

    So the flag decides two separate things: where membership is read from,
    and whether a mark belongs to a team or to a person. Defaulting it would
    mean guessing at both.
    """

    BRIGHTSPACE = "brightspace"
    MODULE_LEADER = "module_leader"


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
        default=None,
        description="This assessment's own folder, relative to paths.assessments. "
        "Defaults to the assessment id.",
    )
    submissions: str = Field(
        default="submissions",
        description="The unzipped Brightspace download, relative to `folder`.",
    )
    grading_output: str = Field(
        default="grading_output",
        description="Everything the tool writes -- grader workbooks and the "
        "combined grades -- relative to `folder`. Safe to delete and regenerate.",
    )
    rubric: str | None = Field(
        default=None, description="Blank feedback sheet, relative to `folder`."
    )
    grade_cell: str | None = Field(
        default=None, description="Cell in the feedback sheet holding the mark."
    )

    graders: list[Person] = Field(default_factory=list)
    due_date: str | None = None

    # ---------------------------------------------------------- group policy
    group: bool = Field(
        default=False, description="True where the work is submitted by a group."
    )
    group_source: GroupSource | None = Field(
        default=None,
        description="Where group membership comes from: 'brightspace' (a "
        "column in the class list, one submission folder per group) or "
        "'module_leader' (sheets of the leader's own, one submission folder "
        "per student). Required when group is true.",
    )
    group_sheets: str = Field(
        default="groups",
        description="Where the module leader's own group sheets are, relative "
        "to `folder`: a folder of them, or one file holding the lot. A name "
        "with a suffix is taken to be a file. Only read for "
        "group_source = 'module_leader'.",
    )
    group_column: str | list[str] | None = Field(
        default=None,
        description="Which column holds the group, where more than one could "
        "and they disagree. A list composes one key from several columns: "
        "['Grp Code', 'Team'] over 2A and 1 gives '2A_1'. Left unset the "
        "column is found automatically, and an ambiguity is refused rather "
        "than guessed at.",
    )

    # --------------------------------------------------------- quiz policy
    #
    # Flat scalars rather than a [assessment.quiz] sub-table, deliberately.
    # The file writer's one real hazard is that a scalar written after a
    # sub-table is parsed *into* that sub-table -- see the comment in
    # init_module about where [module.leader] has to go -- and flat keys
    # cannot trip it.
    pass_mark: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Percentage a single quiz must exceed to count as passed. "
        "Strictly above: at 80 a score of exactly 80 has failed. 0 is "
        "meaningful and legal -- it means any score above nothing passes, "
        "i.e. the quiz is an engagement mark.",
    )
    free_passes: int = Field(
        default=0,
        ge=0,
        description="Quizzes a student may fail without losing a mark. Added "
        "to the count of passes, then capped at marks_out_of.",
    )

    status: AssessmentStatus = Field(default_factory=AssessmentStatus)

    #: Where ``paths.assessments`` resolves to, pushed down by Module on load.
    #:
    #: A PrivateAttr rather than a Field(exclude=True): private attributes are
    #: left out of serialisation automatically, so round-tripping module.toml
    #: cannot accidentally start writing an absolute path into a file that is
    #: deliberately all relative.
    _assessments_root: pl.Path | None = PrivateAttr(default=None)

    def bind(self, assessments_root: pl.Path) -> "Assessment":
        """Tell this assessment where the assessments directory is.

        Called by Module once its own root is known. Without it an assessment
        cannot resolve its own paths, because nothing else in the object knows
        where on disk the module lives.
        """
        self._assessments_root = assessments_root
        return self

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

    @model_validator(mode="after")
    def _a_group_assessment_says_which_kind(self) -> Self:
        """`group = true` on its own does not say enough to act on.

        The two kinds differ in where membership is read from *and* in
        whether a mark belongs to a team or a person, so a default would be
        guessing at both -- and both guesses fail late and quietly. A
        Brightspace-managed run against a per-student download simply finds
        no group folders and distributes nothing; a leader-managed run
        against a class list that already has the groups goes looking for
        sheets that were never written.
        """
        if self.group and self.group_source is None:
            raise ValueError(
                f"Assessment {self.id!r} is a group assessment but does not "
                "say where its groups come from. Set group_source:\n"
                "  group_source = \"brightspace\"     groups made in "
                "Brightspace -- they appear as a column in the class list, "
                "and the download has one folder, one feedback sheet and one "
                "mark per group\n"
                "  group_source = \"module_leader\"   groups made by you, in "
                "sheets of your own -- the download is the individual shape, "
                "one folder and one feedback sheet per student, and marks may "
                "differ within a group"
            )
        if self.group_column is not None and not self.group:
            raise ValueError(
                f"Assessment {self.id!r} sets group_column but group is "
                "false, so nothing would read it. There is no group to find "
                "a column for."
            )
        if self.group_source is not None and not self.group:
            raise ValueError(
                f"Assessment {self.id!r} sets group_source = "
                f"{self.group_source.value!r} but group is false, so nothing "
                "would read it. Set group = true, or drop group_source."
            )
        return self

    @model_validator(mode="after")
    def _quiz_policy_belongs_to_a_quiz(self) -> Self:
        """`pass_mark` and `free_passes` only mean something for a quiz.

        On a coursework a "pass mark" reads as a compensation threshold,
        which is a different thing entirely and is not what this package
        would do with it. Refusing is cheaper than the conversation about
        why a coursework's pass mark had no effect.
        """
        collected = COLLECTED_TYPES
        if self.type in collected:
            return self

        set_here = [
            name
            for name, value in (
                ("pass_mark", self.pass_mark),
                ("free_passes", self.free_passes or None),
            )
            if value is not None
        ]
        if set_here:
            raise ValueError(
                f"Assessment {self.id!r} is a {self.type.value} but sets "
                f"{set_here}. Those describe how a mark is collected from "
                "Brightspace quiz exports, so they belong to an assessment "
                f"of type {[t.value for t in collected]}. A pass mark on a "
                "coursework is a compensation threshold, which this package "
                "does not implement."
            )
        return self

    @model_validator(mode="after")
    def _free_passes_leave_something_to_earn(self) -> Self:
        """Forgiving as many quizzes as there are marks awards them all.

        Every student takes full marks without sitting anything, and the
        result is a plausible number rather than an error -- which is the
        failure mode this package spends most of its guards on.
        """
        if self.free_passes and self.free_passes >= self.marks_out_of:
            raise ValueError(
                f"Assessment {self.id!r} gives {self.free_passes} free "
                f"pass(es) but is marked out of {self.marks_out_of}, so "
                "every student would take full marks without passing a "
                "single quiz. free_passes must be fewer than marks_out_of."
            )
        return self

    # ------------------------------------------------------------ grade sheet

    @property
    def raw_column(self) -> str:
        """The column holding the mark as awarded, e.g. 'Coursework 1 (100)'."""
        return f"{self.name} ({tidy_number(self.marks_out_of)})"

    @property
    def weighted_column(self) -> str | None:
        """The column holding the contribution, e.g. 'Coursework 1 (40)'.

        ``None`` when the piece is already marked on its contribution -- an
        MCQ out of 10 worth 10 needs no second column, which is exactly what
        the departmental sheet does.
        """
        if self.marks_out_of == self.weight:
            return None
        return f"{self.name} ({tidy_number(self.weight)})"

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

    def _root(self) -> pl.Path:
        if self._assessments_root is None:
            raise ValueError(
                f"Assessment {self.id!r} does not know where it lives, so its "
                "paths cannot be resolved. Reach it through a module loaded "
                "with load_module() or ModuleFile.load(), which binds it, "
                "rather than constructing it on its own."
            )
        return self._assessments_root

    @property
    def folder_path(self) -> pl.Path:
        """This assessment's own folder, inside the assessments directory."""
        return self._root() / (self.folder or self.id)

    @property
    def submissions_path(self) -> pl.Path:
        """The unzipped Brightspace download."""
        return self.folder_path / self.submissions

    @property
    def grading_output_path(self) -> pl.Path:
        """Where the tool writes: grader workbooks and the combined grades."""
        return self.folder_path / self.grading_output

    @property
    def rubric_path(self) -> pl.Path | None:
        """The blank feedback sheet, or None if this assessment has no rubric."""
        if self.rubric is None:
            return None
        return self.folder_path / self.rubric

    @property
    def group_sheets_path(self) -> pl.Path | None:
        """The leader's own group sheets, or None where there are none.

        A folder of sheets or a single file, whichever ``group_sheets``
        names -- ``collect_group_membership`` reads either, and a leader who
        keeps every team in one workbook is at least as common as one who
        keeps a file per team.

        ``None`` unless ``group_source = "module_leader"``: a
        Brightspace-managed group assessment reads its membership from the
        class list, so a place to put group sheets would be a place nothing
        ever puts anything.
        """
        if self.group_source is not GroupSource.MODULE_LEADER:
            return None
        return self.folder_path / self.group_sheets

    @property
    def group_sheets_is_file(self) -> bool:
        """Whether ``group_sheets`` names one file rather than a folder.

        By its suffix, not by what is on disk: this has to answer before the
        file exists, because ``init_module`` uses it to decide what to
        create, and creating a *directory* called ``groups.xlsx`` is a mess
        to undo.
        """
        return bool(pl.PurePath(self.group_sheets).suffix)

    @property
    def group_membership_path(self) -> pl.Path | None:
        """The collected student-id-to-group table, or None where there is none.

        Written by ``build_group_membership``, and derived entirely from the
        sheets in ``group_sheets``, so it lives in ``grading_output`` with
        everything else that can be deleted and regenerated.
        """
        if self.group_source is not GroupSource.MODULE_LEADER:
            return None
        return self.grading_output_path / GROUP_MEMBERSHIP_FILENAME

    @property
    def directories(self) -> tuple[pl.Path, ...]:
        """Every directory this assessment needs, for init_module to create."""
        wanted = [self.folder_path, self.submissions_path, self.grading_output_path]
        sheets = self.group_sheets_path
        # A folder to put the sheets in, yes. A folder *named* groups.xlsx,
        # no -- that is a file the leader already has, and creating a
        # directory over the top of its name is a mess to undo.
        if sheets is not None and not self.group_sheets_is_file:
            wanted.append(sheets)
        return tuple(wanted)


def tidy_number(value: float) -> str:
    """Render a number the way the grade sheet does: 40, not 40.0.

    Shared with the sheet builder, which puts the same two numbers into the
    weighting formula -- ``=C30/100*40``. The column header and the formula
    that reads it have to agree, so they render through one function.
    """
    return str(int(value)) if float(value).is_integer() else str(value)
