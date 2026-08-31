#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Does the mark the student received match the one the department gets?

Between the two records sits a human copying a number by hand. A grader fills
in the feedback sheet, reads the mark off it, and types that mark into their
own grade sheet; the student is shown the first and the department is sent the
second. Nothing checks that the two are the same number, which is why
:func:`~grader_helper.catch_grades` and
:func:`~grader_helper.ingest_completed_graderfiles` both exist -- they are two
halves of one audit, not alternatives, and this is the half that compares
them.

    >>> import pathlib as pl
    >>> from grader_helper import catch_grades, reconcile_marks
    >>> received = catch_grades(assessment.submissions_path, assessment.grade_cell)
    >>> reconcile_marks(received, collated).agree
    True

**Not every disagreement is a fault**, so they are separated rather than
counted. A student who never submitted still gets allocated a grader from the
class list, so they appear in the collated file with no feedback sheet to read
-- which is normal, and looks identical to a lost mark if all you have is a
number.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

from typing import NamedTuple

import pandas as pd


class Reconciliation(NamedTuple):
    """The two records compared, and where they part company."""

    #: Every student in either record, with both marks and a ``_merge``
    #: column saying which records they appeared in.
    comparison: pd.DataFrame

    #: The rows that do not agree, of any kind.
    disagreements: pd.DataFrame

    #: The column holding the mark read off the feedback sheet.
    received_column: str

    #: The column holding the mark the grader reported.
    reported_column: str

    @property
    def agree(self) -> bool:
        """True when every student's two records say the same thing."""
        return self.disagreements.empty

    @property
    def not_submitted(self) -> pd.DataFrame:
        """Collated, but with no feedback sheet to read.

        Usually a student who never submitted: they are on the class list, so
        a grader was allocated them, but there is nothing to mark. Normal, and
        worth seeing rather than hiding.
        """
        return self.comparison[self.comparison["_merge"] == "right_only"]

    @property
    def not_allocated(self) -> pd.DataFrame:
        """Marked, but nobody was allocated them.

        Always worth a look: a feedback sheet exists for a student no grader
        was given, so either the allocation missed them or the sheet is in the
        wrong folder.
        """
        return self.comparison[self.comparison["_merge"] == "left_only"]

    @property
    def transcription_slips(self) -> pd.DataFrame:
        """In both records, with two different marks.

        The failure this whole audit exists for: the number on the student's
        sheet is not the number the department will be sent.
        """
        both = self.comparison["_merge"] == "both"
        return self.disagreements[self.disagreements.index.isin(
            self.comparison[both].index
        )]

    def __str__(self) -> str:
        if self.agree:
            return (
                f"{len(self.comparison)} students compared, every mark agrees"
            )
        return (
            f"{len(self.comparison)} students compared, "
            f"{len(self.disagreements)} disagreements: "
            f"{len(self.transcription_slips)} differing marks, "
            f"{len(self.not_submitted)} collated without a feedback sheet, "
            f"{len(self.not_allocated)} marked without an allocation"
        )


def reconcile_marks(
    received: pd.DataFrame,
    reported: pd.DataFrame,
    id_column: str = "Student ID",
    received_column: str = "grade",
    reported_column: str = "Mark",
) -> Reconciliation:
    """
    Compare what the students were given with what the graders reported.

    Args:
    received (pd.DataFrame): What `catch_grades` read off the feedback sheets
        -- the mark each student actually saw.
    reported (pd.DataFrame): The collated grader sheets, from
        `ingest_completed_graderfiles` -- the mark the department will be sent.
    id_column (str): The student id, in both frames. Read as text everywhere in
        this package, because an id read as a number loses its leading zero and
        then matches nothing.
    received_column (str): Where the mark is in ``received``.
    reported_column (str): Where the mark is in ``reported``.

    Returns:
    Reconciliation: The full comparison, the disagreements, and the three
        kinds of disagreement told apart.

    Raises:
    KeyError: If either frame is missing the id or mark column named.
    ValueError: If the two id columns cannot be merged -- which in practice
        means one of them was read as a number.

    Example:
        >>> reconcile_marks(received, reported).agree
        True
    """
    for frame, name, column in (
        (received, "received", received_column),
        (reported, "reported", reported_column),
    ):
        missing = [c for c in (id_column, column) if c not in frame.columns]
        if missing:
            raise KeyError(
                f"The {name} marks have no {missing} column. Columns present: "
                f"{list(frame.columns)}."
            )

    try:
        comparison = received.merge(
            reported[[id_column, reported_column]],
            on=id_column,
            how="outer",
            indicator=True,
        )
    except ValueError as exc:
        # pandas refuses to merge an object column against an int64 one, which
        # is the shape this takes when a student id was read as a number
        # somewhere upstream. Loud is right -- a merge that silently matched
        # nothing would report every student twice and agree with none.
        raise ValueError(
            f"The two records' {id_column!r} columns cannot be compared: "
            f"{exc}. Student ids must be read as text on both sides, or the "
            "leading zeros are gone and nothing matches."
        ) from exc

    both = comparison["_merge"] == "both"
    marks_match = comparison[received_column] == comparison[reported_column]
    # Two blanks are not a disagreement. Nobody marked that student, and the
    # two records agree about it -- an unmarked student is a different problem,
    # caught by the mark being missing rather than by the two copies differing.
    both_blank = (
        comparison[received_column].isna() & comparison[reported_column].isna()
    )

    disagreements = comparison[~(both & (marks_match | both_blank))]

    return Reconciliation(
        comparison=comparison,
        disagreements=disagreements,
        received_column=received_column,
        reported_column=reported_column,
    )
