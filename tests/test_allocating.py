#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Allocating an assessment's marking, and the files that record it.

The three kinds and what each produces:

| kind                        | allocated over | grader's workbook |
|-----------------------------|----------------|-------------------|
| individual                  | students       | one row per student |
| group, made in Brightspace  | groups         | one row per **group** |
| group, made by the leader   | groups         | one row per **student** |

The middle row is the one worth holding on to: Brightspace gives a team one
folder, one feedback sheet and one mark, so a per-student workbook there
would ask the grader to type the same mark four times.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pandas as pd
import pytest

from grader_helper import (
    AmbiguousGroupError,
    Module,
    allocate_graders,
    build_group_membership,
)
from grader_helper.recording import evidence_for

from test_group_membership import write_group_sheet

GRADERS = ["ABC", "DEF"]


def make_module(tmp_path, **assessment_overrides) -> Module:
    """A one-assessment module on disk, with its folders created."""
    spec = dict(
        id="cw1",
        type="coursework",
        name="Coursework 1",
        marks_out_of=100,
        weight=100,
        graders=GRADERS,
    )
    module = Module(
        code="PS4001",
        name="Advanced Research Methods",
        year="2025/26",
        leader="KOM",
        assessments=[{**spec, **assessment_overrides}],
        root=tmp_path,
    )
    for directory in module.directories:
        directory.mkdir(parents=True, exist_ok=True)
    return module


@pytest.fixture
def classlist():
    """Six students, no groups."""
    return pd.DataFrame(
        {
            "Student ID": [f"2330430{i}" for i in range(6)],
            "Last Name": list("ABCDEF"),
            "First Name": list("abcdef"),
            "Score": [""] * 6,
        }
    )


@pytest.fixture
def grouped_classlist(classlist):
    """As ``import_brightspace_classlist(group=True)`` returns it."""
    out = classlist.copy()
    out.insert(3, "Group", ["Team 1"] * 2 + ["Team 2"] * 2 + ["Team 3"] * 2)
    return out


# ---------------------------------------------------------------------------
# Individual
# ---------------------------------------------------------------------------


def test_an_individual_assessment_allocates_per_student(tmp_path, classlist):
    a = make_module(tmp_path).assessment("cw1")

    allocation = allocate_graders(a, classlist, seed=1)

    assert len(allocation.frame) == 6
    assert len(allocation.per_grader) == 6
    assert set(allocation.frame["grader"]) <= set(GRADERS)
    assert allocation.membership is None


def test_the_two_files_go_where_the_assessment_says(tmp_path, classlist):
    a = make_module(tmp_path).assessment("cw1")

    allocation = allocate_graders(a, classlist, seed=1)

    assert allocation.master == a.folder_path / "distributed.xlsx"
    assert allocation.master.exists()
    assert set(allocation.workbooks) == set(GRADERS)
    for grader, path in allocation.workbooks.items():
        assert path == a.grading_output_path / f"{grader}.xlsx"
        assert path.exists()


def test_the_graders_come_from_the_module(tmp_path, classlist):
    """The whole point of the wiring: module.toml already says who marks it."""
    a = make_module(tmp_path).assessment("cw1")

    allocation = allocate_graders(a, classlist, seed=1)

    assert set(allocation.workbooks) == {"ABC", "DEF"}


def test_an_assessment_with_no_graders_says_so(tmp_path, classlist):
    a = make_module(tmp_path, graders=[]).assessment("cw1")

    with pytest.raises(ValueError, match="lists no graders"):
        allocate_graders(a, classlist)


def test_graders_can_be_overridden(tmp_path, classlist):
    a = make_module(tmp_path).assessment("cw1")

    allocation = allocate_graders(a, classlist, ["XYZ"], seed=1)

    assert set(allocation.workbooks) == {"XYZ"}


def test_a_grader_workbook_gets_a_mark_column_to_fill_in(tmp_path, classlist):
    """The column collate_module_marks reads back out again."""
    a = make_module(tmp_path).assessment("cw1")

    allocation = allocate_graders(a, classlist, seed=1)
    written = pd.read_excel(allocation.workbooks["ABC"])

    assert "Mark" in written.columns
    assert written["Mark"].isna().all()


def test_allocating_writes_no_status_of_its_own(tmp_path, classlist):
    """Status is set from what a step returned, by `record`. A run that set
    the flag itself would set it before its files were all written."""
    a = make_module(tmp_path).assessment("cw1")

    allocate_graders(a, classlist, seed=1)

    assert a.status.graders_allocated is False


def test_the_result_is_evidence_that_graders_were_allocated(tmp_path, classlist):
    a = make_module(tmp_path).assessment("cw1")

    result = allocate_graders(a, classlist, seed=1)

    assert evidence_for(result) == ("graders_allocated", True, "assessment")
    assert result.master == result.allocation.path


def test_an_allocation_of_nobody_is_not_evidence(tmp_path, classlist):
    """The usual enemy: a green tick against a step that did nothing."""
    a = make_module(tmp_path).assessment("cw1")

    result = allocate_graders(a, classlist.iloc[:0], seed=1)

    assert evidence_for(result) == ("graders_allocated", False, "assessment")


