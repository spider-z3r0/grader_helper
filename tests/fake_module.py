#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A whole fake module on disk: class list, submissions, feedback sheets.

Built so one call serves both an exploratory notebook and an end-to-end
test. Nothing in the suite currently drives an assessment from unzipped
download to departmental sheet, and the joins least covered -- reading a
mark out of a real workbook, and renaming folders back for re-upload -- are
exactly the ones a walkthrough exercises.

So the feedback sheets here are **real .xlsx files with a real number in a
real cell**, written with openpyxl. Empty placeholder files would sail past
``extract_studentid_grade`` without testing it, which is the blind spot this
exists to close.

Usage from a test::

    def test_something(fake_module):
        marks = catch_grades(fake_module.submissions["cw1"], fake_module.grade_cell)

Usage from a notebook, or to leave a module on disk to poke at::

    python tests/fake_module.py ~/scratch/PS4001

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl
import sys
from typing import NamedTuple

import pandas as pd
from openpyxl import Workbook

from grader_helper.dataframe_operations import excel_round, make_letter_grade
from grader_helper.models import init_module

#: Brightspace's own assignment id. Changes per assignment; carried here so
#: folder names look like the real thing.
ASSIGNMENT_ID = "27236-46025"

#: Where the mark sits in the feedback sheet. Matches module.toml.
GRADE_CELL = "D30"

#: The module's shape, matching the 2026 departmental sample.
ASSESSMENTS = (
    dict(id="cw1", type="coursework", name="Coursework 1",
         marks_out_of=100, weight=40),
    dict(id="cw2", type="coursework", name="Coursework 2",
         marks_out_of=100, weight=50),
    dict(id="mcq", type="mcq", name="MCQ", marks_out_of=10, weight=10),
)

#: The cohort, with marks chosen rather than randomised so the expected
#: results are readable and the edge cases are deliberate:
#:
#:   23304305  totals exactly 64.5 -- Excel says 65 (B2), Python says 64 (B3)
#:   23304309  scored 0 throughout -- NG, not F: no participation
#:   00123456  a leading zero, which Excel round-trips away if unguarded
#:   23304311  never submitted at all
#:   23304307  submitted twice
#:
#: (student_id, first, last, cw1, cw2, mcq)
COHORT = (
    ("23304301", "Aoife",  "Angood",   74, 66, 7),
    ("23304302", "Barra",  "Barry",    67, 56, 5),
    ("23304303", "Ciara",  "Casey",    85, 88, 9),
    ("23304304", "Darragh", "Doyle",   52, 48, 4),
    ("23304305", "Eimear", "Egan",     70, 65, 4),   # -> 64.5
    ("23304306", "Fiachra", "Flynn",   38, 42, 3),
    ("00123456", "Grainne", "Gallagher", 61, 59, 6),
    ("23304307", "Harry",  "Hayes",    45, 51, 5),   # submits twice
    ("23304308", "Iseult", "Ivers",    91, 79, 10),
    ("23304309", "Jack",   "Joyce",     0,  0, 0),   # -> NG
    ("23304310", "Kate",   "Kelly",    58, 63, 6),
    ("23304311", "Liam",   "Lynch",    55, 60, 5),   # never submits
)

#: The student who is in the class list but has no submission folder.
NON_SUBMITTER = "23304311"

#: The student with two submission folders, at different times.
DOUBLE_SUBMITTER = "23304307"


class FakeModule(NamedTuple):
    """A generated module, and the truth about what is in it.

    The ``expected`` frame is what the pipeline should reproduce. Holding it
    beside the files is what makes this an end-to-end fixture rather than
    scaffolding: a test can assert the marks that come back are the marks
    that went in.
    """

    root: pl.Path
    module_file: pl.Path
    classlist: pl.Path
    #: assessment id -> the unzipped submissions folder
    submissions: dict[str, pl.Path]
    #: assessment id -> the blank feedback sheet
    rubrics: dict[str, pl.Path]
    #: assessment id -> where the tool writes (grader workbooks, combined grades)
    grading_output: dict[str, pl.Path]
    #: One row per student: ids, names, the mark written for each assessment,
    #: and the total and letter grade those marks should produce.
    expected: pd.DataFrame
    grade_cell: str = GRADE_CELL

    def __str__(self) -> str:
        return (
            f"{self.root.name}: {len(self.expected)} students, "
            f"{len(self.submissions)} assessments, marks in {self.grade_cell}"
        )


# ---------------------------------------------------------------------------
# Pieces
# ---------------------------------------------------------------------------


def _brightspace_folder(student_id: str, last_name: str, when: str) -> str:
    """A folder name in Brightspace's download format.

    "27236-46025 - 23304308 Angood - 05 March 2026 612 PM"
    """
    return f"{ASSIGNMENT_ID} - {student_id} {last_name} - {when}"


def _write_feedback_sheet(path: pl.Path, mark=None, cell: str = GRADE_CELL) -> pl.Path:
    """A real workbook, with a real number in the marked cell.

    ``mark=None`` leaves the cell empty, which is what a blank rubric is.
    """
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Feedback"
    sheet["A1"] = "Feedback sheet"
    sheet["A29"] = "Overall mark"
    sheet[cell] = mark
    wb.save(path)
    return path


def _classlist_frame() -> pd.DataFrame:
    """A Brightspace class-list export, '#' on the username and all."""
    return pd.DataFrame(
        {
            "OrgDefinedId": [sid for sid, *_ in COHORT],
            # Brightspace writes it with a leading '#'; the reader strips it.
            "Username": [f"#{sid}" for sid, *_ in COHORT],
            "Last Name": [last for _, _, last, *_ in COHORT],
            "First Name": [first for _, first, *_ in COHORT],
            "Email": [
                f"{first.lower()}.{last.lower()}@studentmail.ul.ie"
                for _, first, last, *_ in COHORT
            ],
            "End-of-Line Indicator": ["#"] * len(COHORT),
        }
    )


