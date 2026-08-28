#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Where everything goes in the departmental grade sheet, for any module shape.

The committed template (``Dept grade sheet Template 2026.xlsx``, tab
``GradeTemplate``) is one module's shape written out by hand: two courseworks
and an MCQ. Its formulas hardcode that -- ``D=C/100*40``, ``F=E/2``, and a
total summing exactly ``D, F, G``. A module with four assessments, or
different weights, does not fit, and until now the module leader reshaped the
block by hand.

That hand-editing is where the mistakes happen, and it is worth being precise
about why. Only two things in the sheet move when the assessment block
changes width, and both are the ones a human gets wrong:

* the **descriptives** at A23 -- Mean, SD and N, one formula per column, so a
  block one column wider silently leaves the last assessment out of the
  summary;
* the **Letter Grade** column and the distribution ``COUNTIF``s that read it
  -- a nested ``IF`` ten levels deep whose every reference has to move.

Everything else -- the band table at A5:E17, the QPV column, the other four
sheets -- is fixed furniture and is never touched.

This module holds the arithmetic of that layout and nothing else: no Excel,
no files, no I/O. Given a :class:`~grader_helper.models.Module` it can say
which column each assessment lands in and what formula belongs in each cell.
:mod:`build_departmental_sheet` does the openpyxl work on top of it.

House convention: ``pl`` is pathlib, ``pr`` is polars.

    >>> import pathlib as pl
    >>> import polars as pr
