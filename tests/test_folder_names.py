#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Parsing and rewriting Brightspace submission folder names.

Real format, confirmed against a live download:

    "27236-46025 - 23304308 Angood - 05 March 2026 612 PM"

The student ID is the first token after the first " - ". Everything
orients on it. (The README's example, "1234-5678 - Lastname Firstname -
01 January 2001 0000 AM", is out of date and puts the name where the ID
actually goes.)
"""

import datetime as dt

import pytest

from grader_helper import alphabetise_folders, make_sub_date, scan_multiple_subs

REAL = "27236-46025 - 23304308 Angood - 05 March 2026 612 PM"


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------


def test_parses_the_real_timestamp_format():
    """Brightspace omits the colon: "612 PM" means 18:12."""
    assert make_sub_date("05 March 2026 612 PM") == dt.datetime(2026, 3, 5, 18, 12)


def test_parses_a_timestamp_that_already_has_a_colon():
    assert make_sub_date("05 March 2026 12:05 AM") == dt.datetime(2026, 3, 5, 0, 5)


def test_noon_and_midday_boundaries():
    assert make_sub_date("05 March 2026 1230 PM") == dt.datetime(2026, 3, 5, 12, 30)
    assert make_sub_date("05 March 2026 1230 AM") == dt.datetime(2026, 3, 5, 0, 30)


@pytest.mark.xfail(
    reason=(
        "'0000 AM' becomes '00:00 AM', but %I is a 12-hour field accepting "
        "01-12, so midnight expressed this way raises ValueError. Brightspace "
        "appears to render midnight as '1200 AM', so this may never occur in "
        "practice -- but the README's own example uses '0000 AM', and one "
        "unparseable folder aborts an entire batch (see below)."
    ),
    strict=True,
)
def test_midnight_expressed_as_four_zeroes():
    assert make_sub_date("05 March 2026 0000 AM") == dt.datetime(2026, 3, 5, 0, 0)


# ---------------------------------------------------------------------------
# Duplicate-submission scanning
# ---------------------------------------------------------------------------


def test_clean_tree_has_no_duplicates(brightspace_tree):
    assert scan_multiple_subs(brightspace_tree) == {}


def test_detects_a_student_who_submitted_twice(brightspace_tree, fake_students, folder_name):
    sid, _, last = fake_students[0]
    (
        brightspace_tree
        / folder_name(sid, last, "09 March 2026 905 AM")
    ).mkdir()

    duplicates = scan_multiple_subs(brightspace_tree)

    assert len(duplicates) == 1
    (key, timestamps), = duplicates.items()
    assert sid in key
    assert len(timestamps) == 2
    assert dt.datetime(2026, 3, 9, 9, 5) in timestamps


@pytest.mark.parametrize("stray", ["__MACOSX", "moderation sample", "feedback"])
def test_stray_folders_do_not_break_the_scan(brightspace_tree, stray):
    """Folders that are not submissions must be skipped, not fatal.

    __MACOSX is created by macOS's unzip -- now a supported platform -- and
    a moderation folder is a documented part of the workflow.
    """
    (brightspace_tree / stray).mkdir()
    assert scan_multiple_subs(brightspace_tree) == {}


def test_scan_rejects_a_path_that_is_not_a_directory(tmp_path):
    f = tmp_path / "not-a-folder.txt"
    f.write_text("x")
    with pytest.raises(RuntimeError):
        scan_multiple_subs(f)


def test_duplicate_keys_are_the_bare_student_id(brightspace_tree, fake_students, folder_name):
    """Every consumer orients on the bare student ID, this one included."""
    sid, _, last = fake_students[0]
    (
        brightspace_tree
        / folder_name(sid, last, "09 March 2026 905 AM")
    ).mkdir()

    assert set(scan_multiple_subs(brightspace_tree)) == {sid}


# ---------------------------------------------------------------------------
# Renaming to UL format
# ---------------------------------------------------------------------------


def test_renames_to_ul_format(brightspace_tree, classlist, fake_students):
    alphabetise_folders(classlist, brightspace_tree)

    names = {p.name for p in brightspace_tree.iterdir() if p.is_dir()}
    for sid, first, last in fake_students:
        assert f"{last.upper()}, {first.upper()}({sid})" in names


def test_rename_writes_a_log(brightspace_tree, classlist):
    import pandas as pd

    alphabetise_folders(classlist, brightspace_tree)

    log = brightspace_tree / "folder_rename_log.csv"
    assert log.exists()
    df = pd.read_csv(log)
    assert set(df.columns) == {
        "Original Name",
        "Suggested Name",
        "Outcome",
        "Error",
    }
    assert (df["Outcome"] == "Renamed").all()


def test_rename_log_appends_across_runs(brightspace_tree, classlist, fake_students, folder_name):
    """Late submissions arrive after the first pass, so the log accumulates."""
    import pandas as pd

    alphabetise_folders(classlist, brightspace_tree)
    first_rows = len(pd.read_csv(brightspace_tree / "folder_rename_log.csv"))

    sid, _, last = fake_students[0]
    late = "23304399"
    (
        brightspace_tree / folder_name(late, "Latecomer", "20 March 2026 100 PM")
    ).mkdir()
    classlist.loc[len(classlist)] = [late, "Latecomer", "Sam", ""]

    alphabetise_folders(classlist, brightspace_tree)

    rows = pd.read_csv(brightspace_tree / "folder_rename_log.csv")
    assert len(rows) > first_rows


def test_rename_records_a_student_missing_from_the_classlist(
    brightspace_tree, classlist, folder_name
):
    """A submission from someone not on the class list is logged, not fatal."""
    import pandas as pd

    (
        brightspace_tree
        / folder_name("99999999", "Ghost", "06 March 2026 200 PM")
    ).mkdir()

    alphabetise_folders(classlist, brightspace_tree)

    log = pd.read_csv(brightspace_tree / "folder_rename_log.csv")
    failed = log[log["Outcome"] == "Failed"]
    assert len(failed) == 1
    assert "99999999" in failed.iloc[0]["Error"]


def test_rename_aborts_when_a_student_submitted_twice(
    brightspace_tree, classlist, fake_students, folder_name
):
    sid, _, last = fake_students[0]
    (
        brightspace_tree
        / folder_name(sid, last, "09 March 2026 905 AM")
    ).mkdir()

    with pytest.raises(RuntimeError, match="multiple submissions"):
        alphabetise_folders(classlist, brightspace_tree)


def test_rename_refuses_a_tree_with_nothing_to_rename(tmp_path, classlist):
    subs = tmp_path / "already done"
    subs.mkdir()
    (subs / "ANGOOD, KEVIN(23304308)").mkdir()

    with pytest.raises(RuntimeError, match="No Brightspace-style folders"):
        alphabetise_folders(classlist, subs)
