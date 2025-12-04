#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import pathlib as pl
import re
from .scan_multiple_submissions import scan_multiple_subs





def alphabetise_folders(df: pd.DataFrame, subs_folder: pl.Path, verbose: bool = False):
    """
    Rename Brightspace download folders to UL's standard name format.

    This function expects `subs_folder` to contain raw Brightspace download
    folders named something like:

        "Lastname, Firstname - 1234567"

    where the numeric part after `" - "` is the student ID.

    Using a class list DataFrame `df` with columns:
    - 'Last Name'
    - 'First Name'
    - 'Student ID'

    it renames each folder to:

        "LASTNAME, FIRSTNAME(1234567)"

    It also logs every attempt (success or failure) to a CSV file
    `folder_rename_log.csv` in `subs_folder`. If that file already exists,
    new runs append to it so that late submissions are included.

    The resulting log can be used later by `brightspace_name_folders()` to
    rename folders *back* to the Brightspace-style format for re-upload.

    Args
    ----
    df:
        DataFrame containing at least 'Last Name', 'First Name', 'Student ID'.
    subs_folder:
        Path to the directory containing the Brightspace download folders.
    verbose:
        If True, print progress and a summary of outcomes to stdout.

    Raises
    ------
    RuntimeError
        - If any students have multiple submissions in `subs_folder`.
        - If no Brightspace-style folders are found to rename.
    """
    # 1. Pre-flight: fail fast if anyone has multiple submissions.
    duplicates = scan_multiple_subs(subs_folder)
    if duplicates:
        body = "\n".join(
            f" - {k}: {', '.join(map(str, v))}" for k, v in sorted(duplicates.items())
        )
        if verbose:
            print("Aborting: found multiple submissions for one or more students:")
            print(body)
        raise RuntimeError(
            "The following students have multiple submissions:\n"
            f"{body}\n"
            "Please delete extras or consolidate into one folder."
        )

    # 2. Look for logs of previous renaming operations.
    log_path = subs_folder / "folder_rename_log.csv"
    if log_path.exists():
        if verbose:
            print(f"Found existing rename log at {log_path}, appending new entries.")
        renames = pd.read_csv(log_path)
    else:
        if verbose:
            print(f"No existing rename log found. Creating new log at {log_path}.")
        renames = None

    # 3. Build a fast lookup: student ID -> (LASTNAME, FIRSTNAME)
    name_id_map = {
        str(row["Student ID"]): (row["Last Name"].upper(), row["First Name"].upper())
        for _, row in df.iterrows()
    }

    rename_attempts = []  # Track every attempt, not just successes.

    # Matches the numeric student ID after " - " in Brightspace folder names
    student_number_pattern = re.compile(r"(?<= - )\d+\b")

    # 4. Walk the submissions folder and attempt renames.
    for folder in subs_folder.iterdir():
        if not folder.is_dir():
            continue

        match = student_number_pattern.search(folder.stem)
        if not match:
            # Not a Brightspace-style folder; ignore but record nothing.
            continue

        student_number = match.group(0)

        try:
            (last, first) = name_id_map.get(student_number)
            new_folder_name = f"{last}, {first}({student_number})"

            folder.rename(subs_folder / new_folder_name)

            if verbose:
                print(f"Renamed: '{folder.name}' -> '{new_folder_name}'")

            rename_attempts.append(
                {
                    "Original Name": folder.name,
                    "Suggested Name": new_folder_name,
                    "Outcome": "Renamed",
                    "Error": None,
                }
            )

        except TypeError:
            # name_id_map.get(...) returned None; student ID not in class list.
            msg = (
                "Student Number not present in class list"
                f" (ID: {student_number}, folder: '{folder.name}')"
            )
            if verbose:
                print(f"Skipped (no match in class list): {msg}")
            rename_attempts.append(
                {
                    "Original Name": folder.name,
                    "Suggested Name": None,
                    "Outcome": "Failed",
                    "Error": msg,
                }
            )
        except Exception as e:
            if verbose:
                print(
                    f"Failed to rename '{folder.name}' "
                    f"(student {student_number}): {repr(e)}"
                )
            rename_attempts.append(
                {
                    "Original Name": folder.name,
                    "Suggested Name": new_folder_name,
                    "Outcome": "Failed",
                    "Error": repr(e),
                }
            )

    # 5. Sanity check: did we see any Brightspace-style folders at all?
    if not rename_attempts:
        if verbose:
            print(
                "No Brightspace-style folders found; "
                "expected folder names like 'Lastname, Firstname - 1234567'."
            )
        raise RuntimeError(
            f"No Brightspace-style folders found in {subs_folder}. "
            "This function expects a folder of raw Brightspace downloads. "
            "If you are trying to prepare folders to go *back* to Brightspace "
            "please use the brightspace_name_folders function."
        )

    renames_log = pd.DataFrame(rename_attempts)

    # 6. Write / append the log.
    if renames is not None:
        combined = pd.concat([renames, renames_log], ignore_index=True)
        combined.to_csv(log_path, index=False)
    else:
        renames_log.to_csv(log_path, index=False)

    if verbose:
        total = len(renames_log)
        renamed = (renames_log["Outcome"] == "Renamed").sum()
        failed = total - renamed
        print(
            f"Completed folder alphabetisation. "
            f"{renamed} renamed, {failed} failed, {total} total attempts."
        )
        print(f"Rename log written to: {log_path}")
