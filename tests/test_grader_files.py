#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The grader-file round trip: allocate, write, mark, read back.

These three functions form one loop -- save_grader_sheets writes a workbook
per grader, save_distributed_graders writes the master sheet, and
ingest_completed_graderfiles reads the workbooks back once the marks are in.
So the test that matters most is the round trip, not any one of them alone.

Nothing here needs Excel. pandas writes and reads .xlsx through openpyxl, so
this runs on Linux CI as well as on Windows.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl

import pandas as pd
import pytest

from grader_helper import (
    ingest_completed_graderfiles,
    save_distributed_graders,
    save_grader_sheets,
)


@pytest.fixture
def allocated() -> pd.DataFrame:
    """An allocation as assign_graders_individual leaves it.

    Student IDs are strings, and one carries a leading zero -- which is the
    whole point of the round-trip test below.
    """
    return pd.DataFrame(
        {
            "Student ID": ["23304308", "00123456", "23304310", "23304311"],
            "Name": ["Angood", "Barry", "Casey", "Doyle"],
            "grader": ["KOM", "SOB", "KOM", "SOB"],
        }
    )


# ---------------------------------------------------------------------------
# save_grader_sheets
# ---------------------------------------------------------------------------


def test_each_grader_gets_their_own_workbook(tmp_path, allocated):
    written = save_grader_sheets(allocated, tmp_path, ["KOM", "SOB"])

    assert sorted(written) == ["KOM", "SOB"]
    assert (tmp_path / "KOM.xlsx").exists()
    assert (tmp_path / "SOB.xlsx").exists()


def test_a_workbook_holds_only_that_graders_rows(tmp_path, allocated):
    save_grader_sheets(allocated, tmp_path, ["KOM", "SOB"])

    kom = pd.read_excel(tmp_path / "KOM.xlsx", dtype={"Student ID": str})

    assert kom["grader"].unique().tolist() == ["KOM"]
    assert kom["Student ID"].tolist() == ["23304308", "23304310"]


def test_the_index_is_never_written(tmp_path, allocated):
    """A phantom index column flows straight into the ingest."""
    save_grader_sheets(allocated, tmp_path, ["KOM"])

    kom = pd.read_excel(tmp_path / "KOM.xlsx")

    assert not any(str(c).startswith("Unnamed") for c in kom.columns)


def test_criteria_are_added_as_empty_columns_to_fill_in(tmp_path, allocated):
    save_grader_sheets(
        allocated, tmp_path, ["KOM"], criteria=["Structure", "Argument", "Mark"]
    )

    kom = pd.read_excel(tmp_path / "KOM.xlsx")

    assert list(kom.columns)[-3:] == ["Structure", "Argument", "Mark"]
    assert kom["Mark"].isna().all()


def test_existing_workbooks_are_not_overwritten(tmp_path, allocated):
    """They may already hold a grader's marks."""
    save_grader_sheets(allocated, tmp_path, ["KOM", "SOB"])
    marked = (tmp_path / "KOM.xlsx").read_bytes()

    with pytest.raises(FileExistsError, match="KOM"):
        save_grader_sheets(allocated, tmp_path, ["KOM", "SOB"])

    assert (tmp_path / "KOM.xlsx").read_bytes() == marked


def test_nothing_is_written_when_one_workbook_would_be_clobbered(
    tmp_path, allocated
):
    """A refusal half way through would split the allocation across files.

    The clash is on the LAST grader deliberately. Checking each file as it is
    reached passes an early-clash test by luck -- the refusal happens before
    anything is written. Only a clash at the end catches a per-file check,
    which writes every grader before it and leaves them on disk.
    """
    save_grader_sheets(allocated, tmp_path, ["SOB"])
    assert not (tmp_path / "KOM.xlsx").exists()

    with pytest.raises(FileExistsError, match="SOB"):
        save_grader_sheets(allocated, tmp_path, ["KOM", "SOB"])

    assert not (tmp_path / "KOM.xlsx").exists(), (
        "KOM was written before the clash on SOB was noticed"
    )


