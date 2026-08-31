#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A taught module: who runs it, what it is assessed by, and where its files are.

Paths in ``module.toml`` are stored relative to the file itself, and the
module root is the file's own directory. Nothing absolute is written down.
That is deliberate: these modules live under OneDrive, where the absolute
path differs between machines and accounts, so an absolute root would break
the moment a colleague opened the file or the folder re-synced elsewhere.
"""

import pathlib as pl
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .assessment import Assessment
from .people import Person, as_person

#: Bumped whenever the on-disk shape changes incompatibly.
SCHEMA_VERSION = 1

#: Tolerance on the weights-sum check.
#:
#: Three equal components written as 33.33 sum to 99.99, and float error
#: puts that fractionally over a 0.01 tolerance. 0.1 accepts any sensible
#: rounding of a repeating fraction while still catching real mistakes,
#: which are off by whole points -- 40 + 50 = 90, or 40 + 50 + 20 = 110.
WEIGHT_TOLERANCE = 0.1


class ModulePaths(BaseModel):
    """Where things sit, relative to the module root."""

    model_config = ConfigDict(str_strip_whitespace=True)

    assessments: str = "assessments"
    classlist: str | None = None
    departmental_sheet: str | None = None
    #: The department's blank workbook, which `build_departmental_sheet` lays
    #: out for this module's assessments. It is the department's file and it
    #: changes year to year, so a module keeps its own copy rather than the
    #: package shipping one and quietly using last year's.
    departmental_template: str | None = None
    #: The upload file the student information system issues, which we fill
    #: two columns of and hand back. Named by SI, not by us.
    si_file: str | None = None


class ModuleStatus(BaseModel):
    """Where the module as a whole has got to.

    Assessment-level state lives on :class:`AssessmentStatus`; these are the
    things produced once for the module -- the departmental sheet, the
    moderation pack, the SI upload.

    **The split running through both is what the code can honestly know.** A
    step can tell that it produced a file; whether that file was then sent,
    read or accepted is in somebody's head and never on disk. So each artefact
    has an automatic flag and, where a person has to do something with it, a
    manual one beside it:

    ==============================  ============================
    set by the code, from evidence  set by a person
    ==============================  ============================
    ``departmental_sheet_written``  ``sent_to_department``
    ``moderation_pack_built``       (per assessment: ``moderated``)
    ``si_file_written``             ``si_submitted``
    ==============================  ============================

    The automatic ones are set by :meth:`ModuleFile.record` from what a step
    returned, **not** from its having failed to raise -- see
    :mod:`grader_helper.recording`. The manual ones are a button in the
    dashboard, or `set_status` from a notebook.
    """

    model_config = ConfigDict(validate_assignment=True)

    # --- the code can see these happen -----------------------------------
    departmental_sheet_written: bool = False
    moderation_pack_built: bool = False
    si_file_written: bool = False

    # --- only a person knows these ---------------------------------------
    #: The sheet reached the department. We wrote a file; we cannot know it
    #: was sent.
    sent_to_department: bool = False
    #: The upload was actually lodged with SI, which happens outside this
    #: package entirely.
    si_submitted: bool = False


class Module(BaseModel):
    """A module and everything needed to run its assessment."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    schema_version: int = SCHEMA_VERSION
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    year: str = Field(min_length=1, description='Academic year, e.g. "2025/26".')

    leader: Person
    internal_moderator: Person | None = None

    paths: ModulePaths = Field(default_factory=ModulePaths)
    assessments: list[Assessment] = Field(default_factory=list)
    status: ModuleStatus = Field(default_factory=ModuleStatus)

    #: The directory holding module.toml. Populated on load, never written
    #: back -- see the module docstring.
    root: pl.Path | None = Field(default=None, exclude=True)

    # ---------------------------------------------------------------- coercion

    @model_validator(mode="before")
    @classmethod
    def _coerce_people(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for key in ("leader", "internal_moderator"):
            if data.get(key) is not None:
                data[key] = as_person(data[key])
        return data

    # -------------------------------------------------------------- validation

    @model_validator(mode="after")
    def _assessment_ids_are_unique(self) -> Self:
        ids = [a.id for a in self.assessments]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(
                f"Duplicate assessment id(s): {sorted(duplicates)}. Each "
                "assessment needs its own id, since it keys the folder and "
                "the status."
            )
        return self

    @model_validator(mode="after")
    def _weights_sum_to_one_hundred(self) -> Self:
        """The single most valuable check in the file.

        A module whose weights do not sum to 100 produces a wrong total for
        every student, and the error is invisible until the marks are
        audited. Catching it when the module is configured costs nothing.
        """
        if not self.assessments:
            return self

        total = sum(a.weight for a in self.assessments)
        if abs(total - 100) > WEIGHT_TOLERANCE:
            breakdown = "\n".join(
                f"  {a.name}: {a.weight}" for a in self.assessments
            )
            raise ValueError(
                f"Assessment weights sum to {total}, not 100:\n{breakdown}\n"
                "Every student's total would be wrong. Fix the weights in "
                "module.toml before allocating any marking."
            )
        return self

    @model_validator(mode="after")
    def _assessments_know_where_they_live(self) -> Self:
        """Push the assessments directory down into each assessment.

        An Assessment holds relative names only, so on its own it cannot turn
        them into paths -- nothing in it knows where the module sits. Binding
        here is what lets `a.submissions_path` be a plain property instead of
        a method every call site has to hand the root to.

        Skipped when there is no root: a Module built in memory for validation
        is still perfectly valid, it just cannot resolve paths yet.
        """
        if self.root is not None:
            for assessment in self.assessments:
                assessment.bind(self.assessments_dir)
        return self

    @model_validator(mode="after")
    def _column_names_are_unique(self) -> Self:
        """Two assessments must not claim the same grade-sheet column."""
        seen: dict[str, str] = {}
        for assessment in self.assessments:
            for column in assessment.columns:
                if column in seen:
                    raise ValueError(
                        f"Assessments {seen[column]!r} and {assessment.id!r} "
                        f"both produce the column {column!r}. Give them "
                        "different names."
                    )
                seen[column] = assessment.id
        return self

    # ------------------------------------------------------------------ lookup

    def assessment(self, assessment_id: str) -> Assessment:
        """Fetch one assessment by id."""
        for a in self.assessments:
            if a.id == assessment_id:
                return a
        raise KeyError(
            f"No assessment {assessment_id!r} in module {self.code}. "
            f"Known ids: {[a.id for a in self.assessments]}"
        )

    # ------------------------------------------------------------------- paths

    def _resolve(self, relative: str | None) -> pl.Path | None:
        if relative is None:
            return None
        if self.root is None:
            raise ValueError(
                "This module has no root, so relative paths cannot be "
                "resolved. Load it with load_module() rather than "
                "constructing it directly, or set .root yourself."
            )
        return (self.root / relative).resolve()

    @property
    def assessments_dir(self) -> pl.Path:
        resolved = self._resolve(self.paths.assessments)
        assert resolved is not None  # paths.assessments has a default
        return resolved

    @property
    def classlist_path(self) -> pl.Path | None:
        return self._resolve(self.paths.classlist)

    @property
    def departmental_sheet_path(self) -> pl.Path | None:
        return self._resolve(self.paths.departmental_sheet)

    @property
    def departmental_template_path(self) -> pl.Path | None:
        return self._resolve(self.paths.departmental_template)

    @property
    def si_file_path(self) -> pl.Path | None:
        """SI's own upload file, if the module records one."""
        return self._resolve(self.paths.si_file)

    # ------------------------------------------------------------- grade sheet

    @property
    def directories(self) -> list[pl.Path]:
        """Every directory this module needs on disk, outermost first.

        What init_module creates, and what a dashboard would check for before
        offering to run anything.
        """
        wanted = [self.root, self.assessments_dir] if self.root else []
        for assessment in self.assessments:
            wanted.extend(assessment.directories)
        return wanted

    @property
    def grade_sheet_columns(self) -> list[str]:
        """Every assessment column, in declared order.

        The departmental sheet puts Name and Student ID first and the
        derived columns last; this is just the assessment block in between.
        """
        return [column for a in self.assessments for column in a.columns]
