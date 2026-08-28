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

#: The quiz assessment, which REPLACES the MCQ when quizzes=True rather
#: than joining it. Same id-shaped slot, same two numbers, same weight, so
#: the weights still sum to 100 and every total in `expected` is unchanged
#: -- which is what keeps the coursework path and the golden data out of
#: this entirely.
QUIZ_ASSESSMENT = dict(
    id="quizzes", type="quiz", name="Quizzes", marks_out_of=10, weight=10,
    pass_mark=80.0, free_passes=1,
)

#: How many weekly quizzes are set. Eleven for ten marks, so one may be
#: dropped -- which is what free_passes = 1 above means.
QUIZ_COUNT = 11

#: A quiz export's header, as Brightspace downloads it. The username carries
#: a '#', and the percentage column's name begins with a space. Both are
#: real, and both are things the reader has to survive.
QUIZ_EXPORT_COLUMNS = (
    "Org Defined ID",
    "Username",
    "LastName",
    "FirstName",
    "Attempt #",
    "Score",
    "Out Of",
    " %",
)

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

#: A second module, whose shape the departmental template has no room for.
#:
#: One coursework and *two* MCQs -- 30 + 35 + 35 -- where the template is
#: written for two courseworks and one MCQ. Nothing about it is exotic; it is
#: simply a permutation the department's file was not drawn for, which until
#: `build_departmental_sheet` existed meant reshaping the block by hand.
#:
#: The MCQs are marked out of 10 and worth 35, the same `marks_out_of` the
#: PS4001 MCQ uses. That is deliberately not a round ratio: 10 does not divide
#: 35, so these exercise the `/marks_out_of*weight` branch of the weighting
#: while the coursework (100 out of, 30 worth) does too, and neither gets the
#: exact-divisor form. See `weighting_formula`.
SECOND_CODE = "PS4002"
SECOND_ASSESSMENTS = (
    dict(id="cw1", type="coursework", name="Coursework 1",
         marks_out_of=100, weight=30),
    dict(id="mcq1", type="mcq", name="MCQ 1", marks_out_of=10, weight=35),
    dict(id="mcq2", type="mcq", name="MCQ 2", marks_out_of=10, weight=35),
)


def second_module_marks() -> dict[str, dict[str, int]]:
    """PS4002's marks, derived from the same cohort rather than invented.

    The coursework takes COHORT's cw1 column and MCQ 1 takes its mcq column.
    MCQ 2 is cw2 scaled to ten, which keeps the two MCQ columns visibly
    different -- two identical columns in a fixture read as a copy-paste slip
    -- while preserving the edge cases that make the cohort worth having:
    Joyce still scores zero on everything, so he is still NG rather than F.
    """
    return {
        "cw1": {sid: cw1 for sid, _, _, cw1, _, _ in COHORT},
        "mcq1": {sid: mcq for sid, _, _, _, _, mcq in COHORT},
        "mcq2": {sid: round(cw2 / 10) for sid, _, _, _, cw2, _ in COHORT},
    }


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
    #: assessment id -> the quiz exports, one file per quiz. Empty unless
    #: the module was built with quizzes=True.
    quiz_exports: dict[str, list]
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


def write_quiz(folder: pl.Path, quiz: str, scores: dict) -> pl.Path:
    """Write one Brightspace quiz export.

    `scores` maps student id (bare digits, as the class list holds them) to
    the percentage they scored. A student absent from it did not sit this
    quiz and so has no row, which is how Brightspace exports it. A score of
    None writes the row with an empty percentage -- opened the quiz, never
    submitted it.

    Lives here rather than in the test that first needed it so there is one
    definition of what an export looks like, beside the one definition of
    what a submission folder looks like.
    """
    path = folder / f"{quiz} - PS4001 - 12 January 2026.csv"
    rows = [
        {
            "Org Defined ID": sid,
            "Username": f"#{sid}",
            "LastName": f"Surname{sid[-2:]}",
            "FirstName": f"First{sid[-2:]}",
            "Attempt #": 1,
            "Score": "" if pct is None else pct / 10,
            "Out Of": 10,
            " %": "" if pct is None else f"{pct} %",
        }
        for sid, pct in scores.items()
    ]
    pd.DataFrame(rows, columns=list(QUIZ_EXPORT_COLUMNS)).to_csv(path, index=False)
    return path


