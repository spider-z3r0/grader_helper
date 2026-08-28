#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Bring a whole module's marks into one frame.

Every other step in this package works on **one** assessment. This is the
one that works on the module: it walks the assessments, fetches each one's
marks from wherever that kind of assessment keeps them, and returns a single
frame ready for :func:`prepare_data_for_departmental_template`.

It lives at the top level rather than inside ``dataframe_operations``
because it is the assembly layer -- it reaches into ``ingesting`` and
``file_operations``, and ``dataframe_operations`` deliberately depends on
nothing but ``models``.

House convention::

    import pathlib as pl        # pl is pathlib
    import polars as pr         # pr is polars

**Where a mark comes from is decided by what the assessment has, not by what
type it is.** That distinction matters: an MCQ sat in Brightspace is
collected from quiz exports, an MCQ sat in a lecture theatre is typed in by
hand, and an MCQ marked on a feedback sheet is read off the sheet -- all
three are ``type = "mcq"``. Asking what the assessment *has* answers the
question; asking what it *is* does not. In order:

1. **Marks handed in** through ``marks=``. The in-person MCQ, and the
   override for anything this package cannot reach.
2. **A grade cell**, meaning the feedback-sheet workflow -- read from
   whichever record ``source`` names. Checked before the folder is looked
   at, because an assessment that says where its mark sits has already
   answered the question.
3. **Quiz exports** in the submissions folder -- collected with
   :func:`collect_quiz_marks`, using the rules recorded on the assessment.
4. **Nothing.** The column is created, left empty, and named in a warning.
   An assessment that quietly vanished would take a component out of every
   total, and a total missing a component is still a plausible number.

The two records
---------------

A marked coursework exists in two places, and they mean different things:

``source="collated"``
    ``completed_grades.xlsx`` -- what the **department** receives, written
    by ``ingest_completed_graderfiles``.
``source="feedback"``
    The feedback sheets -- what the **students** received, read by
    ``catch_grades``.