def test_overwrite_replaces_them_when_asked(tmp_path, allocated):
    save_grader_sheets(allocated, tmp_path, ["KOM", "SOB"])

    save_grader_sheets(allocated, tmp_path, ["KOM", "SOB"], overwrite=True)

    assert (tmp_path / "KOM.xlsx").exists()


def test_a_missing_grader_column_says_so(tmp_path, allocated):
    with pytest.raises(KeyError, match="assign_graders_individual"):
        save_grader_sheets(
            allocated.drop(columns=["grader"]), tmp_path, ["KOM"]
        )


def test_duplicate_graders_are_refused(tmp_path, allocated):
    """Each grader gets one workbook named for them, so names must be unique."""
    with pytest.raises(ValueError, match="Duplicate"):
        save_grader_sheets(allocated, tmp_path, ["KOM", "KOM"])


def test_no_graders_is_refused(tmp_path, allocated):
    with pytest.raises(ValueError, match="nothing to write"):
        save_grader_sheets(allocated, tmp_path, [])


# ---------------------------------------------------------------------------
# save_distributed_graders
# ---------------------------------------------------------------------------


def test_the_master_sheet_holds_every_student(tmp_path, allocated):
    allocation = save_distributed_graders(allocated, tmp_path)
    target = allocation.path
    assert allocation.students == len(allocated), (
        "the count is the evidence record() reads"
    )

    written = pd.read_excel(target, dtype={"Student ID": str})

    assert len(written) == len(allocated)
    assert written["Student ID"].tolist() == allocated["Student ID"].tolist()


def test_the_master_sheet_never_writes_an_index(tmp_path, allocated):
    """The bug: index=False on the first write, omitted on the overwrite.

    Replacing the file silently added an unnamed index column, which then
    travelled into every downstream read.
    """
    save_distributed_graders(allocated, tmp_path)
    save_distributed_graders(allocated, tmp_path, overwrite=True)

    written = pd.read_excel(tmp_path / "distributed.xlsx")

    assert not any(str(c).startswith("Unnamed") for c in written.columns)
    assert list(written.columns) == list(allocated.columns)


def test_an_existing_master_sheet_is_not_replaced(tmp_path, allocated):
    save_distributed_graders(allocated, tmp_path)

    with pytest.raises(FileExistsError, match="overwrite=True"):
        save_distributed_graders(allocated, tmp_path)


# ---------------------------------------------------------------------------
# ingest_completed_graderfiles
# ---------------------------------------------------------------------------


def test_every_graders_rows_come_back(tmp_path, allocated):
    save_grader_sheets(allocated, tmp_path, ["KOM", "SOB"])

    ingested = ingest_completed_graderfiles(
        tmp_path, ["KOM", "SOB"], file_type="excel"
    )

    assert len(ingested) == len(allocated)
    assert sorted(ingested["grader"].unique()) == ["KOM", "SOB"]


def test_student_ids_survive_the_round_trip(tmp_path, allocated):
    """The defect that silently destroys data.

    Left to pandas, a column of digit strings is written to Excel and read
    back as int64: '00123456' becomes 123456. The leading zeros are gone and
    the ids no longer match the class list.
    """
    save_grader_sheets(allocated, tmp_path, ["KOM", "SOB"])

    ingested = ingest_completed_graderfiles(
        tmp_path, ["KOM", "SOB"], file_type="excel"
    )

    assert ingested["Student ID"].dtype == object
    assert sorted(ingested["Student ID"]) == sorted(allocated["Student ID"])
    assert "00123456" in ingested["Student ID"].tolist()


def test_the_ingested_frame_merges_with_the_class_list(tmp_path, allocated):
    """The consequence, stated as the thing the user actually does.

    Merging an object column against an int64 one does not mismatch quietly
    -- pandas raises. So this failing means the marks cannot be joined back
    to the students at all.
    """
    save_grader_sheets(allocated, tmp_path, ["KOM", "SOB"])
    ingested = ingest_completed_graderfiles(
        tmp_path, ["KOM", "SOB"], file_type="excel"
    )

    classlist = allocated[["Student ID", "Name"]]
    merged = classlist.merge(ingested, on="Student ID", how="inner")

    assert len(merged) == len(classlist)


