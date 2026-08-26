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


@pytest.mark.xfail(
    reason=(
        "assign_graders_groups reads d.index.get_level_values(0), i.e. it "
        "requires a MultiIndex keyed on group. Nothing in the package "
        "produces one -- import_brightspace_classlist(group=True) returns a "
        "flat frame with a Group COLUMN. On a flat frame the RangeIndex "
        "makes every row its own group, so members of one team are split "
        "across different graders and the group's single piece of work gets "
        "marked by more than one person. Phase 3 must rebuild this around "
        "the Group column, since polars has no index."
    ),
    strict=True,
)
def test_every_member_of_a_group_gets_the_same_grader(group_classlist):
    out = assign_graders_groups(group_classlist, GRADERS)
    per_group = out.groupby("Group")["grader"].nunique()
    assert (per_group == 1).all(), (
        f"groups split across graders: {per_group.to_dict()}"
    )


def test_group_allocation_currently_assigns_per_student(group_classlist):
    """Characterisation of the bug above, so the fix is visibly a change."""
    out = assign_graders_groups(group_classlist, GRADERS)
    # It does produce a grader for every row -- it just ignores Group.
    assert out["grader"].notna().all()
    assert "Group" in out.columns


def test_group_allocation_works_on_the_multiindex_it_expects():
    """The function is correct for the shape it was written against."""
    index = pd.MultiIndex.from_tuples(
        [("Team 1", "1"), ("Team 1", "2"), ("Team 2", "3"), ("Team 2", "4")],
        names=["Group", "Student"],
    )
    df = pd.DataFrame({"Score": [0, 0, 0, 0]}, index=index)

    out = assign_graders_groups(df, GRADERS)

    per_group = out.groupby(level=0)["grader"].nunique()
    assert (per_group == 1).all()