def _quiz_scores(target: int, count: int = QUIZ_COUNT) -> list:
    """The per-quiz percentages that produce a mark of exactly `target`.

    Built backwards from the answer, which is what makes the fixture assert
    something rather than merely exist. With one free pass, the mark is
    ``min(passes + 1, marks_out_of)``, so:

        target 0   sat nothing at all -- no rows anywhere, and no free pass
        target v   passed v - 1, failed the rest
        target 10  passed 9 of 11, and the cap does the last mark

    Returns one percentage per quiz, or an empty list for a student who
    never appears in an export.
    """
    if target <= 0:
        return []
    passes = target - 1
    return [90.0] * passes + [10.0] * (count - passes)


def _write_quiz_exports(folder: pl.Path, marks: dict) -> list:
    """One export per quiz, holding every student who sat it."""
    scores = {sid: _quiz_scores(target) for sid, target in marks.items()}
    written = []
    for index in range(QUIZ_COUNT):
        written.append(
            write_quiz(
                folder,
                f"Quiz {index + 1:02d}",
                {
                    sid: sat[index]
                    for sid, sat in scores.items()
                    if index < len(sat)
                },
            )
        )
    return written


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
    quizzes: bool = False,
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
    quizzes (bool): Replace the MCQ with a batch of weekly quizzes --
        eleven Brightspace exports in the assessment's submissions folder,
        and the collection rules recorded in module.toml. Off by default,
        so the module every other test sees is exactly the module it saw
        before this existed. The marks work out the same either way: a
        student's quiz mark is the mark their MCQ would have been, so
        `expected` and the totals in it do not change.

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

    # The quiz takes the MCQ's slot rather than being added beside it, so
    # the weights still sum to 100 and no total moves.
    specs = tuple(
        QUIZ_ASSESSMENT if quizzes and spec["id"] == "mcq" else spec
        for spec in ASSESSMENTS
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
            {**spec, "folder": spec["id"]}
            if spec["type"] == "quiz"
            else {**spec, "folder": spec["id"],
                  "rubric": "Feedback sheet BLANK.xlsx",
                  "grade_cell": GRADE_CELL, "graders": ["KOM", "SOB"]}
            for spec in specs
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
        # The quiz mark is the mark the MCQ would have been. Same column of
        # COHORT, same totals, so `expected` covers both shapes.
        ("quizzes" if quizzes else "mcq"): {
            sid: mcq for sid, _, _, _, _, mcq in COHORT
        },
    }

    submissions: dict[str, pl.Path] = {}
    rubrics: dict[str, pl.Path] = {}
    grading_output: dict[str, pl.Path] = {}
    quiz_exports: dict[str, list] = {}

    for index, spec in enumerate(specs):
        # init_module has already created folder/, submissions/ and
        # grading_output/ -- ask the model where they are rather than
        # rebuilding the paths here.
        assessment = handle.module.assessment(spec["id"])

        if spec["type"] == "quiz":
            # Nobody marks a quiz: there are no submission folders and no
            # feedback sheets, just Brightspace's own exports where the
            # download would be.
            subs = assessment.submissions_path
            submissions[spec["id"]] = subs
            grading_output[spec["id"]] = assessment.grading_output_path
            quiz_exports[spec["id"]] = _write_quiz_exports(
                subs, marks_by_assessment[spec["id"]]
            )
            continue

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
        quiz_exports=quiz_exports,
        expected=_expected_frame(),
        grade_cell=GRADE_CELL,
    )


