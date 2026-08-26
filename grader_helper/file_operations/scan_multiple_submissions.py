#!/usr/bin/env python

import pathlib as pl
import datetime as dt

def main():
    folder = pl.Path(
        r"C:\Users\Kevin.OMalley\OneDrive - University of Limerick\Teaching\grader_helper\example_project\data\Week 1 Lab workbook submission  Download 14 October 2025 320 PM"
        )
    scan_multiple_subs(folder=folder)

def make_sub_date(s: str, fmt="%d %B %Y %I:%M %p") -> dt.datetime:
    # Brightspace: "13 September 2025 310 PM" or "13 September 2025 3:10 PM"
    day, month, year, time, ap = s.strip().split()

    if ":" not in time:              # e.g., "310" -> "3:10"
        time = time[:-2] + ":" + time[-2:]

    return dt.datetime.strptime(f"{day} {month} {year} {time} {ap}", fmt)

    


def parse_brightspace_folder(name: str) -> tuple[str, dt.datetime] | None:
    """Parse a Brightspace submission folder name.

    The download format is::

        "27236-46025 - 23304308 Angood - 05 March 2026 612 PM"
         |             |        |        |
         |             |        |        submission timestamp
         |             |        surname
         |             student ID
         Brightspace's own id, which changes per assignment

    Returns ``(student_id, submitted_at)``, or ``None`` if ``name`` is not a
    Brightspace folder at all. Returning None rather than raising is what
    lets callers run over a folder that has already been through
    ``alphabetise_folders`` -- those folders are in UL format
    ("ANGOOD, KEVIN(23304308)") and have no " - " to split on -- as well as
    over incidental directories such as ``__MACOSX``, which macOS creates
    when unzipping, or a moderation folder the user has added.
    """
    parts = name.strip().split(" - ")
    if len(parts) < 3:
        return None

    student_id = parts[1].split(" ")[0]
    if not student_id.isdigit():
        return None

    try:
        submitted_at = make_sub_date(parts[-1])
    except ValueError:
        return None

    return student_id, submitted_at


def scan_multiple_subs(folder: pl.Path) -> dict[str, list[dt.datetime]]:
    """Find students who submitted more than once.

    Only folders still in Brightspace format are considered; anything else
    is skipped. Keys are student IDs, values the submission timestamps.
    """
    if not folder.is_dir():
        raise RuntimeError(
                f"{folder.name} is not a directory/folder, please make sure you are calling "
                "this function on the unzipped folder you downloaded from Brightspace "
                "which contains the student submissions"
        )

    temp_dict: dict[str, list[dt.datetime]] = {}

    for f in folder.iterdir():
        if not f.is_dir():
            continue
        parsed = parse_brightspace_folder(f.name)
        if parsed is None:
            continue
        student_id, submitted_at = parsed
        temp_dict.setdefault(student_id, []).append(submitted_at)

    return {k: v for (k, v) in temp_dict.items() if len(v) > 1}







if __name__ == '__main__':
    main()


