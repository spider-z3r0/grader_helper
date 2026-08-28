#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Choose whose work goes to the internal moderator.

A stratified draw: *n* students per letter grade, so the moderator sees the
range rather than whoever happens to be at the top of the list. On top of
that, two deliberate additions:

``also=``
    students the module leader wants a second opinion on regardless of band.
``borderline=``
    students within a point of the next grade up -- see :mod:`borderline`.

**The draw is recorded, not repeated.** A random sample that comes out
different every time it runs is not a sample, it is a lottery: nobody can
answer "why was this student moderated?" six months later, and re-running
quietly swaps the answer. So every draw carries the seed that produced it,
and the seed is part of what gets written down. Given the seed and the marks,
anyone can reproduce the selection exactly.

House convention: ``pl`` is pathlib, ``pr`` is polars.

    >>> import pathlib as pl
    >>> import polars as pr
"""

import random
from typing import Iterable, NamedTuple

from ..dataframe_operations.make_letter_grade import NO_PARTICIPATION
from ..dependencies import pd
from .borderline import BORDERLINE_COLUMN, DEFAULT_TOLERANCE, flag_borderline

#: Why a student is in the sample. One row can be picked for more than one
#: reason, and the reason is recorded because it is what the moderator and
#: the external examiner will ask about.
DRAWN = "drawn"
BORDERLINE = "borderline"
REQUESTED = "requested"

#: The column naming why each student was selected.
REASON_COLUMN = "Selected Because"

#: What to do about students near a grade boundary.
#:
#: "flag"    -- work them out and mark them, but do not select them. The
#:              default, and what the department does today.
#: "include" -- select every borderline student as well as the random draw.
#:              What the department is discussing doing *instead* of the
#:              per-band sample, so it is here ready rather than guessed at.
#: "ignore"  -- do not compute them at all.
BORDERLINE_MODES = ("flag", "include", "ignore")


class Sample(NamedTuple):
    """A moderation selection, and everything needed to justify it.

    The seed is not decoration. It is the difference between a sample that
    can be defended and one that cannot be repeated.
    """

    #: The selected students, with the reason each was chosen.
    selected: pd.DataFrame
    #: Every student, with the borderline columns added. What the module
    #: leader eyeballs before accepting the draw.
    considered: pd.DataFrame
    #: The seed that produced this draw.
    seed: int
    #: Students per band asked for.
    n: int
    #: Bands with fewer students than `n`, and how many each had. Not an
    #: error -- a band with one student in it can only offer one -- but the
    #: moderator should know the sample is thinner there than requested.
    short_bands: dict[str, int]

    def __str__(self) -> str:
        return (
            f"{len(self.selected)} of {len(self.considered)} students, "
            f"n={self.n} per band, seed={self.seed}"
        )


def sample_for_moderation(
    df: pd.DataFrame,
    n: int = 1,
    seed: int | None = None,
    also: Iterable[str] = (),
    borderline: str = "flag",
    tolerance: float = DEFAULT_TOLERANCE,
    grade_column: str = "Letter Grade",
    id_column: str = "Student ID",
) -> Sample:
    """
    Draw the internal moderation sample.

    Args:
    df (pd.DataFrame): A prepared marks frame, as
        `prepare_data_for_departmental_template` returns it -- one row per
        student, with a letter grade.
    n (int): Students per grade band. Defaults to 1.
    seed (int | None): The seed for the draw. Defaults to None, which
        generates one and returns it in the result, so it can be written
        down. Pass a seed back to reproduce a previous draw exactly.
    also (Iterable[str]): Student ids to include whatever their band -- the
        cases the module leader wants a second opinion on.
    borderline (str): One of "flag", "include" or "ignore". See
        BORDERLINE_MODES.
    tolerance (float): How near the next grade counts as borderline.
    grade_column (str): The column holding the letter grade.
    id_column (str): The column holding the student id.

    Returns:
    Sample: The selection, everything considered, the seed, and any bands
    that could not fill their quota.

    Note:
        **No participation is never sampled.** A student who submitted
        nothing has nothing to moderate, and an NG folder containing no work
        is a job that looks done and is not.

        A band with fewer than `n` students contributes everyone it has and
        is named in `short_bands`, rather than the shortfall passing without
        comment.

    Raises:
    ValueError: If the frame is empty or missing the grade or id column, if
        `n` is not positive, or if `borderline` is not a known mode.

    Example:
        >>> sample = sample_for_moderation(sheet, n=1)
        >>> sample.seed          # write this down
        >>> sample.selected[["Student ID", "Letter Grade", "Selected Because"]]
    """
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a pandas DataFrame")
    if df.empty:
        raise ValueError("DataFrame is empty, so there is nobody to sample")
    if n < 1:
        raise ValueError(f"n must be at least 1, not {n}")
    if borderline not in BORDERLINE_MODES:
        raise ValueError(
            f"borderline must be one of {list(BORDERLINE_MODES)}, not "
            f"{borderline!r}"
        )
    for column in (grade_column, id_column):
        if column not in df.columns:
            raise ValueError(
                f"DataFrame has no {column!r} column. Run "
                "prepare_data_for_departmental_template first; it produces "
                "the shape this expects."
            )

    if seed is None:
        # Chosen here rather than left to the global random state, so it can
        # be returned and recorded. An unrecorded seed is the same as none.
        seed = random.SystemRandom().randrange(2**31)

    considered = (
        df.copy()
        if borderline == "ignore"
        else flag_borderline(df, tolerance=tolerance)
    )

    # Reasons accumulate per student id, because one student can be both the
    # random draw for their band and a borderline case, and the moderator
    # should see both.
    reasons: dict[str, list[str]] = {}

    def note(student_id, reason: str) -> None:
        reasons.setdefault(str(student_id), []).append(reason)

    eligible = considered[considered[grade_column] != NO_PARTICIPATION]

    short_bands: dict[str, int] = {}
    rng = random.Random(seed)
    for band in sorted(eligible[grade_column].dropna().unique()):
        in_band = eligible[eligible[grade_column] == band]
        ids = sorted(str(value) for value in in_band[id_column])
        if len(ids) < n:
            short_bands[str(band)] = len(ids)
        for student_id in rng.sample(ids, min(n, len(ids))):
            note(student_id, DRAWN)

    if borderline == "include":
        for student_id in eligible.loc[eligible[BORDERLINE_COLUMN], id_column]:
            note(student_id, BORDERLINE)

    # Requested students are honoured even where the band filter would not
    # have reached them -- if the leader wants a second opinion on someone,
    # that is not ours to overrule.
    wanted = {str(value) for value in also}
    known = {str(value) for value in considered[id_column]}
    unknown = sorted(wanted - known)
    if unknown:
        raise ValueError(
            f"Asked to moderate student(s) not in the marks: {unknown}. "
            "Check the ids against the class list -- a typo here means "
            "somebody the leader wanted looked at silently is not."
        )
    for student_id in sorted(wanted):
        note(student_id, REQUESTED)

    selected = considered[
        considered[id_column].astype(str).isin(reasons)
    ].copy()
    selected[REASON_COLUMN] = [
        ", ".join(sorted(set(reasons[str(value)])))
        for value in selected[id_column]
    ]

    return Sample(
        selected=selected.reset_index(drop=True),
        considered=considered,
        seed=seed,
        n=n,
        short_bands=short_bands,
    )