def make_second_module(root: pl.Path, marked: bool = True) -> FakeModule:
    """
    Write PS4002 -- one coursework and two MCQs -- to ``root``.

    A shape the departmental template has no room for, built so the
    walkthrough can show `build_departmental_sheet` laying a sheet out for it.
    Deliberately lighter than `make_fake_module`: the marking pipeline is
    demonstrated twice over by PS4001, so this writes only what is needed to
    collate a module and build its sheet.

    Args:
    root (pl.Path): Directory to build in. Created if absent.
    marked (bool): Write each student's mark into their coursework feedback
        sheet. The MCQs have no sheets at all -- they are sat on paper, and
        their marks are handed to `collate_module_marks` through ``marks=``.

    Returns:
    FakeModule: The paths, plus an ``expected`` frame carrying the marks for
    all three assessments, so the MCQ marks a caller has to hand in come from
    the fixture rather than being retyped.

    Note:
        The cohort and the class list are PS4001's. These are the same
        students taking a second module, which is what makes it reasonable to
        reuse the class list rather than invent a parallel one.

    Example:
        >>> second = make_second_module(pl.Path("scratch/PS4002"))
        >>> by_id = second.expected.set_index("Student ID")
        >>> collate_module_marks(
        ...     module,
        ...     class_list,
        ...     source="feedback",
        ...     marks={"mcq1": by_id["mcq1"].to_dict()},
        ... )
    """
    root = pl.Path(root)
    root.mkdir(parents=True, exist_ok=True)
    marks = second_module_marks()

    handle = init_module(
        root,
        code=SECOND_CODE,
        name="Cognition and Perception",
        year="2025/26",
        leader={"initials": "KOM", "name": "Kevin O Malley"},
        internal_moderator="SOB",
        assessments=[
            {**spec, "folder": spec["id"]}
            if spec["type"] != "coursework"
            else {**spec, "folder": spec["id"],
                  "rubric": "Feedback sheet BLANK.xlsx",
                  "grade_cell": GRADE_CELL, "graders": ["KOM", "SOB"]}
            for spec in SECOND_ASSESSMENTS
        ],
        paths={"classlist": "classlist.xlsx"},
        overwrite=True,
    )

    classlist = root / "classlist.xlsx"
    _classlist_frame().to_excel(classlist, index=False)

    submissions: dict[str, pl.Path] = {}
    rubrics: dict[str, pl.Path] = {}
    grading_output: dict[str, pl.Path] = {}

    for spec in SECOND_ASSESSMENTS:
        assessment = handle.module.assessment(spec["id"])
        submissions[spec["id"]] = assessment.submissions_path
        grading_output[spec["id"]] = assessment.grading_output_path

        if spec["type"] != "coursework":
            # Nobody hands in an MCQ sat in a lecture theatre, so there is no
            # download to unzip and no feedback sheet to read. The marks reach
            # collate_module_marks through `marks=` instead, which is what
            # that argument is for.
            continue

        rubrics[spec["id"]] = _write_feedback_sheet(assessment.rubric_path, mark=None)

        for sid, _, last, *_ in COHORT:
            if sid == NON_SUBMITTER:
                continue
            folder = assessment.submissions_path / _brightspace_folder(
                sid, last, "14 April 2026 430 PM"
            )
            folder.mkdir(exist_ok=True)
            _write_feedback_sheet(
                folder / f"Feedback sheet {sid}.xlsx",
                mark=marks[spec["id"]][sid] if marked else None,
            )

    return FakeModule(
        root=root,
        module_file=handle.path,
        classlist=classlist,
        submissions=submissions,
        rubrics=rubrics,
        grading_output=grading_output,
        quiz_exports={},
        expected=_second_expected_frame(marks),
        grade_cell=GRADE_CELL,
    )


def _second_expected_frame(marks: dict) -> pd.DataFrame:
    """PS4002's marks and the total they should produce.

    Weighted the way the sheet weights them -- each component scaled by
    weight/marks_out_of and left unrounded, with excel_round applied once to
    the total. Rounding the components instead moves totals across band
    boundaries, which is the whole point of the rule.
    """
    rows = []
    for sid, first, last, *_ in COHORT:
        # The non-submitter has no feedback sheet, so there is no coursework
        # mark to read and his total is the MCQs alone. Crediting him with the
        # cohort's cw1 value would make `expected` disagree with anything that
        # actually collates the module -- and disagree by 30 marks, silently.
        submitted = sid != NON_SUBMITTER
        coursework = marks["cw1"][sid] if submitted else None
        total = excel_round(
            (coursework * (30 / 100) if submitted else 0)
            + marks["mcq1"][sid] * (35 / 10)
            + marks["mcq2"][sid] * (35 / 10)
        )
        rows.append(
            {
                "Student ID": sid,
                "First Name": first,
                "Last Name": last,
                "cw1": coursework,
                "mcq1": marks["mcq1"][sid],
                "mcq2": marks["mcq2"][sid],
                "Total % Grade": total,
                "Letter Grade": make_letter_grade(total),
                "submitted": sid != NON_SUBMITTER,
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    target = pl.Path(sys.argv[1] if len(sys.argv) > 1 else "fake_PS4001")
    fake = make_fake_module(target)
    print(fake)
    print(f"\nwritten to {fake.root.resolve()}")
    print(f"  module.toml   {fake.module_file}")
    print(f"  class list    {fake.classlist}")
    for assessment_id, path in fake.submissions.items():
        print(f"  {assessment_id:<13} {path}")
