#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Group assessments: saying which kind, and collecting a leader's own groups.

Two kinds of group assessment, and they are not variations on each other:

``brightspace``
    Brightspace made the groups, so they come down in the class list and the
    download is one folder per team.
``module_leader``
    The leader made them, in sheets of their own, and the download is the
    ordinary per-student shape.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl

import pandas as pd
import pytest

from grader_helper import (
    AmbiguousGroupError,
    Assessment,
    ConflictingGroupsError,
    GroupSource,
    MissingGroupError,
    attach_group_membership,
    collect_group_membership,
)


def write_group_sheet(folder: pl.Path, name: str, ids, suffix: str = ".xlsx", **extra):
    """One team's sheet, named for the team."""
    folder.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame({"Student ID": list(ids), **extra})
    path = folder / f"{name}{suffix}"
    if suffix == ".csv":
        frame.to_csv(path, index=False)
    else:
        frame.to_excel(path, index=False)
    return path


@pytest.fixture
def group_sheets(tmp_path) -> pl.Path:
    """Three teams, one sheet each, named for the team."""
    folder = tmp_path / "groups"
    write_group_sheet(folder, "Team 1", ["23304300", "23304301"])
    write_group_sheet(folder, "Team 2", ["23304302", "23304303"])
    write_group_sheet(folder, "Team 3", ["23304304", "23304305"])
    return folder


# ---------------------------------------------------------------------------
# The model: a group assessment has to say which kind it is
# ---------------------------------------------------------------------------


def _spec(**overrides):
    base = dict(
        id="cw1", type="coursework", name="Coursework 1", marks_out_of=100, weight=40
    )
    return {**base, **overrides}


def test_a_group_assessment_must_say_where_its_groups_come_from():
    """`group = true` alone decides neither where membership is nor whose the mark is."""
    with pytest.raises(ValueError, match="does not say where its groups come from"):
        Assessment(**_spec(group=True))


@pytest.mark.parametrize("source", ["brightspace", "module_leader"])
def test_either_group_source_is_accepted(source):
    assessment = Assessment(**_spec(group=True, group_source=source))
    assert assessment.group_source is GroupSource(source)


def test_an_unknown_group_source_is_refused():
    with pytest.raises(ValueError):
        Assessment(**_spec(group=True, group_source="microsoft_teams"))


def test_a_group_source_without_group_is_refused():
    """Nothing would read it, and the assessment would be allocated per student."""
    with pytest.raises(ValueError, match="but group is false"):
        Assessment(**_spec(group_source="brightspace"))


def test_an_individual_assessment_stays_individual_by_default():
    assessment = Assessment(**_spec())
    assert assessment.group is False
    assert assessment.group_source is None


def test_a_group_column_can_be_recorded_on_the_assessment():
    """Asked once in module.toml, not on every run."""
    one = Assessment(**_spec(group=True, group_source="module_leader",
                             group_column="Group"))
    composed = Assessment(**_spec(group=True, group_source="module_leader",
                                  group_column=["Cohort", "Team"]))

    assert one.group_column == "Group"
    assert composed.group_column == ["Cohort", "Team"]


def test_a_group_column_without_group_is_refused():
    """Nothing would read it -- an individual assessment has no group to
    find a column for."""
    with pytest.raises(ValueError, match="group_column but group is"):
        Assessment(**_spec(group_column="Group"))


# ---------------------------------------------------------------------------
# Paths: only a leader-managed assessment has group sheets
# ---------------------------------------------------------------------------


@pytest.fixture
def bound(tmp_path):
    """Build an assessment bound to tmp_path, as Module does on load."""

    def build(**overrides):
        return Assessment(**_spec(**overrides)).bind(tmp_path)

    return build


def test_leader_managed_groups_get_a_sheets_folder_and_a_collected_file(
    bound, tmp_path
):
    a = bound(group=True, group_source="module_leader")

    assert a.group_sheets_path == tmp_path / "cw1" / "groups"
    assert a.group_membership_path == (
        tmp_path / "cw1" / "grading_output" / "group_membership.csv"
    )
    # init_module creates it, so the leader has somewhere to put the sheets.
    assert a.group_sheets_path in a.directories


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        dict(group=True, group_source="brightspace"),
    ],
    ids=["individual", "brightspace"],
)
def test_nothing_else_has_group_sheets(bound, overrides):
    """A folder nothing ever writes to should not be created or offered."""
    a = bound(**overrides)
    assert a.group_sheets_path is None
    assert a.group_membership_path is None
    assert all("groups" != d.name for d in a.directories)


