#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The audit over the manual copy.

A grader reads the mark off the feedback sheet and types it into their own
grade sheet. The student sees the first, the department is sent the second,
and nothing but this compares them. What matters is not that disagreements
are counted but that the kinds are told apart: a student who never submitted
is collated without a feedback sheet every time, and if that reads the same
as a lost mark then the check is noise and gets ignored.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pandas as pd
import pytest

from grader_helper import reconcile_marks


def received(**marks) -> pd.DataFrame:
    """What catch_grades read off the feedback sheets."""
    return pd.DataFrame(
        {"Student ID": list(marks), "grade": list(marks.values())}
    )


def reported(**marks) -> pd.DataFrame:
    """What the graders wrote in their own sheets."""
    return pd.DataFrame({"Student ID": list(marks), "Mark": list(marks.values())})


# ---------------------------------------------------------------------------
# Agreement
# ---------------------------------------------------------------------------


def test_matching_records_agree():
    result = reconcile_marks(received(a=62, b=71), reported(a=62, b=71))

    assert result.agree
    assert result.disagreements.empty
    assert len(result.comparison) == 2


def test_two_blanks_are_not_a_disagreement():
    """Nobody marked that student, and the two records agree about it.

    An unmarked student is a real problem and a different one -- it shows up
    as a missing mark, not as two copies differing. Reporting it here would
    put a disagreement in front of the leader for every student the graders
    have not reached yet, which is how a check stops being read.
    """
    result = reconcile_marks(received(a=62, b=None), reported(a=62, b=None))

    assert result.agree


# ---------------------------------------------------------------------------
# The three kinds of disagreement
# ---------------------------------------------------------------------------


def test_a_differing_mark_is_a_transcription_slip():
    """The failure the audit exists for."""
    result = reconcile_marks(received(a=62, b=71), reported(a=62, b=17))

    assert not result.agree
    assert list(result.transcription_slips["Student ID"]) == ["b"]
    assert result.not_submitted.empty and result.not_allocated.empty


def test_collated_without_a_feedback_sheet_is_not_submitted():
    """Normal, and must not read as a lost mark.

    A student on the class list is allocated a grader whether or not they
    submit, so they reach the collated file with nothing to mark.
    """
    result = reconcile_marks(received(a=62), reported(a=62, b=None))

    assert list(result.not_submitted["Student ID"]) == ["b"]
    assert result.transcription_slips.empty


def test_marked_without_an_allocation_is_flagged_separately():
    """Always worth a look: a sheet exists for a student nobody was given."""
    result = reconcile_marks(received(a=62, b=55), reported(a=62))

    assert list(result.not_allocated["Student ID"]) == ["b"]
    assert result.transcription_slips.empty


def test_the_summary_says_which_kind():
    result = reconcile_marks(received(a=62, b=71), reported(a=62, b=17))

    assert "1 differing marks" in str(result)
    assert "every mark agrees" in str(reconcile_marks(received(a=1), reported(a=1)))


# ---------------------------------------------------------------------------
# What it refuses
# ---------------------------------------------------------------------------


def test_ids_read_as_numbers_are_refused_loudly():
    """A silent mismatch would agree with nobody and report everyone twice.

    Student ids are text everywhere in this package: read as numbers, a
    leading zero is gone and the two records stop matching at all.
    """
    text_ids = received(**{"023304308": 62})
    number_ids = pd.DataFrame({"Student ID": [23304308], "Mark": [62]})

    with pytest.raises(ValueError, match="read as text"):
        reconcile_marks(text_ids, number_ids)


def test_a_missing_column_says_which_one():
    with pytest.raises(KeyError, match="Mark"):
        reconcile_marks(received(a=62), pd.DataFrame({"Student ID": ["a"]}))
