#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Rename folders back to Brightspace format, ready for re-upload.

The counterpart to ``alphabetise_folders``, and the last step before marked
work goes back up -- so a wrong name here reaches students.

It is fed the rename log that ``alphabetise_folders`` wrote, read back from
``folder_rename_log.csv``. That log has two columns: ``Original Name``, as
Brightspace wrote it, and ``Suggested Name``, the UL form the folders were
renamed to. Going back means looking a folder up by its UL name and restoring
its original.

**Matching is case-insensitive; the name written is not.** Those are two
different things, and conflating them was the defect: both columns were
upper-cased in place and the upper-cased original was then used as the new
folder name, so

    27236-46025 - 23304302 Barry - 01 March 2026 600 PM     went in
    27236-46025 - 23304302 BARRY - 01 MARCH 2026 600 PM     came back

on 11 of 12 folders. Upper case belongs in the lookup key only.
"""

from typing import NamedTuple

from ..dependencies import pd, pl

#: Written beside the submissions, as before.
LOG_FILENAME = "folder_brightspace_name_log.csv"
UNFOUND_FILENAME = "folder_brightspace_name_unfound.csv"


class Restoration(NamedTuple):
    """What a rename-back run actually did.

    Returned rather than printed. The caller needs to know that three of
    forty folders were not recognised before uploading anything, and the
    dashboard cannot read stdout.
    """

    #: UL name -> the Brightspace name it was restored to.
    renamed: dict[str, str]
    #: Folders already in Brightspace format. A re-run is normal.
    already_correct: list[str]
    #: Folders the log does not account for, by name. Left untouched.
    unmatched: list[str]
    #: Folders whose rename failed, name -> the error.
    failed: dict[str, str]

    def __str__(self) -> str:
        return (
            f"{len(self.renamed)} restored, {len(self.already_correct)} already "
            f"correct, {len(self.unmatched)} unrecognised, {len(self.failed)} failed"
        )


def brightspace_name_folders(
    df: pd.DataFrame, subs_folder: pl.Path
) -> Restoration:
    """
    Rename each folder back to the name Brightspace gave it.

    Args:
    df (pd.DataFrame): The rename log written by ``alphabetise_folders``,
        with 'Original Name' and 'Suggested Name' columns. Not modified.
    subs_folder (pl.Path): The submissions folder.

    Returns:
    Restoration: What was renamed, what was already correct, what was not
    recognised, and what failed.

    Raises:
    KeyError: If the log is missing a column, which usually means a class
        list was passed instead of the rename log.

    Note:
        The names are restored exactly, case included. They go back to
        Brightspace, so "BARRY - 01 MARCH" instead of "Barry - 01 March" is a
        real difference even when the id is intact.
    """
    subs_folder = pl.Path(subs_folder)

    missing = [c for c in ("Original Name", "Suggested Name") if c not in df.columns]
    if missing:
        raise KeyError(
            f"The rename log is missing {', '.join(missing)}. This function "
            "takes the log alphabetise_folders wrote "
            "('folder_rename_log.csv' in the submissions folder), not the "
            f"class list. Columns given: {list(df.columns)}."
        )

    # Upper case in the KEY only. The value keeps the case Brightspace used,
    # which is the whole point of the exercise.
    restore_to = {
        str(suggested).upper(): str(original)
        for suggested, original in zip(df["Suggested Name"], df["Original Name"])
        if pd.notna(suggested) and pd.notna(original)
    }
    already_brightspace = {
        str(original).upper() for original in df["Original Name"] if pd.notna(original)
    }

    renamed: dict[str, str] = {}
    already_correct: list[str] = []
    unmatched: list[str] = []
    failed: dict[str, str] = {}
    attempts = []

    for folder in sorted(subs_folder.iterdir()):
        if not folder.is_dir():
            continue

        key = folder.name.upper()

        if key in restore_to:
            target = restore_to[key]
            try:
                folder.rename(subs_folder / target)
            except OSError as error:
                # Narrow: a rename fails for filesystem reasons. Anything
                # else is a bug here and should surface, not be logged.
                failed[folder.name] = str(error)
                attempts.append({
                    "Original Name": folder.name,
                    "Suggested Name": target,
                    "Outcome": f"Failed: {error}",
                })
                continue

            renamed[folder.name] = target
            attempts.append({
                "Original Name": folder.name,
                "Suggested Name": target,
                "Outcome": "Renamed",
            })

        elif key in already_brightspace:
            already_correct.append(folder.name)
            attempts.append({
                "Original Name": folder.name,
                "Suggested Name": folder.name,
                "Outcome": "Already Correct",
            })

        else:
            unmatched.append(folder.name)

    if unmatched:
        pd.DataFrame(unmatched, columns=["Unfound Name"]).to_csv(
            subs_folder / UNFOUND_FILENAME, index=False
        )

    log_path = subs_folder / LOG_FILENAME
    log = pd.DataFrame(attempts)
    if log_path.exists():
        log = pd.concat([pd.read_csv(log_path), log], ignore_index=True)
    log.to_csv(log_path, index=False)

    return Restoration(renamed, already_correct, unmatched, failed)