# ---------------------------------------------------------------------------
# collect_group_membership
# ---------------------------------------------------------------------------


def test_one_sheet_per_team_named_for_the_team(group_sheets):
    membership = collect_group_membership(group_sheets)

    assert list(membership.columns) == ["Student ID", "Group"]
    assert len(membership) == 6
    assert set(membership["Group"]) == {"Team 1", "Team 2", "Team 3"}
    assert membership.loc[
        membership["Student ID"] == "23304303", "Group"
    ].item() == "Team 2"


def test_student_ids_come_back_as_text(group_sheets):
    """Ints here lose leading zeros and stop matching the class list."""
    membership = collect_group_membership(group_sheets)
    assert membership["Student ID"].map(type).eq(str).all()


def test_a_leading_hash_is_stripped(tmp_path):
    """Brightspace writes the username as '#23304300'; a pasted sheet keeps it."""
    write_group_sheet(tmp_path / "groups", "Team 1", ["#23304300"])
    membership = collect_group_membership(tmp_path / "groups")
    assert membership["Student ID"].tolist() == ["23304300"]


def test_csv_and_xlsx_sheets_are_both_read(tmp_path):
    folder = tmp_path / "groups"
    write_group_sheet(folder, "Team 1", ["23304300"], suffix=".xlsx")
    write_group_sheet(folder, "Team 2", ["23304301"], suffix=".csv")

    membership = collect_group_membership(folder)
    assert set(membership["Group"]) == {"Team 1", "Team 2"}


def test_one_workbook_with_a_tab_per_team(tmp_path):
    """The other way a leader keeps them: one file, one sheet per group."""
    path = tmp_path / "groups.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"Student ID": ["23304300", "23304301"]}).to_excel(
            writer, sheet_name="Team 1", index=False
        )
        pd.DataFrame({"Student ID": ["23304302"]}).to_excel(
            writer, sheet_name="Team 2", index=False
        )

    membership = collect_group_membership(path)
    assert set(membership["Group"]) == {"Team 1", "Team 2"}
    assert len(membership) == 3


def test_a_single_sheet_workbook_is_named_by_its_file(tmp_path):
    """A workbook saved from a template is called 'Sheet1' inside, whatever
    the file is called. The filename is the one the leader chose."""
    folder = tmp_path / "groups"
    folder.mkdir()
    pd.DataFrame({"Student ID": ["23304300"]}).to_excel(
        folder / "Team 7.xlsx", index=False, sheet_name="Sheet1"
    )

    membership = collect_group_membership(folder)
    assert membership["Group"].tolist() == ["Team 7"]


def test_a_group_column_inside_a_sheet_wins_over_its_name(tmp_path):
    """A leader who wrote a group column meant it -- and it is the only way
    to put two teams in one sheet."""
    folder = tmp_path / "groups"
    write_group_sheet(
        folder,
        "everyone",
        ["23304300", "23304301"],
        Group=["Team 4", "Team 5"],
    )

    membership = collect_group_membership(folder)
    assert set(membership["Group"]) == {"Team 4", "Team 5"}


def test_trailing_blank_rows_are_not_students(tmp_path):
    """Hand-made sheets have blank rows at the bottom and between teams."""
    folder = tmp_path / "groups"
    folder.mkdir()
    pd.DataFrame({"Student ID": ["23304300", None, "23304301", ""]}).to_csv(
        folder / "Team 1.csv", index=False
    )

    membership = collect_group_membership(folder)
    assert membership["Student ID"].tolist() == ["23304300", "23304301"]


def test_the_same_student_twice_in_one_group_is_one_student(tmp_path):
    write_group_sheet(tmp_path / "groups", "Team 1", ["23304300", "23304300"])
    membership = collect_group_membership(tmp_path / "groups")
    assert membership["Student ID"].tolist() == ["23304300"]