def _expected_frame() -> pd.DataFrame:
    """What the pipeline should produce, computed straight from the marks.

    excel_round and make_letter_grade are used deliberately: both are
    golden-tested against the departmental sheet in
    tests/test_departmental_golden.py, so leaning on them here checks the
    plumbing without re-deriving arithmetic that is already pinned.
    """
    rows = []
    for sid, first, last, cw1, cw2, mcq in COHORT:
        total = excel_round(cw1 * 0.4 + cw2 * 0.5 + mcq)
        rows.append(
            {
                "Student ID": sid,
                "First Name": first,
                "Last Name": last,
                "cw1": cw1,
                "cw2": cw2,
                "mcq": mcq,
                "Total % Grade": total,
                "Letter Grade": make_letter_grade(total),
                "submitted": sid != NON_SUBMITTER,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# The generator
# ---------------------------------------------------------------------------


def make_fake_module(
    root: pl.Path,
    distributed: bool = True,
    marked: bool = True,
    messy: bool = True,
) -> FakeModule:
    """
    Write a complete fake module to ``root``.

    Args:
    root (pl.Path): Directory to build in. Created if absent.
    distributed (bool): Put a feedback sheet in each submission folder, as
        distribute_feedback_sheets would. Set False to start a walkthrough
        from the raw download.
    marked (bool): Write each student's mark into their sheet. Requires
        ``distributed``. Set False for sheets a grader has yet to fill in.
    messy (bool): Include the things a real download has -- a __MACOSX
        folder, a student who submitted twice, a stray index.html. Set False
        for a clean cohort.

    Returns:
    FakeModule: The paths, plus the expected results.

    Example:
        >>> fake = make_fake_module(pl.Path("scratch/PS4001"))
        >>> catch_grades(fake.submissions["cw1"], fake.grade_cell)
    """
    root = pl.Path(root)
    root.mkdir(parents=True, exist_ok=True)

    if marked and not distributed:
        raise ValueError(
            "marked=True needs distributed=True -- there is no sheet to write "
            "a mark into until the sheets have been distributed."
        )

    # --- module.toml -------------------------------------------------------
    handle = init_module(
        root,
        code="PS4001",
        name="Advanced Research Methods",
        year="2025/26",
        leader={"initials": "KOM", "name": "Kevin O Malley"},
        internal_moderator="SOB",
        assessments=[
            {**spec, "folder": spec["id"], "rubric": "Feedback sheet BLANK.xlsx",
             "grade_cell": GRADE_CELL, "graders": ["KOM", "SOB"]}
            for spec in ASSESSMENTS
        ],
        paths={"classlist": "classlist.xlsx"},
        overwrite=True,
    )

    # --- class list --------------------------------------------------------
    classlist = root / "classlist.xlsx"
    _classlist_frame().to_excel(classlist, index=False)

    # --- per assessment ----------------------------------------------------
    marks_by_assessment = {
        "cw1": {sid: cw1 for sid, _, _, cw1, _, _ in COHORT},
        "cw2": {sid: cw2 for sid, _, _, _, cw2, _ in COHORT},
        "mcq": {sid: mcq for sid, _, _, _, _, mcq in COHORT},
    }

    submissions: dict[str, pl.Path] = {}
    rubrics: dict[str, pl.Path] = {}
    grading_output: dict[str, pl.Path] = {}

    for index, spec in enumerate(ASSESSMENTS):
        # init_module has already created folder/, submissions/ and
        # grading_output/ -- ask the model where they are rather than
        # rebuilding the paths here.
        assessment = handle.module.assessment(spec["id"])

        rubrics[spec["id"]] = _write_feedback_sheet(
            assessment.rubric_path, mark=None
        )

        subs = assessment.submissions_path
        submissions[spec["id"]] = subs
        grading_output[spec["id"]] = assessment.grading_output_path

        for sid, _, last, *_ in COHORT:
            if sid == NON_SUBMITTER:
                continue

            when = f"0{index + 1} March 2026 {600 + index * 11} PM"
            folder = subs / _brightspace_folder(sid, last, when)
            folder.mkdir(exist_ok=True)

            if distributed:
                _write_feedback_sheet(
                    folder / f"Feedback sheet {sid}.xlsx",
                    mark=marks_by_assessment[spec["id"]][sid] if marked else None,
                )

            if messy and sid == DOUBLE_SUBMITTER:
                # A resubmission, later the same day. scan_multiple_subs is
                # what finds these; the marker needs to know which to read.
                again = subs / _brightspace_folder(
                    sid, last, f"0{index + 1} March 2026 {700 + index * 11} PM"
                )
                again.mkdir(exist_ok=True)

        if messy:
            # macOS creates this when unzipping; Brightspace leaves the html.
            (subs / "__MACOSX").mkdir(exist_ok=True)
            (subs / "index.html").write_text("<html>brightspace</html>")

    return FakeModule(
        root=root,
        module_file=handle.path,
        classlist=classlist,
        submissions=submissions,
        rubrics=rubrics,
        grading_output=grading_output,
        expected=_expected_frame(),
        grade_cell=GRADE_CELL,
    )


if __name__ == "__main__":
    target = pl.Path(sys.argv[1] if len(sys.argv) > 1 else "fake_PS4001")
    fake = make_fake_module(target)
    print(fake)
    print(f"\nwritten to {fake.root.resolve()}")
    print(f"  module.toml   {fake.module_file}")
    print(f"  class list    {fake.classlist}")
    for assessment_id, path in fake.submissions.items():
        print(f"  {assessment_id:<13} {path}")
