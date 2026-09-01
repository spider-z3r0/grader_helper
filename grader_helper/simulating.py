#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Fill in marks that nobody marked, so the rest of the pipeline can be run.

Everything downstream of allocation needs marks to exist: reconciliation
needs two records to compare, collation needs something to collate, the
moderation sample needs a spread of bands to stratify, and the departmental
sheet needs numbers to put in it. Producing those by hand means opening
forty workbooks, and producing them by marking real work means marking real
work.

So this is the stand-in for **steps 5 and 6 of the lifecycle** -- the grader
writing a mark on the feedback sheet, and the grader copying that mark into
their own workbook. Two writes, not one, because they are two records and
the whole point of step 7 is that they can disagree. A simulator that only
ever wrote them together could never exercise the control that exists to
catch the copy going wrong, so ``discrepancies=`` deliberately mistypes a
few.

**This writes into real files.** It is a testing aid, meant for a scratch
copy of a module. Two things protect you and neither is clever:

- a feedback sheet whose grade cell already holds a number is **skipped**,
  so a part-marked assessment is not quietly overwritten;
- the command line **shows the plan and writes nothing** unless you pass
  ``--write``.

Writing a number into the grade cell **replaces whatever formula is there**.
That is unavoidable -- a real rubric calculates its total from criterion
cells this knows nothing about -- and it is the main reason to point this at
a copy.

House convention::

    import pathlib as pl        # pl is pathlib
    import polars as pr         # pr is polars

From a terminal::

    uv run python -m grader_helper.simulating ~/scratch/PS4001
    uv run python -m grader_helper.simulating ~/scratch/PS4001 -a cw1 --write