def test_a_re_run_will_not_quietly_reshuffle_started_marking(tmp_path, classlist):
    a = make_module(tmp_path).assessment("cw1")
    allocate_graders(a, classlist, seed=1)

    with pytest.raises(FileExistsError):
        allocate_graders(a, classlist, seed=2)


def test_the_allocation_is_reproducible(tmp_path, classlist):
    a = make_module(tmp_path).assessment("cw1")

    first = allocate_graders(a, classlist, seed=11).frame
    second = allocate_graders(a, classlist, seed=11, overwrite=True).frame

    pd.testing.assert_series_equal(first["grader"], second["grader"])


# ---------------------------------------------------------------------------
# Group, made in Brightspace
# ---------------------------------------------------------------------------


def test_brightspace_groups_are_read_from_the_class_list(
    tmp_path, grouped_classlist
):
    a = make_module(
        tmp_path, group=True, group_source="brightspace"
    ).assessment("cw1")

    allocation = allocate_graders(a, grouped_classlist, seed=1)

    assert allocation.membership is None
    assert len(allocation.frame) == 6


def test_a_team_is_marked_by_one_person(tmp_path, grouped_classlist):
    a = make_module(
        tmp_path, group=True, group_source="brightspace"
    ).assessment("cw1")

    allocation = allocate_graders(a, grouped_classlist, seed=1)

    per_group = allocation.frame.groupby("Group")["grader"].nunique()
    assert (per_group == 1).all()


def test_a_brightspace_grader_workbook_has_one_row_per_group(
    tmp_path, grouped_classlist
):
    """One folder, one feedback sheet, one mark -- so one row to fill in.
    A per-student workbook would be three chances to mistype the same mark."""
    a = make_module(
        tmp_path, group=True, group_source="brightspace"
    ).assessment("cw1")

    allocation = allocate_graders(a, grouped_classlist, seed=1)

    assert len(allocation.per_grader) == 3
    assert list(allocation.per_grader.columns) == ["Group", "grader"]

    written = pd.concat(
        pd.read_excel(path) for path in allocation.workbooks.values()
    )
    assert sorted(written["Group"]) == ["Team 1", "Team 2", "Team 3"]


def test_the_master_sheet_is_still_per_student(tmp_path, grouped_classlist):
    """It is what you open when a student asks who marked their work, and
    that question has an answer whoever submitted it."""
    a = make_module(
        tmp_path, group=True, group_source="brightspace"
    ).assessment("cw1")

    allocation = allocate_graders(a, grouped_classlist, seed=1)
    master = pd.read_excel(allocation.master, dtype={"Student ID": str})

    assert len(master) == 6
    assert set(master["Student ID"]) == set(grouped_classlist["Student ID"])


def test_a_brightspace_group_assessment_without_groups_says_which_import(
    tmp_path, classlist
):
    a = make_module(
        tmp_path, group=True, group_source="brightspace"
    ).assessment("cw1")

    with pytest.raises(ValueError) as excinfo:
        allocate_graders(a, classlist, seed=1)

    message = str(excinfo.value)
    assert "group=True" in message
    assert "Last Name" in message  # names the columns that are there


# ---------------------------------------------------------------------------
# Group, made by the module leader
# ---------------------------------------------------------------------------


@pytest.fixture
def leader_module(tmp_path):
    """A leader-managed group assessment with its three sheets written."""
    module = make_module(tmp_path, group=True, group_source="module_leader")
    a = module.assessment("cw1")
    write_group_sheet(a.group_sheets_path, "Team 1", ["23304300", "23304301"])
    write_group_sheet(a.group_sheets_path, "Team 2", ["23304302", "23304303"])
    write_group_sheet(a.group_sheets_path, "Team 3", ["23304304", "23304305"])
    return module


def test_the_leaders_sheets_are_collected_into_one_file(leader_module):
    a = leader_module.assessment("cw1")

    membership = build_group_membership(a)

    assert membership.path == a.group_membership_path
    assert membership.path.exists()
    written = pd.read_csv(membership.path, dtype=str)
    assert list(written.columns) == ["Student ID", "Group"]
    assert len(written) == 6


def test_collecting_can_be_asked_not_to_write(leader_module):
    a = leader_module.assessment("cw1")

    membership = build_group_membership(a, save=False)

    assert membership.path is None
    assert not a.group_membership_path.exists()


def test_only_a_leader_managed_assessment_has_sheets_to_collect(
    tmp_path, grouped_classlist
):
    a = make_module(
        tmp_path, group=True, group_source="brightspace"
    ).assessment("cw1")

    with pytest.raises(ValueError, match="does not keep its own group sheets"):
        build_group_membership(a)


def test_allocating_collects_the_groups_first(leader_module, classlist):
    """No group=True import needed: the groups were never in Brightspace."""
    a = leader_module.assessment("cw1")

    allocation = allocate_graders(a, classlist, seed=1)

    assert allocation.membership == a.group_membership_path
    assert allocation.membership.exists()
    per_group = allocation.frame.groupby("Group")["grader"].nunique()
    assert (per_group == 1).all()