"""

from dataclasses import dataclass
from typing import Sequence

from openpyxl.utils import get_column_letter

from ..dataframe_operations.sort_order_columns import (
    LEADING_COLUMNS,
    TRAILING_COLUMNS,
)
from ..models import Assessment, Module, tidy_number

#: The tab marks go into. The other four sheets are guidance and moderation.
SHEET_NAME = "GradeTemplate"

#: Row 29 holds the column headers; students start on the row after it.
HEADER_ROW = 29
FIRST_DATA_ROW = 30

#: The last row the template rules for students, giving 501 of them. Fixed
#: by the department's file, not by us -- a bigger cohort is refused rather
#: than silently written past the end of the ruled block.
LAST_DATA_ROW = 530

#: Rows 8..17 of the band table: A lower bound, B upper bound, C letter.
#: Row 7 is `No participation` and is the formula's else branch, not a band.
FIRST_BAND_ROW = 8
LAST_BAND_ROW = 17

#: Column C of the band table, read to build the letter-grade formula.
BAND_LETTER_COLUMN = 3

#: The distribution block: grade names in G6:G16, counts beside them in H.
FIRST_DISTRIBUTION_ROW = 6
LAST_DISTRIBUTION_ROW = 16
DISTRIBUTION_GRADE_COLUMN = 7
DISTRIBUTION_COUNT_COLUMN = 8

#: The descriptives under the block. This is the half of the sheet that goes
#: wrong most often by hand, because there is one formula per column and
#: nothing complains when the last one is missing.
MEAN_ROW = 23
SD_ROW = 24
N_ROW = 25

#: The sheet's own names for the identifying and derived columns -- the
#: strings in row 29.
#:
#: Imported from `sort_order_columns` rather than restated here, and that is
#: load-bearing: it orders a marks frame by the same tuples this lays the sheet
#: out by, so a prepared frame and the sheet it is written into agree by
#: construction instead of by two lists happening to match. Renaming a column
#: in one place now breaks the other visibly.
NAME_COLUMN, ID_COLUMN = LEADING_COLUMNS
TOTAL_COLUMN, LETTER_COLUMN, COMMENTS_COLUMN = TRAILING_COLUMNS


@dataclass(frozen=True)
class DepartmentalLayout:
    """Which column of the grade sheet each of a module's columns lands in.

    Built by :meth:`for_module`. Holds the header row and nothing else --
    every position is derived from it, so there is one place where the sheet's
    shape is decided.

    Example:
        >>> layout = DepartmentalLayout.for_module(module)
        >>> layout.headers[:2]
        ['Name', 'Student ID']
        >>> layout.letter_for(module.assessments[0].raw_column)
        'C'
    """

    headers: tuple[str, ...]
    module: Module

    # ------------------------------------------------------------ construction

    @classmethod
    def for_module(cls, module: Module) -> "DepartmentalLayout":
        """Lay a module out in departmental order.

        Name, Student ID, then each assessment's columns in declared order --
        raw first, weighted after it where the piece is not already marked on
        its contribution -- then the total, the letter grade and comments.

        Raises:
        ValueError: If the module declares no assessments, so there is no
            sheet to lay out.
        """
        if not isinstance(module, Module):
            raise ValueError(
                "module must be a Module. Load it with load_module(), which "
                "reads module.toml and tells this function the module's shape "
                "rather than leaving it to guess from column names."
            )
        if not module.assessments:
            raise ValueError(
                f"Module {module.code} declares no assessments, so there is "
                "no grade sheet to lay out. Add an [[assessment]] to "
                "module.toml."
            )
        headers = (
            *LEADING_COLUMNS,
            *module.grade_sheet_columns,
            *TRAILING_COLUMNS,
        )
        return cls(headers=headers, module=module)

    # ----------------------------------------------------------------- lookups

    def index_for(self, header: str) -> int:
        """The 1-based column number holding `header`."""
        try:
            return self.headers.index(header) + 1
        except ValueError:
            raise KeyError(
                f"{header!r} is not a column of this sheet. It holds: "
                f"{list(self.headers)}"
            ) from None

    def letter_for(self, header: str) -> str:
        """The column letter holding `header`, e.g. 'C'."""
        return get_column_letter(self.index_for(header))

    @property
    def last_column(self) -> int:
        return len(self.headers)

    @property
    def assessment_headers(self) -> tuple[str, ...]:
        """Every assessment column, raw and weighted, in sheet order."""
        return tuple(self.module.grade_sheet_columns)

    @property
    def raw_headers(self) -> tuple[str, ...]:
        """The columns a mark is written into -- the only ones we ever write."""
        return tuple(a.raw_column for a in self.module.assessments)

    def contributing_header(self, assessment: Assessment) -> str:
        """The column that reaches the total for this assessment.

        The weighted column where the piece is marked out of more than it is
        worth, and the raw column where the two numbers are equal and there is
        nothing to weight. Getting this wrong is how an assessment silently
        drops out of every student's total.
        """
        return assessment.weighted_column or assessment.raw_column

    @property
    def summary_headers(self) -> tuple[str, ...]:
        """The columns the descriptives cover: every assessment, plus the total.

        Read off the template, which runs Mean/SD/N from C to H -- the whole
        assessment block and the total, but not the letter grade or comments.
        """
        return (*self.assessment_headers, TOTAL_COLUMN)

    def count_source_for(self, header: str) -> str:
        """The column an N formula counts for `header`.

        The template counts the *raw* column in every case: ``D25`` is
        ``COUNT(C30:C530)``, not ``COUNT(D30:D530)``. That is deliberate for a
        weighted column -- the weighting formula is present in all 501 rows, so
        counting it would return 501 every time regardless of how many students
        were marked. ``H25`` counting ``G`` follows from the same fill and has
        the same effect: the total, too, carries a formula in every row.

        So the rule that reproduces the template exactly is *the nearest raw
        column at or before this one*, and it is the honest one as well: N
        means "students with a mark", and only a raw column knows that.
        """
        index = self.index_for(header)
        raw_indices = [self.index_for(h) for h in self.raw_headers]
        earlier = [i for i in raw_indices if i <= index]
        if not earlier:
            raise KeyError(
                f"No raw mark column at or before {header!r}, so there is "
                "nothing to count. This means the sheet's assessment block is "
                "laid out wrongly."
            )
        return self.headers[max(earlier) - 1]

    # ---------------------------------------------------------------- formulas

    def weighting_formula(self, assessment: Assessment, row: int) -> str:
        """The weighted column's formula, e.g. ``=C30/100*40`` or ``=E30/2``.

        The template writes weightings two ways -- ``=C30/100*40`` for a
        coursework worth 40, and the shorter ``=E30/2`` for one worth 50 -- and
        the difference is not cosmetic, which is the whole reason this picks
        between them rather than settling on the tidier-looking long form.

        ``x/2`` is exact in binary floating point. ``x/100*50`` is two roundings
        and is not: the two disagree by up to 1.4e-14, and because the total is
        ``ROUND(SUM(...),0)`` that is enough to move a mark. On marks in half
        points, ``cw2 = 29`` gives ``14.5`` one way and ``14.499999999999998``
        the other, which Excel rounds to 15 and 14 -- a whole mark, and at a
        band boundary a different letter grade. Thirteen such disagreements
        exist on that grid alone.

        So: divide by a whole number where the weight goes into the marks
        exactly, and use the department's general ``/marks_out_of*weight``
        otherwise. On the template's own shape that yields their two formulas
        back, character for character, which is the point -- where the sheet
        has an answer it is the answer, wobbles included, because it is the
        mark the student is actually given.
        """
        raw = self.letter_for(assessment.raw_column)
        divisor = assessment.marks_out_of / assessment.weight
        if divisor > 0 and float(divisor).is_integer():
            return f"={raw}{row}/{tidy_number(divisor)}"
        return (
            f"={raw}{row}/{tidy_number(assessment.marks_out_of)}"
            f"*{tidy_number(assessment.weight)}"
        )

    def total_formula(self, row: int) -> str:
        """The total's formula: ``=ROUND(SUM(D30,F30,G30),0)``.

        Sums each assessment's *contributing* column and rounds once, at the
        end. Rounding the components instead moves the total and can cross a
        band boundary -- see the notes' "Rounding, two rules, both
        grade-affecting".
        """
        cells = ",".join(
            f"{self.letter_for(self.contributing_header(a))}{row}"
            for a in self.module.assessments
        )
        return f"=ROUND(SUM({cells}),0)"

    def letter_grade_formula(self, row: int, band_letters: Sequence[str]) -> str:
        """The nested ``IF`` that reads the total off the band table.

        `band_letters` comes from column C of the band table in the workbook
        being written, ascending from :data:`FIRST_BAND_ROW`, so the formula
        follows the department's own bands rather than a copy of them here. If
        they retire a grade, the generated sheet retires it too.

        Two details are the sheet's and are reproduced rather than reasoned
        about: the top band closes with ``<=`` where every other band uses
        ``<``, and a total that is not greater than zero is ``NG`` -- no
        participation, which is not the same as a very low mark and is excluded
        from the average QPV.
        """
        total = f"ROUND({self.letter_for(TOTAL_COLUMN)}{row},2)"
        last_row = FIRST_BAND_ROW + len(band_letters) - 1
        branches = []
        for offset, letter in enumerate(band_letters):
            band_row = FIRST_BAND_ROW + offset
            comparison = "<=" if band_row == last_row else "<"
            branches.append(
                f"IF(AND({total}>=$A${band_row},"
                f"{total}{comparison}$B${band_row}),\"{letter}\","
            )
        closing = ")" * len(branches)
        return f"=IF({total}>0,{''.join(branches)}\"NG\"{closing},\"NG\")"

    def mean_formula(self, header: str) -> str:
        """``=AVERAGEIF(C30:C530, "> 0")`` -- the sheet's own spacing included."""
        column = self.letter_for(header)
        return (
            f'=AVERAGEIF({column}{FIRST_DATA_ROW}:{column}{LAST_DATA_ROW}, "> 0")'
        )

    def sd_formula(self, header: str) -> str:
        """The sample SD over the non-zero numeric marks.

        A dynamic-array formula, so it carries the ``_xlfn`` / ``_xlws``
        prefixes openpyxl needs for functions newer than the file format.
        Written into the sheet as an ArrayFormula.
        """
        column = self.letter_for(header)
        span = f"{column}{FIRST_DATA_ROW}:{column}{LAST_DATA_ROW}"
        return (
            f"=_xlfn.STDEV.S(_xlfn._xlws.FILTER({span}, "
            f"({span}<>0) * ISNUMBER({span})))"
        )

    def count_formula(self, header: str) -> str:
        """``=COUNT(C30:C530)`` over this column's raw source."""
        column = self.letter_for(self.count_source_for(header))
        return f"=COUNT({column}{FIRST_DATA_ROW}:{column}{LAST_DATA_ROW})"

    def distribution_formula(self, grade: str) -> str:
        """``=COUNTIF(I30:I530,"A1")`` against wherever the letter column landed.

        This is the other half of the hand-editing problem: the counts sit in a
        fixed block beside the band table, but every one of them points at the
        Letter Grade column, which moves whenever the assessment block does.
        """
        column = self.letter_for(LETTER_COLUMN)
        return (
            f'=COUNTIF({column}{FIRST_DATA_ROW}:{column}{LAST_DATA_ROW},"{grade}")'
        )