def test_a_student_in_two_groups_is_refused(tmp_path):
    """Taking the last one seen marks their work with a team they were not in."""
    folder = tmp_path / "groups"
    write_group_sheet(folder, "Team 1", ["23304300", "23304301"])
    write_group_sheet(folder, "Team 2", ["23304301"])

    with pytest.raises(ConflictingGroupsError) as excinfo:
        collect_group_membership(folder)

    message = str(excinfo.value)
    assert "23304301" in message
    assert "Team 1" in message and "Team 2" in message
    # The one who is fine is not named as a problem.
    assert "23304300" not in message


def test_a_sheet_with_no_id_column_names_the_columns_it_has(tmp_path):
    folder = tmp_path / "groups"
    folder.mkdir()
    pd.DataFrame({"Who": ["Kevin"], "Notes": ["late"]}).to_csv(
        folder / "Team 1.csv", index=False
    )

    with pytest.raises(ValueError) as excinfo:
        collect_group_membership(folder)

    message = str(excinfo.value)
    assert "Team 1.csv" in message
    assert "'Who'" in message and "'Notes'" in message


@pytest.mark.parametrize(
    "column", ["Student ID", "student_id", "Student Number", "ID", "Username"]
)
def test_the_id_column_is_found_however_it_is_named(tmp_path, column):
    folder = tmp_path / "groups"
    folder.mkdir()
    pd.DataFrame({column: ["23304300"]}).to_csv(folder / "Team 1.csv", index=False)

    assert collect_group_membership(folder)["Student ID"].tolist() == ["23304300"]


def test_an_unusually_named_id_column_can_be_given(tmp_path):
    folder = tmp_path / "groups"
    folder.mkdir()
    pd.DataFrame({"Who they are": ["23304300"]}).to_csv(
        folder / "Team 1.csv", index=False
    )

    membership = collect_group_membership(folder, id_column="Who they are")
    assert membership["Student ID"].tolist() == ["23304300"]


def test_a_missing_groups_folder_says_what_it_wanted(tmp_path):
    with pytest.raises(FileNotFoundError, match="one per team"):
        collect_group_membership(tmp_path / "nothing here")


def test_an_empty_groups_folder_says_what_it_looked_for(tmp_path):
    (tmp_path / "groups").mkdir()
    with pytest.raises(ValueError, match="No group sheets in"):
        collect_group_membership(tmp_path / "groups")


def test_excel_lock_files_are_not_group_sheets(tmp_path):
    """'~$Team 1.xlsx' means someone has the sheet open, not a fourth team."""
    folder = tmp_path / "groups"
    write_group_sheet(folder, "Team 1", ["23304300"])
    (folder / "~$Team 1.xlsx").write_bytes(b"not really a workbook")

    membership = collect_group_membership(folder)
    assert membership["Group"].tolist() == ["Team 1"]


def test_sheets_naming_nobody_are_refused(tmp_path):
    folder = tmp_path / "groups"
    folder.mkdir()
    pd.DataFrame({"Student ID": []}).to_csv(folder / "Team 1.csv", index=False)

    with pytest.raises(ValueError, match="name no students"):
        collect_group_membership(folder)


# ---------------------------------------------------------------------------
# attach_group_membership -- the point where the two kinds become one shape
# ---------------------------------------------------------------------------


@pytest.fixture
def six_student_classlist():
    return pd.DataFrame(
        {
            "Student ID": [f"2330430{i}" for i in range(6)],
            "Last Name": list("ABCDEF"),
            "First Name": list("abcdef"),
            "Score": [""] * 6,
        }
    )


def test_a_class_list_comes_back_with_a_group_column(
    six_student_classlist, group_sheets
):
    membership = collect_group_membership(group_sheets)
    out = attach_group_membership(six_student_classlist, membership)

    assert out["Group"].tolist() == [
        "Team 1", "Team 1", "Team 2", "Team 2", "Team 3", "Team 3"
    ]


def test_the_group_column_lands_where_brightspace_puts_it(
    six_student_classlist, group_sheets
):
    """Both kinds have to produce the same frame, or downstream code has to
    know which one it is looking at."""
    membership = collect_group_membership(group_sheets)
    out = attach_group_membership(six_student_classlist, membership)

    assert list(out.columns) == [
        "Student ID", "Last Name", "First Name", "Group", "Score"
    ]


