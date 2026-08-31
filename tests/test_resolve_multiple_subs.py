#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Choosing which of a student's submissions counts.

Brightspace keeps every attempt, and `alphabetise_folders` refuses to rename
anything while a student has two folders -- both cannot become
``SURNAME, NAME(id)``. So this is the step that unblocks the whole
assessment, and it deletes work, which is why what it removes is worked out
before anything is touched.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl

import pytest

from grader_helper import resolve_multiple_subs
from grader_helper.file_operations.resolve_multiple_subs import KEEP_CHOICES


def submission(folder: pl.Path, student: str, surname: str, when: str) -> pl.Path:
    """One Brightspace submission folder, with a file in it."""
    path = folder / f"27236-46025 - {student} {surname} - {when}"
    path.mkdir(parents=True)
    (path / "essay.docx").write_bytes(b"")
    return path


@pytest.fixture
def straddling_a_month(tmp_path) -> dict:
    """One student, two attempts, whose date order and name order disagree.

    March comes before April in time and after it as text, so this is the
    tree that tells a real sort from a sort of the folder names.
    """
    return {
        "folder": tmp_path,
        "march": submission(tmp_path, "23304307", "Egan", "05 March 2026 612 PM"),
        "april": submission(tmp_path, "23304307", "Egan", "01 April 2026 900 AM"),
    }


# ---------------------------------------------------------------------------
# Which one counts
# ---------------------------------------------------------------------------


def test_earliest_is_the_earliest_in_time_not_in_the_alphabet(straddling_a_month):
    """Sorted as text, `01 April` comes before `05 March`.

    A folder-name sort would keep April and call it the earliest -- the
    wrong submission, silently, and only for the students who happen to
    straddle a month.
    """
    plan = resolve_multiple_subs(straddling_a_month["folder"], keep="earliest")

    assert plan.kept == {"23304307": straddling_a_month["march"]}
    assert plan.removed == [straddling_a_month["april"]]


def test_latest_is_the_latest_in_time(straddling_a_month):
    plan = resolve_multiple_subs(straddling_a_month["folder"], keep="latest")

    assert plan.kept == {"23304307": straddling_a_month["april"]}
    assert plan.removed == [straddling_a_month["march"]]


def test_there_is_no_default_for_which_one_counts():
    """Whether a resubmission supersedes the first attempt is the module's
    rule. A tool that picked one would be making an academic judgement."""
    with pytest.raises(TypeError):
        resolve_multiple_subs(pl.Path("."))

    with pytest.raises(ValueError, match="module leader's decision"):
        resolve_multiple_subs(pl.Path("."), keep="whichever")

    assert KEEP_CHOICES == ("earliest", "latest")


# ---------------------------------------------------------------------------
# Nothing happens until it is asked for
# ---------------------------------------------------------------------------


def test_a_plan_deletes_nothing(straddling_a_month):
    """It removes a student's work, so what it would do is shown first."""
    plan = resolve_multiple_subs(straddling_a_month["folder"], keep="latest")

    assert not plan.applied
    assert straddling_a_month["march"].exists()
    assert straddling_a_month["april"].exists()


def test_applying_removes_only_the_extras(straddling_a_month):
    result = resolve_multiple_subs(
        straddling_a_month["folder"], keep="latest", apply=True
    )

    assert result.applied
    assert straddling_a_month["april"].exists()
    assert not straddling_a_month["march"].exists()


def test_a_student_who_submitted_once_is_untouched(tmp_path):
    only = submission(tmp_path, "23304308", "Angood", "05 March 2026 612 PM")

    result = resolve_multiple_subs(tmp_path, keep="latest", apply=True)

    assert only.exists()
    assert not result
    assert "no student submitted more than once" in str(result)


def test_folders_it_does_not_recognise_are_left_alone(tmp_path, straddling_a_month):
    """Only Brightspace's own format, and only directly inside the folder.

    A moderation folder somebody added, `__MACOSX` from unzipping on a Mac,
    or a folder already renamed to UL format are all things this must not
    decide it owns.
    """
    for name in ("__MACOSX", "EGAN, AOIFE(23304307)", "moderation"):
        (tmp_path / name).mkdir()

    resolve_multiple_subs(tmp_path, keep="latest", apply=True)

    for name in ("__MACOSX", "EGAN, AOIFE(23304307)", "moderation"):
        assert (tmp_path / name).exists(), f"{name} was removed"


def test_it_refuses_a_folder_that_is_not_there(tmp_path):
    with pytest.raises(RuntimeError):
        resolve_multiple_subs(tmp_path / "nope", keep="latest")