"""

import argparse
import pathlib as pl
import random
import zlib
from typing import Mapping, NamedTuple, Sequence

import pandas as pd
from openpyxl import load_workbook

from .dataframe_operations.make_letter_grade import GRADE_BANDS
from .models import Assessment, Module, load_module

#: What `distribute_feedback_sheets` names the sheets it copies in. The
#: identifier after it is a student id, or a group label like "Team 3".
SHEET_PREFIX = "feedback sheet "

#: The column a grader writes their mark into, matching `allocating` and
#: `collating` -- this stands in for the grader, so it writes where they do.
MARK_COLUMN = "Mark"

#: Roughly where a psychology coursework cohort actually sits, as fractions
#: of whatever the piece is marked out of. Not uniform: a uniform cohort
#: puts a tenth of the class in every band, which makes the moderation
#: sample look easy and the grade distribution look nothing like one.
MEAN_FRACTION = 0.58
SD_FRACTION = 0.15

#: Marks worth planting deliberately, as percentages, because they are the
#: ones the arithmetic can get wrong and random draws almost never hit:
#:
#: * every band edge, where one mark either way is a different letter grade;
#: * the halves that Python and Excel round in opposite directions --
#:   ``round(64.5)`` is 64 (half to even) and Excel's is 65 (half away from
#:   zero), and 64 is a B3 where 65 is a B2. That rule has a house note of
#:   its own, and a cohort with no exact halves in it never tests it;
#: * zero, which the departmental sheet grades NG rather than F.
BOUNDARY_MARKS: tuple[float, ...] = tuple(
    sorted(
        {band.lower for band in GRADE_BANDS}
        | {54.5, 64.5, 74.5, 39.5, 49.5}
        | {0.0}
    )
)


class SimulatedMarking(NamedTuple):
    """What a simulated marking run did, or would do.

    Returned rather than printed, so the command line can render it and a
    test can assert on it.
    """

    #: ``{identifier: mark}`` -- the mark written on each feedback sheet.
    marks: dict[str, float]
    #: Feedback sheets written, by identifier. A list each, because a
    #: student who submitted twice has two sheets and both are theirs.
    sheets: dict[str, list[pl.Path]]
    #: Sheets left alone because they already carried a mark.
    skipped: dict[str, list[pl.Path]]
    #: Grader workbooks filled in, and how many rows each got.
    workbooks: dict[str, int]
    #: ``{identifier: (on the sheet, in the workbook)}`` where the two were
    #: deliberately made to disagree -- the mistyped copy step 7 catches.
    discrepancies: dict[str, tuple[float, float]]
    #: True when nothing was written.
    dry_run: bool

    def __str__(self) -> str:
        what = "would write" if self.dry_run else "wrote"
        written = sum(len(paths) for paths in self.sheets.values())
        skipped = sum(len(paths) for paths in self.skipped.values())
        parts = [
            f"{what} {written} feedback sheet(s) for {len(self.sheets)} student(s)",
            f"{skipped} already marked",
            f"{len(self.workbooks)} grader workbook(s)",
        ]
        if self.discrepancies:
            parts.append(f"{len(self.discrepancies)} planted discrepancy(ies)")
        return ", ".join(parts)


def _identifier(stem: str) -> str | None:
    """The student id or group label a feedback sheet is named for."""
    lowered = stem.lower()
    if not lowered.startswith(SHEET_PREFIX):
        return None
    found = stem[len(SHEET_PREFIX):].strip()
    return found or None


def feedback_sheets(assessment: Assessment) -> dict[str, list[pl.Path]]:
    """Every distributed feedback sheet, by the identifier it is named for.

    **A list per identifier, not one path.** A student who submitted twice
    has two folders and therefore two feedback sheets, and that is a normal
    state -- resolving resubmissions is a judgement call, so a download sits
    in it until somebody makes one. Keeping only the last would leave the
    other sheet unmarked, and `catch_grades` reads every sheet it finds, so
    the result is a warning about an empty cell on a student who was marked.

    Raises
    ------
    NotADirectoryError
        If the submissions folder is not there, which means the download has
        not been unzipped into it yet.
    """
    submissions = assessment.submissions_path
    if not submissions.is_dir():
        raise NotADirectoryError(
            f"No submissions folder for {assessment.id!r} at {submissions}. "
            "There is nothing to mark until the Brightspace download is "
            "unzipped into it and the feedback sheets are distributed."
        )

    found: dict[str, list[pl.Path]] = {}
    for path in sorted(submissions.rglob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        identifier = _identifier(path.stem)
        if identifier is not None:
            found.setdefault(identifier, []).append(path)
    return found


def _already_marked(path: pl.Path, cell: str) -> bool:
    """Whether the grade cell already holds a number.

    A formula with no cached result reads as ``None`` here, which is what an
    unmarked sheet written by this package looks like. A sheet somebody has
    actually marked in Excel has a number cached, and is left alone.
    """
    workbook = None
    try:
        workbook = load_workbook(path, data_only=True, read_only=True)
        value = workbook.worksheets[0][cell].value
    except Exception:
        # Unreadable is not "already marked" -- let the write attempt say so.
        return False
    finally:
        if workbook is not None:
            try:
                workbook.close()
            except Exception:
                pass
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def draw_marks(
    identifiers: Sequence[str],
    marks_out_of: float,
    *,
    seed: int | None = None,
    boundaries: int = 3,
    rng: "random.Random | None" = None,
) -> dict[str, float]:
    """A plausible mark for each identifier, rounded to the nearest half.

    Parameters
    ----------
    identifiers
        Who is being marked -- student ids, or group labels.
    marks_out_of
        The assessment's own scale. The distribution and the planted
        boundary marks are both expressed as fractions of it, so a piece
        marked out of 50 gets sensible numbers without being told anything
        else.
    seed
        For a reproducible cohort. Worth using: a bug found against one set
        of marks is much easier to chase when the marks come back.
    rng
        An existing random source, used instead of ``seed``. How
        ``simulate_marking`` keeps drawing marks and choosing who mistypes
        one off a single stream -- two ``Random(seed)`` objects make the
        same first choice, so the mistyped students were exactly the
        boundary students, every run.
    boundaries
        How many of the marks to place on a band edge or an awkward half
        rather than drawing them. See :data:`BOUNDARY_MARKS`.

    Returns
    -------
    dict
        ``{identifier: mark}``.
    """
    rng = rng if rng is not None else random.Random(seed)
    ordered = list(identifiers)

    planted: dict[str, float] = {}
    if boundaries > 0 and ordered:
        chosen = rng.sample(ordered, min(boundaries, len(ordered)))
        for i, identifier in enumerate(chosen):
            percent = BOUNDARY_MARKS[i % len(BOUNDARY_MARKS)]
            planted[identifier] = round(percent / 100 * marks_out_of, 2)

    marks: dict[str, float] = {}
    for identifier in ordered:
        if identifier in planted:
            marks[identifier] = planted[identifier]
            continue
        drawn = rng.gauss(MEAN_FRACTION * marks_out_of, SD_FRACTION * marks_out_of)
        clamped = min(max(drawn, 0.0), marks_out_of)
        # To the nearest half: what a grader actually writes, and it puts
        # exact halves in front of the rounding rule on purpose.
        marks[identifier] = round(clamped * 2) / 2
    return marks


def _write_sheet(path: pl.Path, cell: str, mark: float) -> None:
    workbook = load_workbook(path)
    workbook.worksheets[0][cell] = mark
    workbook.save(path)


def _key_column(frame: pd.DataFrame) -> str:
    """What a grader workbook's rows are keyed by.

    ``Student ID`` for the per-student shape, ``Group`` for the per-group one
    a Brightspace-managed group assessment gets -- the same split
    `allocate_graders` writes them in.
    """
    for column in ("Student ID", "Group"):
        if column in frame.columns:
            return column
    raise KeyError(
        "A grader workbook has neither a 'Student ID' nor a 'Group' column, "
        f"so its rows cannot be matched to a mark. Columns present: "
        f"{list(frame.columns)}. allocate_graders writes one or the other."
    )


def simulate_marking(
    assessment: Assessment,
    *,
    seed: int | None = None,
    boundaries: int = 3,
    discrepancies: int = 0,
    overwrite: bool = False,
    dry_run: bool = False,
    marks: Mapping[str, float] | None = None,
) -> SimulatedMarking:
    """
    Mark an assessment as if a grader had, on both records.

    Writes a mark into every distributed feedback sheet's grade cell, and
    the same mark into the ``Mark`` column of the grader workbook that
    student or group belongs to -- which is what a grader does, in that
    order, and what step 7 then reconciles.

    Parameters
    ----------
    assessment
        A bound assessment, i.e. one reached through a module loaded with
        ``load_module``. It must have a ``grade_cell``.
    seed
        For a reproducible cohort.
    boundaries
        How many marks to place on band edges and awkward halves instead of
        drawing them.
    discrepancies
        How many students to have the grader **mistype** into their
        workbook. This is the failure `reconcile_marks` exists to catch, and
        without it every reconciliation trivially passes.
    overwrite
        Mark sheets that already carry a number. Off by default, so a
        part-marked assessment survives a careless run.
    dry_run
        Work out what would happen and write nothing.
    marks
        Use these marks instead of drawing any. ``{identifier: mark}``.

    Returns
    -------
    SimulatedMarking
        What was written, skipped and planted.

    Raises
    ------
    ValueError
        If the assessment has no ``grade_cell``, or if more discrepancies
        are asked for than there are marks to spoil.
    NotADirectoryError
        If the submissions folder is not there.

    Examples
    --------
    ::

        import pathlib as pl        # pl is pathlib

        module = load_module(pl.Path("~/scratch/PS4001/module.toml"))
        result = simulate_marking(module.assessment("cw1"), seed=1,
                                  discrepancies=2)
        print(result)
    """
    if not isinstance(assessment, Assessment):
        raise ValueError(
            "assessment must be an Assessment, reached through a module "
            "loaded with load_module() -- an unbound one does not know where "
            "its own files are."
        )
    if assessment.grade_cell is None:
        raise ValueError(
            f"Assessment {assessment.id!r} has no grade_cell, so there is no "
            "cell to write a mark into. Set grade_cell in module.toml -- it "
            "is the same cell catch_grades reads back."
        )

    sheets = feedback_sheets(assessment)
    if not sheets:
        raise ValueError(
            f"No feedback sheets under {assessment.submissions_path}. "
            "distribute_feedback_sheets puts them there, named "
            "'Feedback sheet <id>.xlsx'; nothing can be marked until it has "
            "run."
        )

    # One random stream for the whole run. Two Random(seed) objects make the
    # same first choice, which had the mistyped students coming out exactly
    # equal to the boundary students on every seed.
    rng = random.Random(seed)
    drawn = (
        dict(marks)
        if marks is not None
        else draw_marks(
            list(sheets), assessment.marks_out_of, boundaries=boundaries, rng=rng
        )
    )

    if discrepancies > len(drawn):
        raise ValueError(
            f"Asked for {discrepancies} discrepancy(ies) but there are only "
            f"{len(drawn)} mark(s) to spoil."
        )

    # The mistyped copy: the sheet says one thing, the workbook another.
    # Done here rather than by nudging the sheet afterwards so that the
    # *sheet* stays the record the student received, which is what it is.
    reported = dict(drawn)
    planted: dict[str, tuple[float, float]] = {}
    for identifier in rng.sample(sorted(drawn), discrepancies):
        # A transposition-sized slip, and never off the end of the scale.
        slip = rng.choice([-10, -9, -2, -1, 1, 2, 9, 10])
        wrong = min(max(drawn[identifier] + slip, 0.0), assessment.marks_out_of)
        if wrong == drawn[identifier]:
            wrong = min(drawn[identifier] + 1, assessment.marks_out_of)
        reported[identifier] = wrong
        planted[identifier] = (drawn[identifier], wrong)

    written: dict[str, list[pl.Path]] = {}
    skipped: dict[str, list[pl.Path]] = {}
    for identifier, paths in sheets.items():
        for path in paths:
            if not overwrite and _already_marked(path, assessment.grade_cell):
                skipped.setdefault(identifier, []).append(path)
                continue
            if not dry_run:
                _write_sheet(path, assessment.grade_cell, drawn[identifier])
            written.setdefault(identifier, []).append(path)

    workbooks = _fill_grader_workbooks(assessment, reported, dry_run=dry_run)

    return SimulatedMarking(
        marks=drawn,
        sheets=written,
        skipped=skipped,
        workbooks=workbooks,
        discrepancies=planted,
        dry_run=dry_run,
    )


def _fill_grader_workbooks(
    assessment: Assessment,
    marks: Mapping[str, float],
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Copy the marks into each grader's workbook, as the grader would."""
    filled: dict[str, int] = {}
    for grader in (g.initials for g in assessment.graders):
        path = assessment.grading_output_path / f"{grader}.xlsx"
        if not path.exists():
            continue

        frame = pd.read_excel(path, dtype={"Student ID": str})
        key = _key_column(frame)
        keys = frame[key].astype(str)
        values = keys.map(lambda k: marks.get(k))
        if MARK_COLUMN in frame.columns:
            # Only fill what the grader has not already written.
            frame[MARK_COLUMN] = frame[MARK_COLUMN].where(
                frame[MARK_COLUMN].notna(), values
            )
        else:
            frame[MARK_COLUMN] = values

        filled[grader] = int(values.notna().sum())
        if not dry_run:
            frame.to_excel(path, index=False)
    return filled


