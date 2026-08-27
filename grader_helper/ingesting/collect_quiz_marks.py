#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""A term of weekly quizzes, collected into one mark.

Brightspace exports one CSV per quiz, not one file for the set, so this is a
fold: read each export, join them on the student id, count how many the
student passed, and hand back a single column for the grade sheet. The
two-numbers rule already says what that column is called -- ten weekly
quizzes marked out of 10 and worth 10 produce ``Quizzes (10)`` and nothing
else -- so the caller supplies the :class:`~grader_helper.models.Assessment`
and the name falls out of it.

House convention::

    import pathlib as pl        # pl is pathlib
    import polars as pr         # pr is polars

Three things about this are policy rather than arithmetic, and all three are
the module leader's to set:

``pass_mark``
    A quiz is passed when its **percentage is strictly above** ``pass_mark``.
    Strictly: at 80.0 the default rule fails a student who scored exactly
    80%. That is the rule as stated on the module this was written for, and
    it is worth knowing rather than discovering.
``free_passes``
    Softening. Eleven quizzes are set, ten marks are available, so a student
    may fail one and still take full marks. Implemented as *add n, then cap
    at* ``marks_out_of`` -- which is more generous than dropping the worst
    quiz, because it lifts everyone rather than only those near the top.
``the non-participant``
    The free pass is **not** given to a student who sat no quiz at all. It
    compensates for a bad week among quizzes taken; a student who took none
    has no bad week to compensate. This matters beyond fairness: the
    departmental sheet awards NG rather than F where the module total is
    zero, so crediting a ghost student with 1% would silently convert their
    NG into a fail.