def test_csv_ids_survive_too(tmp_path, allocated):
    for grader in ("KOM", "SOB"):
        rows = allocated.loc[allocated["grader"] == grader]
        rows.to_csv(tmp_path / f"{grader}.csv", index=False)

    ingested = ingest_completed_graderfiles(tmp_path, ["KOM", "SOB"])

    assert ingested["Student ID"].dtype == object
    assert "00123456" in ingested["Student ID"].tolist()


def test_a_missing_grader_file_is_refused_by_default(tmp_path, allocated):
    """Missing files mean missing marks -- not something to find out later."""
    save_grader_sheets(allocated, tmp_path, ["KOM"])

    with pytest.raises(FileNotFoundError, match="SOB"):
        ingest_completed_graderfiles(tmp_path, ["KOM", "SOB"], file_type="excel")


def test_ingesting_without_a_grader_warns(tmp_path, allocated):
    save_grader_sheets(allocated, tmp_path, ["KOM"])

    with pytest.warns(UserWarning, match="SOB"):
        ingested = ingest_completed_graderfiles(
            tmp_path, ["KOM", "SOB"], file_type="excel", require_all=False
        )

    assert ingested["grader"].unique().tolist() == ["KOM"]


def test_no_files_at_all_says_what_it_looked_for(tmp_path):
    """This used to raise an unhandled ValueError from pd.concat([]).

    Only pd.errors.MergeError was caught, so the ValueError escaped -- and
    had it not, the function would have returned an unbound name.
    """
    with pytest.warns(UserWarning), pytest.raises(ValueError, match="KOM.xlsx"):
        ingest_completed_graderfiles(
            tmp_path, ["KOM", "SOB"], file_type="excel", require_all=False
        )


def test_saving_the_combined_frame(tmp_path, allocated):
    save_grader_sheets(allocated, tmp_path, ["KOM", "SOB"])

    ingest_completed_graderfiles(
        tmp_path, ["KOM", "SOB"], file_type="excel", save=True
    )

    assert (tmp_path / "completed_grades.xlsx").exists()


def test_an_existing_combined_file_is_not_replaced(tmp_path, allocated):
    save_grader_sheets(allocated, tmp_path, ["KOM", "SOB"])
    ingest_completed_graderfiles(
        tmp_path, ["KOM", "SOB"], file_type="excel", save=True
    )

    with pytest.raises(FileExistsError, match="overwrite=True"):
        ingest_completed_graderfiles(
            tmp_path, ["KOM", "SOB"], file_type="excel", save=True
        )


def test_an_unknown_file_type_is_refused(tmp_path):
    with pytest.raises(ValueError, match="excel"):
        ingest_completed_graderfiles(tmp_path, ["KOM"], file_type="parquet")


# ---------------------------------------------------------------------------
# The whole loop
# ---------------------------------------------------------------------------


def test_allocate_write_mark_read_back(tmp_path, allocated):
    """The loop as it is actually used, with marks written in between."""
    save_distributed_graders(allocated, tmp_path)
    save_grader_sheets(allocated, tmp_path, ["KOM", "SOB"], criteria=["Mark"])

    # Each grader opens their workbook and fills in the marks.
    for grader, marks in (("KOM", [65, 72]), ("SOB", [58, 81])):
        sheet = pd.read_excel(tmp_path / f"{grader}.xlsx", dtype={"Student ID": str})
        sheet["Mark"] = marks
        sheet.to_excel(tmp_path / f"{grader}.xlsx", index=False)

    ingested = ingest_completed_graderfiles(
        tmp_path, ["KOM", "SOB"], file_type="excel"
    )

    assert len(ingested) == 4
    assert ingested["Mark"].notna().all()

    master = pd.read_excel(tmp_path / "distributed.xlsx", dtype={"Student ID": str})
    merged = master.merge(ingested[["Student ID", "Mark"]], on="Student ID")
    assert len(merged) == 4
    assert merged.loc[merged["Student ID"] == "00123456", "Mark"].iloc[0] == 58