def test_a_student_in_no_group_is_refused_by_name(
    six_student_classlist, group_sheets
):
    """A student with no group is silently a group of one, marked apart from
    everyone -- the same refusal as a Brightspace group class list."""
    membership = collect_group_membership(group_sheets)
    membership = membership[membership["Student ID"] != "23304303"]

    with pytest.raises(MissingGroupError) as excinfo:
        attach_group_membership(six_student_classlist, membership)

    assert "23304303" in str(excinfo.value)


def test_a_student_marked_solo_gets_a_group_of_their_own(
    six_student_classlist, tmp_path
):
    folder = tmp_path / "groups"
    write_group_sheet(folder, "Team 1", [f"2330430{i}" for i in range(5)])
    write_group_sheet(folder, "SOLO", ["23304305"])

    out = attach_group_membership(
        six_student_classlist, collect_group_membership(folder)
    )

    solo = out.loc[out["Student ID"] == "23304305", "Group"].item()
    assert solo == "SOLO (23304305)"


def test_a_student_in_the_sheets_but_not_the_class_list_is_flagged(
    six_student_classlist, group_sheets
):
    """The other half of a mistyped id: it shows up here and as a student
    with no group."""
    membership = collect_group_membership(group_sheets)
    membership.loc[membership["Student ID"] == "23304305", "Student ID"] = "23304355"

    with pytest.warns(UserWarning, match="23304355"):
        with pytest.raises(MissingGroupError, match="23304305"):
            attach_group_membership(six_student_classlist, membership)


# ---------------------------------------------------------------------------
# The module leader's real file: one sheet, several columns that look like
# the group, and an id column in title case
# ---------------------------------------------------------------------------
#
#   Name          Student Id   Team   Grp Code   Group
#   LAST FIRST    12345678     1      2A         2A_1
#   LAST2 FIRST2  12345679     1      2A         2A_1
#   LAST3 FIRST3  12345680     2      2A         2A_2
#   LAST4 FIRST4  12345681     1      2B         2B_1
#
# `Team`, `Grp Code` and `Group` are all recognised names, and Team and
# Group are NOT the same partition: on Team the first and last students are
# one team, on Group they are two.


@pytest.fixture
def ml_groups_file(tmp_path) -> pl.Path:
    """The leader's own file, as it actually arrives."""
    path = tmp_path / "PS4001 groups.xlsx"
    pd.DataFrame(
        {
            "Name": [f"LAST{i} FIRST{i}" for i in range(4)],
            "Student Id": ["12345678", "12345679", "12345680", "12345681"],
            "Team": [1, 1, 2, 1],
            "Grp Code": ["2A", "2A", "2A", "2B"],
            "Group": ["2A_1", "2A_1", "2A_2", "2B_1"],
        }
    ).to_excel(path, index=False)
    return path


def test_a_title_case_id_column_still_joins(ml_groups_file):
    """'Student Id' is not 'Student ID'. The frame has to come back with the
    name everything downstream merges on, whatever the sheet called it."""
    membership = collect_group_membership(ml_groups_file, group_column="Group")

    assert list(membership.columns) == ["Student ID", "Group"]
    assert sorted(membership["Student ID"]) == [
        "12345678", "12345679", "12345680", "12345681"
    ]


def test_columns_that_disagree_are_refused_not_ranked(ml_groups_file):
    """`Team` and `Group` are both recognised and they cut the cohort
    differently. Alias order picks Group here and is right by luck; reorder
    the tuple and two teams reach one grader as one team, with one mark."""
    with pytest.raises(AmbiguousGroupError) as excinfo:
        collect_group_membership(ml_groups_file)

    message = str(excinfo.value)
    assert "'Team'" in message and "'Group'" in message
    assert "group_column=" in message
    # Names the file, so a folder of sheets says which one.
    assert "PS4001 groups.xlsx" in message


@pytest.mark.parametrize(
    "asked", ["Grp Code", "grp code", "GRP_CODE", "Group Code", "groupcode"]
)
def test_a_group_code_is_never_the_group(ml_groups_file, asked):
    """It is produced elsewhere, for something else, and only looks like the
    group because the group label is built out of it -- '2A_1' contains
    '2A'. Allocating on it puts students who are not in a team together in
    front of one grader, with team names that read perfectly."""
    with pytest.raises(ValueError, match="is not the group"):
        collect_group_membership(ml_groups_file, group_column=asked)


