#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Allocation of students and groups to graders."""

import pandas as pd
import pytest

from grader_helper import assign_graders_groups, assign_graders_individual

GRADERS = ["alice", "bob", "carol"]


@pytest.fixture
def students():
    return pd.DataFrame(
        {"Student ID": [f"1000000{i}" for i in range(7)], "Score": [""] * 7}
    )


@pytest.fixture
def group_classlist():
    """A flat frame with a Group column.

    This is exactly what ``import_brightspace_classlist(group=True)``
    returns -- columns Student ID / Last Name / First Name / Group / Score.
    """
    return pd.DataFrame(
        {
            "Student ID": list("123456"),
            "Group": ["Team 1"] * 3 + ["Team 2"] * 3,
            "Score": [""] * 6,
        }
    )


# --------------------------------------------------------------------------
# Individual allocation
# --------------------------------------------------------------------------


def test_every_student_gets_a_grader(students):
    out = assign_graders_individual(students, GRADERS, seed=1)
    assert out["grader"].notna().all()
    assert set(out["grader"]) <= set(GRADERS)


def test_allocation_is_even_within_one(students):
    """7 students across 3 graders must split 3/2/2, not 5/1/1."""
    out = assign_graders_individual(students, GRADERS, seed=1)
    counts = sorted(out["grader"].value_counts().tolist())
    assert counts == [2, 2, 3]


def test_seed_makes_allocation_reproducible(students):
    a = assign_graders_individual(students, GRADERS, seed=42)
    b = assign_graders_individual(students, GRADERS, seed=42)
    pd.testing.assert_series_equal(a["grader"], b["grader"])


def test_weights_produce_proportional_quotas():
    """Hamilton's largest-remainder: 10 students, weights 3:1:1 -> 6/2/2."""
    df = pd.DataFrame({"Student ID": [str(i) for i in range(10)]})
    out = assign_graders_individual(
        df, GRADERS, weights={"alice": 3, "bob": 1, "carol": 1}, seed=7
    )
    counts = out["grader"].value_counts()
    assert counts["alice"] == 6
    assert counts["bob"] == 2
    assert counts["carol"] == 2


def test_existing_column_is_preserved_unless_overwrite(students):
    first = assign_graders_individual(students, GRADERS, seed=1)
    second = assign_graders_individual(first, GRADERS, seed=999)
    pd.testing.assert_series_equal(first["grader"], second["grader"])


def test_overwrite_replaces_an_existing_allocation(students):
    first = assign_graders_individual(students, GRADERS, seed=1)
    second = assign_graders_individual(
        first, GRADERS, seed=999, overwrite=True
    )
    assert second["grader"].notna().all()


def test_empty_frame_is_handled(students):
    out = assign_graders_individual(students.iloc[:0], GRADERS, seed=1)
    assert len(out) == 0
    assert "grader" in out.columns


def test_duplicate_grader_names_are_rejected(students):
    with pytest.raises(ValueError):
        assign_graders_individual(students, ["alice", "alice"], seed=1)


def test_empty_grader_list_is_rejected(students):
    with pytest.raises(ValueError):
        assign_graders_individual(students, [], seed=1)


def test_graders_must_be_a_list_not_any_sequence(students):
    """Characterisation: the annotation says Sequence, the check says list.

    A tuple is a perfectly good Sequence and is rejected. Worth revisiting
    in Phase 3, but pinned here so the migration does not change it by
    accident.
    """
    with pytest.raises(TypeError):
        assign_graders_individual(students, ("alice", "bob"), seed=1)


# --------------------------------------------------------------------------
# Group allocation
# --------------------------------------------------------------------------


def test_every_member_of_a_group_gets_the_same_grader(group_classlist):
    """The whole point: a group's single piece of work gets one marker."""
    out = assign_graders_groups(group_classlist, GRADERS)
    per_group = out.groupby("Group")["grader"].nunique()
    assert (per_group == 1).all(), (
        f"groups split across graders: {per_group.to_dict()}"
    )


def test_every_student_keeps_their_row(group_classlist):
    out = assign_graders_groups(group_classlist, GRADERS)
    assert len(out) == len(group_classlist)
    assert out["grader"].notna().all()
    assert set(out["grader"]) <= set(GRADERS)


def test_groups_are_spread_evenly_across_graders():
    """Six groups across three graders is 2/2/2, not 4/1/1.

    The old implementation sampled with replacement, so a grader could be
    given every group while another got none.
    """
    df = pd.DataFrame(
        {
            "Student ID": [str(i) for i in range(12)],
            "Group": [f"Team {i % 6 + 1}" for i in range(12)],
        }
    )

    out = assign_graders_groups(df, GRADERS, seed=3)

    groups_per_grader = out.drop_duplicates("Group")["grader"].value_counts()
    assert sorted(groups_per_grader.tolist()) == [2, 2, 2]


def test_group_allocation_is_reproducible_with_a_seed(group_classlist):
    a = assign_graders_groups(group_classlist, GRADERS, seed=11)
    b = assign_graders_groups(group_classlist, GRADERS, seed=11)
    pd.testing.assert_series_equal(a["grader"], b["grader"])


def test_group_column_is_found_however_it_is_named():
    df = pd.DataFrame(
        {"Student ID": list("1234"), "Team": ["A", "A", "B", "B"]}
    )

    out = assign_graders_groups(df, GRADERS, seed=1)

    per_group = out.groupby("Team")["grader"].nunique()
    assert (per_group == 1).all()


def test_a_frame_with_no_group_column_says_so():
    """A MultiIndex is no longer supported; the group lives in a column."""
    df = pd.DataFrame({"Student ID": list("12"), "Score": [0, 0]})

    with pytest.raises(ValueError, match="group column"):
        assign_graders_groups(df, GRADERS)


def test_existing_allocation_is_not_reshuffled(group_classlist):
    """Re-running must not move work graders may already have started."""
    first = assign_graders_groups(group_classlist, GRADERS, seed=1)
    second = assign_graders_groups(first, GRADERS, seed=999)
    pd.testing.assert_series_equal(first["grader"], second["grader"])