No rounding happens here. The percentage Brightspace reports is compared as
given, because rounding *up* to the boundary would promote a fail to a pass
-- inventing a mark rather than reading one. ``excel_round`` belongs where
totals are formed for the sheet, not where a threshold is tested.
"""

import pathlib as pl
import warnings
from functools import reduce

import pandas as pd
import polars as pr

from ..models import Assessment

#: Columns every Brightspace quiz export carries, mapped to what this package
#: calls them. ``Username`` matches the class list export; the name columns do
#: not -- Brightspace writes them unspaced here and spaced there.
QUIZ_COLUMNS: dict[str, str] = {
    "Username": "Student ID",
    "FirstName": "First Name",
    "LastName": "Last Name",
}

#: Column names accepted as "the percentage score", compared with spaces,
#: underscores and case ignored. Brightspace writes it as ``" %"`` -- with a
#: leading space -- which is exactly the kind of detail that changes between
#: versions, so it is matched leniently rather than by literal name.
PERCENT_ALIASES: tuple[str, ...] = ("%", "percent", "percentage", "score%")

#: What separates the quiz name from the rest of the export's file name.
#: ``"Quiz 1 - PS4001 - 12 January 2026.csv"`` is quiz ``"Quiz 1"``.
NAME_SEPARATOR = " - "

#: Suffix given to each quiz's score column, so the joined frame reads
#: ``"Quiz 1 score"``, ``"Quiz 2 score"``, ...
SCORE_SUFFIX = " score"


class DuplicateAttemptError(ValueError):
    """Raised when one quiz export holds more than one row for a student.

    Its own type, and deliberately not resolved automatically. Which attempt
    counts -- first, last, best -- is a decision about the module's rules,
    and picking one here would quietly award a mark the leader never chose.
    The same refusal ``alphabetise_folders`` makes on a double submission,
    for the same reason.
    """


def _normalise(name: str) -> str:
    return str(name).strip().lower().replace(" ", "").replace("_", "")


def quiz_name(path: pl.Path) -> str:
    """The quiz's name, taken from the export's file name.

    Everything before the first ``" - "``, so a file downloaded as
    ``"Quiz 1 - PS4001 - 12 January 2026.csv"`` is quiz ``"Quiz 1"``. A file
    name without the separator is used whole.

    >>> import pathlib as pl
    >>> quiz_name(pl.Path("Quiz 1 - PS4001 - 12 January 2026.csv"))
    'Quiz 1'
    >>> quiz_name(pl.Path("Week 3.csv"))
    'Week 3'
    """
    return path.stem.split(NAME_SEPARATOR)[0].strip()


def find_percent_column(columns) -> str:
    """Return the column holding the percentage score.

    Raises
    ------
    ValueError
        If no candidate is found. The message lists the columns that *are*
        present, because the usual cause is an export of the wrong report
        rather than a corrupt file.
    """
    lookup = {_normalise(c): c for c in columns}
    for alias in PERCENT_ALIASES:
        if alias in lookup:
            return lookup[alias]
    raise ValueError(
        "No percentage column in this quiz export. Looked for any of "
        f"{list(PERCENT_ALIASES)} (ignoring case and spaces). Columns "
        f"present: {list(columns)}. Brightspace writes it as ' %', with a "
        "leading space, in the quiz export -- check this is that export and "
        "not the class list or a grades download."
    )


def read_quiz(path: pl.Path, name: str | None = None) -> pr.LazyFrame:
    """Read one Brightspace quiz export.

    Parameters
    ----------
    path
        The exported CSV for a single quiz.
    name
        The quiz's name, defaulting to :func:`quiz_name` of the file name.
        Becomes the stem of the score column.

    Returns
    -------
    polars.LazyFrame
        ``Student ID``, ``First Name``, ``Last Name`` and one float column
        named ``"<name> score"`` holding the percentage.

    Notes
    -----
    Two things are done to the id, and both are load-bearing:

    - **The ``#`` is stripped.** Brightspace writes the username as
      ``"#56170559"`` here exactly as it does in the class list, where
      ``import_brightspace_classlist`` already strips it. Left on, the join
      against the class list does not fail -- it matches nothing, and every
      student comes back twice with half their row empty.
    - **Every column is read as text.** ``'00123456'`` inferred as a number
      reads back ``123456``, and a student with a leading zero stops
      existing. The percentage is cast to float afterwards, explicitly.
    """
    if not isinstance(path, pl.Path):
        raise TypeError("path must be a Path object")
    if path.suffix.lower() != ".csv":
        raise ValueError(
            f"{path.name} is not a .csv. Quiz exports come out of Brightspace "
            "as CSV; an .xlsx here usually means the file has been opened and "
            "re-saved, which is also where student ids lose their leading "
            "zeros."
        )
    if not path.exists():
        raise FileNotFoundError(f"No quiz export found at {path}")

    # infer_schema_length=0 reads every column as text, which is the whole
    # defence for the student id. Nothing is inferred and then regretted.
    frame = pr.scan_csv(path, infer_schema_length=0)
    columns = frame.collect_schema().names()  # forces the header read early

    missing = [c for c in QUIZ_COLUMNS if c not in columns]
    if missing:
        raise ValueError(
            f"{path.name} is missing {missing}, so it cannot be a Brightspace "
            f"quiz export. Columns present: {columns}"
        )
    percent = find_percent_column(columns)

    quiz = name if name is not None else quiz_name(path)
    if not quiz:
        raise ValueError(
            f"Could not read a quiz name from {path.name!r}. Pass name= to "
            "set it explicitly."
        )

    collected = frame.select(
        pr.col("Username")
        .str.strip_chars()
        .str.strip_prefix("#")
        .alias(QUIZ_COLUMNS["Username"]),
        pr.col("FirstName").str.strip_chars().alias(QUIZ_COLUMNS["FirstName"]),
        pr.col("LastName").str.strip_chars().alias(QUIZ_COLUMNS["LastName"]),
        pr.col(percent)
        .str.strip_chars(" %")
        .cast(pr.Float64, strict=False)
        .alias(f"{quiz}{SCORE_SUFFIX}"),
    ).collect()

    repeated = (
        collected.group_by("Student ID")
        .len()
        .filter(pr.col("len") > 1)
        .get_column("Student ID")
        .to_list()
    )
    if repeated:
        raise DuplicateAttemptError(
            f"{path.name} has more than one row for {sorted(repeated)}. That "
            "is usually multiple attempts at the quiz. Decide which attempt "
            "counts and export again -- this package will not choose one for "
            "you, because the choice is a rule about the module, not a fact "
            "about the file."
        )

    return collected.lazy()


def collect_quiz_marks(
    assessment: Assessment,
    class_list: pd.DataFrame,
    folder: pl.Path | None = None,
    pass_mark: float | None = None,
    free_passes: int | None = None,
) -> pd.DataFrame:
    """Fold a folder of quiz exports into one mark per student.

    Parameters
    ----------
    assessment
        The quiz assessment. Supplies ``marks_out_of`` (the cap) and
        ``raw_column`` (what the mark column is called).
    class_list
        The class list, as ``import_brightspace_classlist`` returns it. It
        decides who is in the cohort: **every student in it gets a row**,
        including one who sat nothing, and a student in the exports but not
        in the class list is dropped with a warning.
    folder
        Where the exports are, defaulting to the assessment's
        ``submissions_path`` -- for a quiz the Brightspace download *is* the
        submissions, so no new folder is needed.
    pass_mark
        The percentage a quiz must exceed, **strictly**, to count as passed.
        Defaults to the assessment's own ``pass_mark``, which is where it
        belongs: the rule is the module's, and ``module.toml`` is the
        module's memory. There is no fallback beyond that -- with neither
        set this raises, because a threshold nobody chose is exactly the
        kind of invisible policy that produces a plausible wrong mark.
    free_passes
        Quizzes a student may fail without losing a mark. Added to the count
        and then capped at ``marks_out_of``. Not given to a student who sat
        no quiz at all -- see this module's docstring. Defaults to the
        assessment's own ``free_passes``, which defaults to none.

    Returns
    -------
    pandas.DataFrame
        ``Student ID`` and one integer column named for the assessment, e.g.
        ``Quizzes (10)``. pandas, not polars, because that is what the rest
        of the pipeline reads; the fold itself is polars throughout.

    Examples
    --------
    Eleven weekly quizzes, ten marks, one bad week forgiven::

        import pathlib as pl        # pl is pathlib
        import polars as pr         # pr is polars

        # pass_mark = 80.0 and free_passes = 1 are recorded on the
        # assessment in module.toml, so the call does not restate them.
        module = load_module(pl.Path("module.toml"))
        marks = collect_quiz_marks(module.assessment("quizzes"), class_list)
    """
    pass_mark = pass_mark if pass_mark is not None else assessment.pass_mark
    if pass_mark is None:
        raise ValueError(
            f"Assessment {assessment.id!r} has no pass_mark, so there is no "
            "rule for what counts as passing one quiz. Add `pass_mark` to "
            "its [[assessment]] block in module.toml -- that is where the "
            "module records its own rules -- or pass pass_mark= for a "
            "one-off."
        )
    free_passes = (
        free_passes if free_passes is not None else assessment.free_passes
    )

    if not float(assessment.marks_out_of).is_integer():
        raise ValueError(
            f"Assessment {assessment.id!r} is marked out of "
            f"{assessment.marks_out_of}, but a quiz mark is a count of "
            "quizzes passed and cannot be fractional. Give the assessment a "
            "whole marks_out_of, or collect it some other way."
        )
    if free_passes < 0:
        raise ValueError(f"free_passes must be 0 or more, not {free_passes}")
    if "Student ID" not in class_list.columns:
        raise ValueError(
            "The class list has no 'Student ID' column, so quiz marks cannot "
            f"be matched to students. Columns present: {list(class_list.columns)}"
        )

    folder = folder if folder is not None else assessment.submissions_path
    if not folder.exists():
        raise FileNotFoundError(f"No quiz folder at {folder}")

    exports = sorted(p for p in folder.iterdir() if p.suffix.lower() == ".csv")
    if not exports:
        raise FileNotFoundError(
            f"No .csv quiz exports in {folder}. Brightspace exports one file "
            "per quiz; this folder has none."
        )

    names = [quiz_name(p) for p in exports]
    repeated = sorted({n for n in names if names.count(n) > 1})
    if repeated:
        raise ValueError(
            f"More than one export in {folder} is named for quiz {repeated}. "
            "Two files for one quiz would count it twice. Remove the "
            "duplicate, or rename so each file's name up to ' - ' is the "
            "quiz it holds."
        )

    quizzes = [read_quiz(p, name=n) for p, n in zip(exports, names)]
    joined = reduce(
        lambda left, right: left.join(
            right.drop("First Name", "Last Name"),
            on="Student ID",
            how="full",
            coalesce=True,
        ),
        quizzes,
    )

    score_columns = [f"{n}{SCORE_SUFFIX}" for n in names]
    #: A null score means the student did not sit that quiz. Made explicit
    #: rather than left to sum_horizontal's null handling, because "did not
    #: sit it" and "sat it and failed" have to count the same here and it
    #: should be visible that they do.
    passed = pr.sum_horizontal(
        [(pr.col(c) > pass_mark).fill_null(False).cast(pr.Int64) for c in score_columns]
    )
    sat_any = (
        pr.sum_horizontal(
            [pr.col(c).is_not_null().cast(pr.Int64) for c in score_columns]
        )
        > 0
    )
    earned = pr.min_horizontal(
        passed + pr.when(sat_any).then(free_passes).otherwise(0),
        pr.lit(int(assessment.marks_out_of)),
    )

    marked = (
        joined.select(
            pr.col("Student ID"),
            earned.cast(pr.Int64).alias("mark"),
        )
        .collect()
    )

    marks = dict(zip(marked.get_column("Student ID"), marked.get_column("mark")))

    ids = class_list["Student ID"].astype(str)
    unknown = sorted(set(marks) - set(ids))
    if unknown:
        warnings.warn(
            f"{len(unknown)} student(s) sat a quiz but are not in the class "
            f"list, so they have no mark here: {unknown[:10]}"
            + (" ..." if len(unknown) > 10 else "")
            + ". Usually a withdrawal, or a class list exported before they "
            "registered.",
            stacklevel=2,
        )

    # Students in the class list and in no export scored nothing and sat
    # nothing: 0, and no free pass. Dropping them instead would take a
    # component out of their module total, which is still a plausible number.
    return pd.DataFrame(
        {
            "Student ID": ids.to_numpy(),
            assessment.raw_column: [int(marks.get(sid, 0)) for sid in ids],
        }
    )
