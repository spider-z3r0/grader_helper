#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Putting a blank feedback sheet into each submission folder.

The function runs against real directories, so these tests build real ones.
Nothing here needs Excel: the sheet is copied byte for byte, never parsed.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl

import pytest

from grader_helper import (
    distribute_feedback_sheets,
    distribute_feedback_sheets_groups,
)
from grader_helper.file_operations.distribute_feedback_sheets import (
    group_id_from_folder,
    student_id_from_folder,
)


@pytest.fixture
def rubric(tmp_path) -> pl.Path:
    """A blank feedback sheet. Its bytes are the thing being copied."""
    path = tmp_path / "Feedback sheet BLANK.xlsx"
    path.write_bytes(b"rubric-contents")
    return path


@pytest.fixture
def subs(tmp_path) -> pl.Path:
    return (tmp_path / "submissions").resolve()


# ---------------------------------------------------------------------------
# Reading an id out of a folder name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        # Straight from Brightspace, before anything has renamed it.
        ("27236-46025 - 23304308 Angood - 05 March 2026 612 PM", "23304308"),
        # After alphabetise_folders has put it in UL form.
        ("ANGOOD, KEVIN(23304308)", "23304308"),
        ("OMALLEY, KEVIN(12345678)", "12345678"),
    ],
)
def test_both_folder_formats_are_recognised(name, expected):
    """The ordering dependency this used to have is gone.

    Only the parenthesised UL form was matched before, so running the
    distribution on a freshly unzipped download found nothing at all and had
    to be preceded by alphabetise_folders. Nothing said so.
    """
    assert student_id_from_folder(name) == expected


@pytest.mark.parametrize(
    "name", ["__MACOSX", "Moderation", "notes.txt", "Team 3"]
)
def test_a_folder_with_no_id_is_not_matched(name):
    assert student_id_from_folder(name) is None


@pytest.mark.parametrize(
    "name,expected",
    [
        ("12345-678 - Team 3 - 05 March 2026 612 PM", "Team 3"),
        ("12345-678 - Group 12 - 05 March 2026 612 PM", "Group 12"),
        ("12345-678 - team 7 - 05 March 2026 612 PM", "Team 7"),
    ],
)
def test_groups_may_be_called_team_or_group(name, expected):
    """The label was hardcoded to "Team".

    A module that called its groups anything else received no feedback
    sheets whatsoever, and the only sign was a printed line per folder.
    """
    assert group_id_from_folder(name) == expected


# ---------------------------------------------------------------------------
# Distributing
# ---------------------------------------------------------------------------


def test_every_student_gets_a_sheet(subs, rubric, folder_name):
    subs.mkdir()
    for sid in ("23304301", "23304302", "23304303"):
        (subs / folder_name(sid, "Surname")).mkdir()

    result = distribute_feedback_sheets(subs, rubric)

    assert sorted(result.copied) == ["23304301", "23304302", "23304303"]
    for sid, path in result.copied.items():
        assert path.name == f"Feedback sheet {sid}.xlsx"
        assert path.read_bytes() == b"rubric-contents"


def test_the_sheet_lands_inside_the_students_own_folder(subs, rubric, folder_name):
    subs.mkdir()
    folder = subs / folder_name("23304308", "Angood")
    folder.mkdir()

    result = distribute_feedback_sheets(subs, rubric)

    assert result.copied["23304308"].parent == folder


def test_an_existing_sheet_is_not_overwritten(subs, rubric, folder_name):
    """It may already carry marks. Re-running a distribution is normal."""
    subs.mkdir()
    folder = subs / folder_name("23304308", "Angood")
    folder.mkdir()
    existing = folder / "Feedback sheet 23304308.xlsx"
    existing.write_bytes(b"a graders marks")

    result = distribute_feedback_sheets(subs, rubric)

    assert existing.read_bytes() == b"a graders marks"
    assert result.copied == {}
    assert "23304308" in result.skipped


def test_overwrite_replaces_it_when_asked(subs, rubric, folder_name):
    subs.mkdir()
    folder = subs / folder_name("23304308", "Angood")
    folder.mkdir()
    (folder / "Feedback sheet 23304308.xlsx").write_bytes(b"stale")

    result = distribute_feedback_sheets(subs, rubric, overwrite=True)

    assert (folder / "Feedback sheet 23304308.xlsx").read_bytes() == b"rubric-contents"
    assert "23304308" in result.copied


def test_a_rerun_copies_nothing_new(subs, rubric, folder_name):
    subs.mkdir()
    (subs / folder_name("23304308", "Angood")).mkdir()

    distribute_feedback_sheets(subs, rubric)
    second = distribute_feedback_sheets(subs, rubric)

    assert second.copied == {}
    assert len(second.skipped) == 1


def test_unrecognised_directories_are_reported_not_guessed_at(
    subs, rubric, folder_name
):
    """__MACOSX is created by macOS when unzipping; it is not a student."""
    subs.mkdir()
    (subs / folder_name("23304308", "Angood")).mkdir()
    (subs / "__MACOSX").mkdir()
    (subs / "Moderation").mkdir()

    result = distribute_feedback_sheets(subs, rubric)

    assert list(result.copied) == ["23304308"]
    assert sorted(result.unmatched) == ["Moderation", "__MACOSX"]


def test_loose_files_are_ignored(subs, rubric, folder_name):
    subs.mkdir()
    (subs / folder_name("23304308", "Angood")).mkdir()
    (subs / "index.html").write_text("brightspace leaves these")

    result = distribute_feedback_sheets(subs, rubric)

    assert list(result.copied) == ["23304308"]
    assert result.unmatched == []


def test_the_result_summarises_itself(subs, rubric, folder_name):
    """The caller needs to see what happened; a dashboard cannot read stdout."""
    subs.mkdir()
    (subs / folder_name("23304308", "Angood")).mkdir()
    (subs / "__MACOSX").mkdir()

    assert str(distribute_feedback_sheets(subs, rubric)) == (
        "1 copied, 0 already present, 1 unrecognised"
    )


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


def test_each_group_gets_one_sheet(subs, rubric):
    subs.mkdir()
    for team in ("Team 1", "Team 2"):
        (subs / f"12345-678 - {team} - 05 March 2026 612 PM").mkdir()

    result = distribute_feedback_sheets_groups(subs, rubric)

    assert sorted(result.copied) == ["Team 1", "Team 2"]
    assert result.copied["Team 1"].name == "Feedback sheet Team 1.xlsx"


def test_group_distribution_accepts_the_word_group(subs, rubric):
    subs.mkdir()
    (subs / "12345-678 - Group 4 - 05 March 2026 612 PM").mkdir()

    result = distribute_feedback_sheets_groups(subs, rubric)

    assert list(result.copied) == ["Group 4"]


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_a_missing_rubric_is_refused(subs, tmp_path):
    subs.mkdir()

    with pytest.raises(FileNotFoundError):
        distribute_feedback_sheets(subs, tmp_path / "nope.xlsx")


def test_a_submissions_path_that_is_not_a_directory_is_refused(tmp_path, rubric):
    not_a_dir = tmp_path / "submissions.zip"
    not_a_dir.write_bytes(b"still zipped")

    with pytest.raises(NotADirectoryError, match="unzipped"):
        distribute_feedback_sheets(not_a_dir, rubric)
