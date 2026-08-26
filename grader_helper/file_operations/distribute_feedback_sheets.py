#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Put a blank feedback sheet into each submission folder.

Folder names arrive in one of two shapes, depending on what has already run:

    "27236-46025 - 23304308 Angood - 05 March 2026 612 PM"   Brightspace
    "ANGOOD, KEVIN(23304308)"                                UL, alphabetised

Both are accepted. The previous implementation matched only the second --
``r"\\((\\d+)\\)"``, an id in parentheses -- so running it on a freshly
unzipped download found nothing and said so once per folder. That ordering
dependency on ``alphabetise_folders`` was real but undocumented, and is now
simply gone.
"""

import pathlib as pl
import re
from shutil import copy2
from typing import NamedTuple

from .scan_multiple_submissions import parse_brightspace_folder

#: The UL form, as produced by alphabetise_folders: "ANGOOD, KEVIN(23304308)".
_UL_ID = re.compile(r"\((\d+)\)")

#: A group folder, e.g. " - Team 3 - " or " - Group 12 - ". The label was
#: previously hardcoded to "Team", so a module that called its groups
#: anything else silently received no feedback sheets at all.
_GROUP = re.compile(r"(?<= - )(?:Team|Group)\s*(\d+)(?= - )", re.IGNORECASE)


class Distribution(NamedTuple):
    """What a distribution run actually did.

    Returned rather than printed. A caller needs to know that eight of forty
    students got a sheet, and the dashboard cannot read stdout.
    """

    copied: dict[str, pl.Path]
    #: Folders that already had a sheet. Not an error -- a re-run is normal.
    skipped: dict[str, pl.Path]
    #: Directories carrying no recognisable id, by name.
    unmatched: list[str]

    def __str__(self) -> str:
        return (
            f"{len(self.copied)} copied, {len(self.skipped)} already present, "
            f"{len(self.unmatched)} unrecognised"
        )


def student_id_from_folder(name: str) -> str | None:
    """The student id in a submission folder name, whichever form it is in."""
    match = _UL_ID.search(name)
    if match:
        return match.group(1)

    parsed = parse_brightspace_folder(name)
    return parsed[0] if parsed else None


def group_id_from_folder(name: str) -> str | None:
    """The group label in a group submission folder, e.g. "Team 3"."""
    match = _GROUP.search(name)
    if not match:
        return None
    return f"{match.group(0).split()[0].title()} {match.group(1)}"


def _distribute(
    subs_folder: pl.Path,
    rubric: pl.Path,
    identify,
    overwrite: bool = False,
) -> Distribution:
    """Copy ``rubric`` into every folder ``identify`` can name."""
    subs_folder = pl.Path(subs_folder)
    rubric = pl.Path(rubric)

    if not rubric.exists():
        raise FileNotFoundError(f"{rubric} does not exist.")
    if not subs_folder.is_dir():
        raise NotADirectoryError(
            f"{subs_folder} is not a directory. This should be the unzipped "
            "folder of submissions downloaded from Brightspace."
        )

    copied: dict[str, pl.Path] = {}
    skipped: dict[str, pl.Path] = {}
    unmatched: list[str] = []

    for folder in sorted(subs_folder.iterdir()):
        if not folder.is_dir():
            continue

        identifier = identify(folder.name)
        if identifier is None:
            unmatched.append(folder.name)
            continue

        target = folder / f"Feedback sheet {identifier}.xlsx"
        if target.exists() and not overwrite:
            # A sheet already there may hold marks. Never clobber it by
            # default -- re-running the distribution is a normal thing to do.
            skipped[identifier] = target
            continue

        copy2(rubric, target)
        copied[identifier] = target

    return Distribution(copied, skipped, unmatched)


def distribute_feedback_sheets(
    subs_folder: pl.Path, rubric_name: pl.Path, overwrite: bool = False
) -> Distribution:
    """
    Copy a blank feedback sheet into each student's submission folder.

    Args:
    subs_folder (pl.Path): The unzipped folder of submissions.
    rubric_name (pl.Path): The blank feedback sheet to copy.
    overwrite (bool): Replace a sheet that is already there. Defaults to
        False, because an existing sheet may already carry marks.

    Returns:
    Distribution: What was copied, skipped and not recognised.

    Raises:
    FileNotFoundError: If the rubric does not exist.
    NotADirectoryError: If ``subs_folder`` is not a directory.
    """
    return _distribute(subs_folder, rubric_name, student_id_from_folder, overwrite)


def distribute_feedback_sheets_groups(
    subs_folder: pl.Path, rubric_name: pl.Path, overwrite: bool = False
) -> Distribution:
    """
    Copy a blank feedback sheet into each group's submission folder.

    Accepts "Team" or "Group" as the label, in any case. Args and exceptions
    are as :func:`distribute_feedback_sheets`.
    """
    return _distribute(subs_folder, rubric_name, group_id_from_folder, overwrite)