Step 7 of the lifecycle reconciles the two, and they must agree. Because
they must agree, it is tempting to let this function fall back from one to
the other when a file is missing. It does not: the fallback would be
invisible, and "the record I meant was not there so I used the other one" is
exactly the class of silent substitution this package spends its guards on.
A missing collated file raises and names both ways out.
"""

import pathlib as pl
import warnings

import pandas as pd

from .file_operations.catch_grades import catch_grades
from .ingesting.collect_quiz_marks import collect_quiz_marks
from .models import Assessment, Module

#: CSVs this package itself writes into a submissions folder, which are
#: therefore not quiz exports. ``alphabetise_folders`` leaves its rename log
#: exactly there -- it is the handoff to ``brightspace_name_folders`` -- so a
#: coursework that has been alphabetised has a .csv sitting beside the
#: submission folders.
NOT_QUIZ_EXPORTS = ("folder_rename_log.csv",)

#: What ``ingest_completed_graderfiles(save=True)`` writes, in either format.
COLLATED_STEMS = ("completed_grades.xlsx", "completed_grades.csv")

#: The column the grader writes their mark into, in the grader workbooks and
#: so in the collated file.
MARK_COLUMN = "Mark"

#: Where marks may be read from. Not a default that can be fallen back to --
#: see this module's docstring.
SOURCES = ("collated", "feedback")


def _read_ids_as_text(path: pl.Path) -> pd.DataFrame:
    """Read a collated grade file, keeping the student id as text.

    ``'00123456'`` left to pandas comes back ``123456``, and the merge
    against the class list then matches nothing.
    """
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype={"Student ID": str})
    return pd.read_excel(path, dtype={"Student ID": str})


def _collated_file(assessment: Assessment) -> pl.Path:
    """The one collated grade file for this assessment.

    Raises
    ------
    ValueError
        If there are two. ``ingest_completed_graderfiles`` writes .xlsx or
        .csv depending on how it was called, and finding both means two
        records of the department's marks with no way to tell which is
        current. Same refusal as two exports for one quiz, for the same
        reason.
    FileNotFoundError
        If there is none, naming both ways forward.
    """
    found = [
        assessment.grading_output_path / stem
        for stem in COLLATED_STEMS
        if (assessment.grading_output_path / stem).exists()
    ]
    if len(found) > 1:
        raise ValueError(
            f"Assessment {assessment.id!r} has two collated grade files: "
            f"{[p.name for p in found]}. Which one is the department's record "
            "is not something to guess -- delete the stale one."
        )
    if not found:
        raise FileNotFoundError(
            f"No collated grades for assessment {assessment.id!r}: expected "
            f"one of {list(COLLATED_STEMS)} in "
            f"{assessment.grading_output_path}. Either run "
            "ingest_completed_graderfiles(..., save=True) to write it, or "
            "pass source='feedback' to read the marks the students received "
            "instead -- but those are two different records, so say which "
            "you mean."
        )
    return found[0]


def _from_collated(assessment: Assessment) -> pd.DataFrame:
    frame = _read_ids_as_text(_collated_file(assessment))
    missing = [c for c in ("Student ID", MARK_COLUMN) if c not in frame.columns]
    if missing:
        raise ValueError(
            f"The collated grades for {assessment.id!r} have no {missing}. "
            f"Columns present: {list(frame.columns)}. A grader's workbook "
            f"gets its {MARK_COLUMN!r} column when the marks are copied in; "
            "this file looks like it was collated before that happened."
        )
    return frame[["Student ID", MARK_COLUMN]].rename(
        columns={MARK_COLUMN: assessment.raw_column}
    )


def _from_feedback(assessment: Assessment) -> pd.DataFrame:
    if assessment.grade_cell is None:
        raise ValueError(
            f"Assessment {assessment.id!r} has no grade_cell, so there is no "
            "cell to read a mark out of. Set grade_cell in module.toml."
        )
    return catch_grades(assessment.submissions_path, assessment.grade_cell).rename(
        columns={"grade": assessment.raw_column}
    )


def _supplied(assessment: Assessment, given) -> pd.DataFrame:
    """Marks handed in by the caller, as a frame or a mapping."""
    if isinstance(given, pd.DataFrame):
        if "Student ID" not in given.columns:
            raise ValueError(
                f"The marks given for {assessment.id!r} have no 'Student ID' "
                f"column. Columns present: {list(given.columns)}"
            )
        others = [c for c in given.columns if c != "Student ID"]
        if len(others) != 1:
            raise ValueError(
                f"The marks given for {assessment.id!r} must have exactly one "
                f"column of marks beside 'Student ID', not {others}."
            )
        frame = given[["Student ID", others[0]]].copy()
    else:
        frame = pd.DataFrame(
            {"Student ID": list(given.keys()), "mark": list(given.values())}
        )
    frame.columns = ["Student ID", assessment.raw_column]
    frame["Student ID"] = frame["Student ID"].astype(str)
    return frame


def _has_quiz_exports(assessment: Assessment) -> bool:
    """Whether the submissions folder holds Brightspace quiz exports.

    Not simply "are there CSVs here": ``alphabetise_folders`` writes
    ``folder_rename_log.csv`` into this very folder, so every alphabetised
    coursework has one. Reading that as a quiz export sends a coursework
    down the quiz path, where it fails complaining about a pass mark -- an
    error about the wrong assessment entirely.
    """
    submissions = assessment.submissions_path
    return submissions.exists() and any(
        p.suffix.lower() == ".csv" and p.name not in NOT_QUIZ_EXPORTS
        for p in submissions.iterdir()
    )


def collate_module_marks(
    module: Module,
    class_list: pd.DataFrame,
    source: str = "collated",
    marks: dict | None = None,
) -> pd.DataFrame:
    """Every assessment's marks, in one frame, one row per enrolled student.

    Parameters
    ----------
    module
        The module. Its assessments decide both what to fetch and what the
        columns are called -- see ``Assessment.raw_column``.
    class_list
        As ``import_brightspace_classlist`` returns it. **This decides the
        cohort**: every student in it gets a row, whether or not they
        submitted anything.
    source
        Which record to read a feedback-sheet assessment from, ``"collated"``
        or ``"feedback"``. See this module's docstring; there is no fallback
        between them.
    marks
        ``{assessment_id: frame or mapping}`` for marks this package cannot
        fetch itself -- an MCQ sat on paper, say. Takes precedence over
        everything else. A frame needs a ``Student ID`` column and exactly
        one other; a mapping is ``{student_id: mark}``.

    Returns
    -------
    pandas.DataFrame
        ``Name``, ``Student ID``, and each assessment's raw column, with the
        weighted columns calculated. Hand it straight to
        :func:`prepare_data_for_departmental_template`.

    Examples
    --------
    ::

        import pathlib as pl        # pl is pathlib

        module = load_module(pl.Path("module.toml"))
        class_list = import_brightspace_classlist(module.classlist_path)

        marks = collate_module_marks(module, class_list)
        sheet = prepare_data_for_departmental_template(marks, module)

    An in-person MCQ, typed in::

        collate_module_marks(
            module, class_list, marks={"mcq": {"23304301": 7, "23304302": 5}}
        )
    """
    if not isinstance(module, Module):
        raise ValueError(
            "module must be a Module. Load it with load_module(), which tells "
            "this function the module's shape rather than leaving it to guess."
        )
    if source not in SOURCES:
        raise ValueError(f"source must be one of {list(SOURCES)}, not {source!r}")
    if not module.assessments:
        raise ValueError(
            f"Module {module.code} has no assessments, so there is nothing to "
            "collate."
        )

    needed = ["Student ID", "First Name", "Last Name"]
    absent = [c for c in needed if c not in class_list.columns]
    if absent:
        raise ValueError(
            f"The class list is missing {absent}. Columns present: "
            f"{list(class_list.columns)}. import_brightspace_classlist "
            "produces the right shape."
        )

    given = marks or {}
    unknown = sorted(set(given) - {a.id for a in module.assessments})
    if unknown:
        raise ValueError(
            f"Marks given for assessment(s) not in module {module.code}: "
            f"{unknown}. Known ids: {[a.id for a in module.assessments]}"
        )

    collated = pd.DataFrame(
        {
            "Student ID": class_list["Student ID"].astype(str),
            "Name": (
                class_list["First Name"].astype(str)
                + " "
                + class_list["Last Name"].astype(str)
            ),
        }
    )

    empty: list[str] = []
    for assessment in module.assessments:
        if assessment.id in given:
            found = _supplied(assessment, given[assessment.id])
        elif assessment.grade_cell is not None:
            found = (
                _from_collated(assessment)
                if source == "collated"
                else _from_feedback(assessment)
            )
        elif _has_quiz_exports(assessment):
            found = collect_quiz_marks(assessment, class_list)
        else:
            empty.append(assessment.id)
            collated[assessment.raw_column] = pd.NA
            continue

        collated = collated.merge(found, on="Student ID", how="left")

    if empty:
        warnings.warn(
            f"No marks found for assessment(s) {empty}, so their columns are "
            "empty. Nothing in the module points at marks for them: no quiz "
            "exports in the submissions folder, and no grade_cell to read a "
            "feedback sheet with. If they are marked outside Brightspace -- "
            "an MCQ sat on paper, say -- pass them in with marks=.",
            stacklevel=2,
        )

    for assessment in module.assessments:
        if not assessment.needs_weighting:
            continue

        # The column's name comes from the assessment, not from re-deriving it
        # from the fraction.
        #
        # `calculate_weighted_score` infers the label by multiplying the
        # fraction by 100, which is the weight only when the piece is marked
        # out of 100. Out of 50 and worth 25 it produces "(50)" -- the raw
        # column's own name, which it then refuses to overwrite; out of 10 and
        # worth 35 it produces "(350)". It reports both by *returning* a
        # string, and that return value was being discarded here, so the
        # weighted column silently never appeared and the failure surfaced two
        # steps later as `prepare_data_for_departmental_template` complaining
        # about a missing column. Exactly the shape of bug this package spends
        # its guards on: a component quietly absent from every total.
        marks = collated[assessment.raw_column]
        if not pd.api.types.is_numeric_dtype(marks):
            marks = pd.to_numeric(marks, errors="coerce")

        collated[assessment.weighted_column] = marks * assessment.weight_fraction()

    return collated