def test_a_leader_managed_grader_workbook_has_one_row_per_student(
    leader_module, classlist
):
    """Brightspace knows nothing about these groups, so it gives each student
    their own folder and their own feedback sheet -- and the marks within a
    group may legitimately differ."""
    a = leader_module.assessment("cw1")

    allocation = allocate_graders(a, classlist, seed=1)

    assert len(allocation.per_grader) == 6
    written = pd.concat(
        pd.read_excel(path, dtype={"Student ID": str})
        for path in allocation.workbooks.values()
    )
    assert len(written) == 6
    assert "Student ID" in written.columns
    assert "Mark" in written.columns


def test_a_grader_gets_whole_teams_not_scattered_students(
    leader_module, classlist
):
    a = leader_module.assessment("cw1")

    allocation = allocate_graders(a, classlist, seed=1)

    for path in allocation.workbooks.values():
        written = pd.read_excel(path, dtype={"Student ID": str})
        if written.empty:
            continue
        # Every student the grader has from a team, they have all of.
        sizes = written.groupby("Group").size()
        assert (sizes == 2).all()


def test_a_student_left_off_every_sheet_stops_the_allocation(
    leader_module, classlist
):
    """Before graders have workbooks, not after."""
    a = leader_module.assessment("cw1")
    (a.group_sheets_path / "Team 3.xlsx").unlink()

    with pytest.raises(ValueError) as excinfo:
        allocate_graders(a, classlist, seed=1)

    assert "23304304" in str(excinfo.value)
    assert not list(a.grading_output_path.glob("*.xlsx"))


def test_missing_group_sheets_say_what_they_were(leader_module, classlist):
    a = leader_module.assessment("cw1")
    for sheet in a.group_sheets_path.iterdir():
        sheet.unlink()
    a.group_sheets_path.rmdir()

    with pytest.raises(FileNotFoundError, match="one per team"):
        allocate_graders(a, classlist, seed=1)


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


def test_an_unbound_assessment_will_not_be_allocated(classlist):
    """It would resolve its paths against the cwd and write files there."""
    from grader_helper import Assessment

    a = Assessment(
        id="cw1", type="coursework", name="Coursework 1", marks_out_of=100, weight=100
    )
    with pytest.raises(ValueError, match="does not know where it lives"):
        allocate_graders(a, classlist, GRADERS)


# ---------------------------------------------------------------------------
# Which column is the group
# ---------------------------------------------------------------------------


def _ml_sheet(folder, **columns):
    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns).to_excel(folder / "PS4001 groups.xlsx", index=False)


def test_an_ambiguous_group_sheet_stops_the_allocation(tmp_path, classlist):
    """Before graders have workbooks, and before anything is written."""
    a = make_module(
        tmp_path, group=True, group_source="module_leader"
    ).assessment("cw1")
    _ml_sheet(
        a.group_sheets_path,
        **{
            "Student Id": [f"2330430{i}" for i in range(6)],
            "Team": [1, 1, 2, 2, 1, 1],
            "Grp Code": ["2A"] * 4 + ["2B"] * 2,
            "Group": ["2A_1", "2A_1", "2A_2", "2A_2", "2B_1", "2B_1"],
        },
    )

    with pytest.raises(AmbiguousGroupError, match="group_column="):
        allocate_graders(a, classlist, seed=1)

    assert not list(a.grading_output_path.glob("*.xlsx"))


def test_the_assessment_can_answer_which_column(tmp_path, classlist):
    """`group_column` in module.toml settles it once, so a leader whose
    sheets always look like this never passes it again."""
    a = make_module(
        tmp_path, group=True, group_source="module_leader",
        group_column="Group",
    ).assessment("cw1")
    _ml_sheet(
        a.group_sheets_path,
        **{
            "Student Id": [f"2330430{i}" for i in range(6)],
            "Team": [1, 1, 2, 2, 1, 1],
            "Grp Code": ["2A"] * 4 + ["2B"] * 2,
            "Group": ["2A_1", "2A_1", "2A_2", "2A_2", "2B_1", "2B_1"],
        },
    )

    allocation = allocate_graders(a, classlist, seed=1)

    assert sorted(allocation.frame["Group"].unique()) == ["2A_1", "2A_2", "2B_1"]
    assert (allocation.frame.groupby("Group")["grader"].nunique() == 1).all()


def test_naming_team_instead_is_honoured(tmp_path, classlist):
    """The other of the two. A sheet whose teams are numbered straight
    through the cohort says Team and means it."""
    a = make_module(
        tmp_path, group=True, group_source="module_leader",
        group_column="Team",
    ).assessment("cw1")
    _ml_sheet(
        a.group_sheets_path,
        **{
            "Student Id": [f"2330430{i}" for i in range(6)],
            "Team": [1, 1, 2, 2, 3, 3],
            "Group": ["2A_1", "2A_1", "2A_2", "2A_2", "2B_1", "2B_1"],
        },
    )

    allocation = allocate_graders(a, classlist, seed=1)

    assert sorted(allocation.frame["Group"].unique()) == ["1", "2", "3"]