def test_a_group_code_cannot_be_composed_into_the_key_either(ml_groups_file):
    """The way it was previously suggested, which is where the danger was."""
    with pytest.raises(ValueError, match="is not the group"):
        collect_group_membership(
            ml_groups_file, group_column=["Grp Code", "Team"]
        )


def test_a_group_code_is_never_offered_as_the_answer(ml_groups_file):
    """The ambiguity message used to name it as the composed example."""
    with pytest.raises(AmbiguousGroupError) as excinfo:
        collect_group_membership(ml_groups_file)

    assert "Grp Code" not in str(excinfo.value).split("Columns here:")[0]


def test_naming_the_column_settles_it(ml_groups_file):
    membership = collect_group_membership(ml_groups_file, group_column="Group")

    assert membership["Group"].tolist() == ["2A_1", "2A_1", "2A_2", "2B_1"]


def test_a_group_key_can_be_composed_from_two_columns(tmp_path):
    """The case with no combined column at all: the cohort and the team
    are only a group together. Alone, team 1 of 2A and team 1 of 2B are
    one team."""
    path = tmp_path / "groups.xlsx"
    pd.DataFrame(
        {
            "Student Id": ["12345678", "12345679", "12345680"],
            "Team": [1, 2, 1],
            "Cohort": ["2A", "2A", "2B"],
        }
    ).to_excel(path, index=False)

    membership = collect_group_membership(
        path, group_column=["Cohort", "Team"]
    )

    assert membership["Group"].tolist() == ["2A_1", "2A_2", "2B_1"]


def test_columns_that_agree_are_not_worth_asking_about(tmp_path):
    """Two recognised columns that cut the cohort identically. Which one is
    used cannot change a single allocation, so it is not a question."""
    path = tmp_path / "groups.xlsx"
    pd.DataFrame(
        {
            "Student Id": ["12345678", "12345679", "12345680"],
            "Team": ["1", "1", "2"],
            "Group": ["Team 1", "Team 1", "Team 2"],
        }
    ).to_excel(path, index=False)

    membership = collect_group_membership(path)

    assert membership["Group"].nunique() == 2


def test_a_composed_key_with_a_blank_part_is_no_group_at_all(tmp_path):
    """'2A_' is a group as far as everything downstream is concerned, so a
    student missing a team stays visibly without one -- and is named by the
    same refusal as a student left off the sheets entirely."""
    path = tmp_path / "groups.csv"
    pd.DataFrame(
        {"Student Id": ["12345678", "12345679"],
         "Cohort": ["2A", "2A"],
         "Team": ["1", None]}
    ).to_csv(path, index=False)

    membership = collect_group_membership(
        path, group_column=["Cohort", "Team"]
    )

    blank = membership.loc[membership["Student ID"] == "12345679", "Group"]
    assert blank.isna().all(), "a half key is not a group"

    class_list = pd.DataFrame(
        {"Student ID": ["12345678", "12345679"],
         "Last Name": ["A", "B"], "First Name": ["a", "b"], "Score": ["", ""]}
    )
    with pytest.raises(MissingGroupError, match="12345679"):
        attach_group_membership(class_list, membership)


# ---------------------------------------------------------------------------
# One file rather than a folder of them
# ---------------------------------------------------------------------------
#
# `group_sheets` defaults to a folder called `groups/`, and a leader who
# keeps every team in one workbook is at least as common as one who keeps a
# file per team. The reader always took either; the model did not.


def test_group_sheets_can_name_one_file(bound, tmp_path):
    a = bound(group=True, group_source="module_leader", group_sheets="groups.xlsx")

    assert a.group_sheets_path == tmp_path / "cw1" / "groups.xlsx"
    assert a.group_sheets_is_file


def test_a_folder_of_sheets_is_still_a_folder(bound, tmp_path):
    a = bound(group=True, group_source="module_leader")

    assert a.group_sheets_path == tmp_path / "cw1" / "groups"
    assert not a.group_sheets_is_file


def test_no_folder_is_created_over_a_file_name(bound):
    """init_module creates what `directories` lists. A *directory* called
    groups.xlsx, sitting where the leader's workbook goes, is a mess to
    undo."""
    a = bound(group=True, group_source="module_leader", group_sheets="groups.xlsx")

    assert a.group_sheets_path not in a.directories


def test_a_folder_of_sheets_is_still_created(bound):
    a = bound(group=True, group_source="module_leader")

    assert a.group_sheets_path in a.directories
