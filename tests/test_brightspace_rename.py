#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Renaming folders back to Brightspace format for re-upload.

The last step before the marked work goes back up, and the one with the
furthest reach: a wrong folder name here lands on students. It had no tests
at all.

The guarantee that matters is a **round trip**. What Brightspace gave us,
alphabetise_folders renamed to UL format, and this must hand back --
character for character, not merely recognisably.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl

import pandas as pd
import pytest

from grader_helper import alphabetise_folders, import_brightspace_classlist
from grader_helper.file_operations.brightspace_name_folders import (
    brightspace_name_folders,
)

#: As Brightspace writes them: mixed case surname, mixed case month.
BRIGHTSPACE_NAMES = [
    "27236-46025 - 23304301 Angood - 01 March 2026 600 PM",
    "27236-46025 - 23304302 Barry - 01 March 2026 600 PM",
    "27236-46025 - 00123456 Gallagher - 01 March 2026 600 PM",
]


@pytest.fixture
def classlist():
    return pd.DataFrame(
        {
            "Student ID": ["23304301", "23304302", "00123456"],
            "Last Name": ["Angood", "Barry", "Gallagher"],
            "First Name": ["Aoife", "Barra", "Grainne"],
        }
    )


@pytest.fixture
def subs(tmp_path, classlist):
    """A submissions folder, alphabetised, with the rename log written."""
    folder = tmp_path / "submissions"
    folder.mkdir()
    for name in BRIGHTSPACE_NAMES:
        (folder / name).mkdir()
    alphabetise_folders(classlist, folder)
    return folder


@pytest.fixture
def rename_log(subs):
    return pd.read_csv(subs / "folder_rename_log.csv")


def folders(path) -> list[str]:
    return sorted(p.name for p in path.iterdir() if p.is_dir())


# ---------------------------------------------------------------------------
# The round trip
# ---------------------------------------------------------------------------


def test_the_folders_come_back_exactly_as_brightspace_wrote_them(subs, rename_log):
    """Character for character.

    The names go back to Brightspace, so "BARRY - 01 MARCH" instead of
    "Barry - 01 March" is a real difference even if the ids are intact.
    """
    brightspace_name_folders(rename_log, subs)

    assert folders(subs) == sorted(BRIGHTSPACE_NAMES)


def test_the_case_of_the_surname_and_date_is_preserved(subs, rename_log):
    """Named separately, because this is the way it failed."""
    brightspace_name_folders(rename_log, subs)

    restored = folders(subs)
    assert any("Gallagher" in name for name in restored), restored
    assert not any("GALLAGHER" in name for name in restored), restored
    assert any("01 March 2026" in name for name in restored), restored


def test_a_leading_zero_survives(subs, rename_log):
    brightspace_name_folders(rename_log, subs)

    assert any("00123456" in name for name in folders(subs))


def test_alphabetised_first_so_the_round_trip_is_real(subs):
    """Guard on the fixture: the folders really are in UL format first."""
    assert folders(subs) == [
        "ANGOOD, AOIFE(23304301)",
        "BARRY, BARRA(23304302)",
        "GALLAGHER, GRAINNE(00123456)",
    ]


# ---------------------------------------------------------------------------
# It leaves the caller's data alone
# ---------------------------------------------------------------------------


def test_the_rename_log_is_not_mutated(subs, rename_log):
    """It used to upper-case two columns of the frame it was handed."""
    before = rename_log.copy(deep=True)

    brightspace_name_folders(rename_log, subs)

    pd.testing.assert_frame_equal(rename_log, before)


# ---------------------------------------------------------------------------
# What it reports
# ---------------------------------------------------------------------------


def test_it_reports_what_it_did(subs, rename_log):
    result = brightspace_name_folders(rename_log, subs)

    assert len(result.renamed) == 3
    assert result.unmatched == []
    assert result.failed == {}


def test_a_folder_it_does_not_know_is_reported_not_touched(subs, rename_log):
    (subs / "__MACOSX").mkdir()
    (subs / "Moderation").mkdir()

    result = brightspace_name_folders(rename_log, subs)

    assert sorted(result.unmatched) == ["Moderation", "__MACOSX"]
    assert (subs / "__MACOSX").is_dir()
    assert (subs / "Moderation").is_dir()


def test_a_folder_already_in_brightspace_format_is_left_alone(subs, rename_log):
    """Re-running must not rename what is already correct."""
    brightspace_name_folders(rename_log, subs)

    second = brightspace_name_folders(rename_log, subs)

    assert folders(subs) == sorted(BRIGHTSPACE_NAMES)
    assert len(second.already_correct) == 3
    assert second.renamed == {}


def test_the_logs_are_still_written(subs, rename_log):
    brightspace_name_folders(rename_log, subs)

    assert (subs / "folder_brightspace_name_log.csv").exists()


def test_matching_ignores_case(subs, rename_log):
    """The lookup is case-insensitive even though the value written is not.

    Someone may have touched a folder name's case by hand; that should still
    match, and still restore the proper name.
    """
    angood = subs / "ANGOOD, AOIFE(23304301)"
    angood.rename(subs / "Angood, Aoife(23304301)")

    brightspace_name_folders(rename_log, subs)

    assert folders(subs) == sorted(BRIGHTSPACE_NAMES)
