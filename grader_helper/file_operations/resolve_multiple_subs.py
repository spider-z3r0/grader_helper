#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Deciding which of a student's submissions counts, and removing the rest.

Brightspace keeps every attempt, so a student who submits twice arrives as
two folders. ``alphabetise_folders`` refuses to rename anything while that is
true -- two folders for one student cannot both become
``SURNAME, NAME(id)`` -- so somebody has to decide which one counts before
any marking can be set up.

**That decision is the module leader's**, which is why ``keep`` has no
default. Whether a resubmission supersedes the first attempt or arrived after
the deadline and does not count is a matter of the module's own rules, and a
tool that picked one would be quietly making an academic judgement.

Two calls, so the choice can be seen before it is acted on::

    >>> import pathlib as pl
    >>> plan = resolve_multiple_subs(submissions, keep="latest")
    >>> plan.removed                       # nothing has happened yet
    [PosixPath('.../23304307 Egan - 01 March 2026 900 AM')]
    >>> resolve_multiple_subs(submissions, keep="latest", apply=True)

Ordering is by the timestamp in the folder name, never by the name itself.
Sorted as text, ``01 April`` comes before ``05 March``, so "keep the
earliest" would keep the April submission -- the wrong one, silently, and
only for students who happen to straddle a month.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import datetime as dt
import pathlib as pl
import shutil
from typing import NamedTuple

from .scan_multiple_submissions import parse_brightspace_folder

#: The two answers to "which one counts?".
KEEP_CHOICES = ("earliest", "latest")


class Resolution(NamedTuple):
    """What was kept, what was removed, and whether it has happened yet."""

    #: Student id -> the folder that counts.
    kept: dict[str, pl.Path]

    #: The folders removed, or that would be removed by a plan.
    removed: list[pl.Path]

    #: Which submission was treated as the one that counts.
    keep: str

    #: False for a plan, True once the folders are gone.
    applied: bool

    def __bool__(self) -> bool:
        """True when there was anything to resolve."""
        return bool(self.removed)

    def __str__(self) -> str:
        if not self.removed:
            return "no student submitted more than once"
        verb = "removed" if self.applied else "would remove"
        return (
            f"{len(self.kept)} student(s) submitted more than once; "
            f"keeping the {self.keep}, {verb} {len(self.removed)} folder(s)"
        )


def resolve_multiple_subs(
    subs_folder: pl.Path,
    keep: str,
    *,
    apply: bool = False,
) -> Resolution:
    """
    Keep one submission per student and remove the others.

    Args:
    subs_folder (pl.Path): The unzipped Brightspace download.
    keep (str): ``"earliest"`` or ``"latest"`` -- which attempt counts. No
        default: whether a resubmission supersedes the first attempt is the
        module's rule, not this package's.
    apply (bool): Whether to actually delete. Defaults to False, which
        returns the same answer without touching anything, so the choice can
        be shown to whoever is making it before it is acted on.

    Returns:
    Resolution: The folder kept per student, the folders removed (or that
        would be), and whether it happened.

    Raises:
    ValueError: If ``keep`` is not one of ``KEEP_CHOICES``.
    RuntimeError: If ``subs_folder`` is not a directory.

    Example:
        >>> resolve_multiple_subs(submissions, keep="latest", apply=True)
    """
    if keep not in KEEP_CHOICES:
        raise ValueError(
            f"keep must be one of {KEEP_CHOICES}, not {keep!r}. Which "
            "submission counts is the module leader's decision, so there is "
            "no default."
        )
    subs_folder = pl.Path(subs_folder)
    if not subs_folder.is_dir():
        raise RuntimeError(f"{subs_folder} is not a directory.")

    # Only folders directly inside the submissions folder, and only ones that
    # parse as Brightspace's own format. Anything already alphabetised, and
    # anything a person put there, is not ours to touch.
    submissions: dict[str, list[tuple[dt.datetime, pl.Path]]] = {}
    for folder in subs_folder.iterdir():
        if not folder.is_dir():
            continue
        parsed = parse_brightspace_folder(folder.name)
        if parsed is None:
            continue
        student_id, submitted_at = parsed
        submissions.setdefault(student_id, []).append((submitted_at, folder))

    kept: dict[str, pl.Path] = {}
    removed: list[pl.Path] = []
    for student_id, attempts in submissions.items():
        if len(attempts) < 2:
            continue
        # By timestamp, never by folder name.
        attempts.sort(key=lambda pair: pair[0])
        chosen = attempts[0] if keep == "earliest" else attempts[-1]
        kept[student_id] = chosen[1]
        removed.extend(folder for _, folder in attempts if folder != chosen[1])

    if apply:
        for folder in removed:
            shutil.rmtree(folder)

    return Resolution(kept=kept, removed=removed, keep=keep, applied=apply)