# ---------------------------------------------------------------------------
# From a terminal
# ---------------------------------------------------------------------------


def _assessments_to_mark(module: Module, wanted: str | None) -> list[Assessment]:
    if wanted is not None:
        return [module.assessment(wanted)]
    # Everything a human marks on a sheet. A quiz has no feedback sheet and
    # nobody marks it, which is why its section of the walkthrough is four
    # cells against the coursework's ten.
    return [a for a in module.assessments if a.grade_cell is not None]


def _seed_for(seed: int | None, assessment: Assessment) -> int | None:
    """One seed per assessment, derived from the one the caller gave.

    Handing every assessment the same seed gives every student the same mark
    in cw1 as in cw2, which is reproducible and useless: the module total
    then equals the component, and a weighting bug looks exactly like a
    correct answer. crc32 of the id rather than ``hash``, which is salted
    per process, so a seed still means the same cohort tomorrow.
    """
    if seed is None:
        return None
    return seed + zlib.crc32(assessment.id.encode("utf-8"))


def main(argv: "Sequence[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m grader_helper.simulating",
        description=(
            "Fill in marks nobody marked, so the rest of the pipeline can be "
            "run. Writes into real files -- point it at a scratch copy."
        ),
    )
    parser.add_argument("module", type=pl.Path, help="The module folder, or its module.toml.")
    parser.add_argument(
        "-a", "--assessment", default=None,
        help="Which assessment. Default: every one with a grade_cell.",
    )
    parser.add_argument(
        "--write", action="store_true",
        help="Actually write. Without it you get the plan and nothing else.",
    )
    parser.add_argument("--seed", type=int, default=None, help="For a reproducible cohort.")
    parser.add_argument(
        "--boundaries", type=int, default=3,
        help="Marks placed on band edges and awkward halves. Default 3.",
    )
    parser.add_argument(
        "-d", "--discrepancies", type=int, default=0,
        help="Marks the grader mistypes into their workbook, for reconciliation.",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Mark sheets that already carry a number.",
    )
    args = parser.parse_args(argv)

    module = load_module(args.module)
    print(f"{module.code} -- {module.name}  ({module.root})")

    for assessment in _assessments_to_mark(module, args.assessment):
        try:
            result = simulate_marking(
                assessment,
                seed=_seed_for(args.seed, assessment),
                boundaries=args.boundaries,
                discrepancies=args.discrepancies,
                overwrite=args.overwrite,
                dry_run=not args.write,
            )
        except (ValueError, NotADirectoryError) as exc:
            print(f"  {assessment.id}: skipped -- {exc}")
            continue

        print(f"  {assessment.id}: {result}")
        for identifier, (sheet, workbook) in sorted(result.discrepancies.items()):
            print(f"      planted: {identifier} sheet {sheet} vs workbook {workbook}")

    if not args.write:
        print("\nNothing was written. Pass --write to do it for real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
