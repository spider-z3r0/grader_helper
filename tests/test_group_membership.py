#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Groups the leader keeps themselves, and marks that reach every member.

Brightspace manages the groups on some modules and not on others, so the
membership arrives two ways. Both have to end in the same shape, checked the
same way, or a module's grader allocation would depend on how its groups
happened to be recorded.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pandas as pd
import pytest

from grader_helper import (
    assign_graders_groups,
    attach_groups,
    load_group_membership,
    spread_group_marks,
)
from grader_helper.ingesting.import_brightspace_classlist import MissingGroupError


@pytest.fixture
def class_list() -> pd.DataFrame:
    """Four students, as import_brightspace_classlist returns them."""
    return pd.DataFrame(
        {
            "Student ID": ["23304301", "23304302", "23304303", "00123456"],
            "Last Name": ["Egan", "Angood", "Joyce", "Lynch"],
            "First Name": ["Aoife", "Ben", "Cara", "Dan"],
            "Score": ["", "", "", ""],
        }
    )


@pytest.fixture
def groups_file(tmp_path) -> "callable":
    """A hand-maintained groups spreadsheet, written however the leader did."""

    def _write(rows: dict, columns=("Student ID", "Group"), name="groups.csv"):
        path = tmp_path / name
        pd.DataFrame(
            {columns[0]: list(rows), columns[1]: list(rows.values())}
        ).to_csv(path, index=False)
        return path

    return _write


# ---------------------------------------------------------------------------
# Reading what the leader keeps
# ---------------------------------------------------------------------------


def test_it_reads_a_groups_file(groups_file):
    path = groups_file({"23304301": "Team 1", "23304302": "Team 1"})

    membership = load_group_membership(path)

    assert list(membership.columns) == ["Student ID", "Group"]
    assert membership["Student ID"].tolist() == ["23304301", "23304302"]


def test_the_columns_can_be_named_however_the_leader_named_them(groups_file):
    """It is their spreadsheet. Matching is lenient about case and spacing."""
    path = groups_file(
        {"23304301": "Team 1"}, columns=("student_id", "Group Name")
    )

    assert list(load_group_membership(path).columns) == ["Student ID", "Group"]


def test_ids_keep_their_leading_zeros_and_lose_the_hash(groups_file):
    """Both are silent-mismatch bugs.

    Read as a number an id loses its leading zero; pasted from Brightspace it
    arrives as `#00123456`. Either way it then matches no class list row and
    no submission folder.
    """
    path = groups_file({"#00123456": "Team 2"})

    assert load_group_membership(path)["Student ID"].tolist() == ["00123456"]


def test_a_file_that_is_not_there_says_what_it_is_for(tmp_path):
    with pytest.raises(FileNotFoundError, match="who is in which group"):
        load_group_membership(tmp_path / "nope.csv")


def test_a_missing_column_names_the_ones_present(groups_file):
    path = groups_file({"23304301": "Team 1"}, columns=("Student ID", "Team!!"))

    with pytest.raises(ValueError, match="Columns present"):
        load_group_membership(path)


# ---------------------------------------------------------------------------
# Putting them on the class list
# ---------------------------------------------------------------------------


def test_attaching_gives_the_shape_the_brightspace_route_gives(
    class_list, groups_file
):
    """Nothing downstream may be able to tell which route the groups came by."""
    path = groups_file(
        {
            "23304301": "Team 1",
            "23304302": "Team 1",
            "23304303": "Team 2",
            "00123456": "Team 2",
        }
    )

    grouped = attach_groups(class_list, path)

    assert "Group" in grouped.columns
    assert len(grouped) == len(class_list)
    # And it is usable by the thing it exists for.
    allocated = assign_graders_groups(grouped, ["KOM", "SOB"])
    assert allocated.groupby("Group")["grader"].nunique().eq(1).all()


def test_a_student_with_no_group_is_refused_by_name(class_list, groups_file):
    """The same refusal the Brightspace route makes, for the same reason.

    A student with no group is silently a group of one, and is then marked
    apart from their team by a grader who never saw the rest of the work.
    """
    path = groups_file({"23304301": "Team 1", "23304302": "Team 1"})

    with pytest.raises(MissingGroupError, match="23304303"):
        attach_groups(class_list, path)


def test_a_student_working_alone_gets_a_group_of_their_own(
    class_list, groups_file
):
    """SOLO is the way to say "really is on their own", and it must not
    collect every such student into one team sharing a grader."""
    path = groups_file(
        {
            "23304301": "Team 1",
            "23304302": "Team 1",
            "23304303": "SOLO",
            "00123456": "SOLO",
        }
    )

    grouped = attach_groups(class_list, path)
    solos = grouped[grouped["Student ID"].isin(["23304303", "00123456"])]

    assert solos["Group"].nunique() == 2, "two solo students are not one team"


def test_someone_in_the_file_who_left_the_module_is_not_added(
    class_list, groups_file
):
    """The class list decides who is on the module, not the groups file."""
    path = groups_file(
        {
            "23304301": "Team 1",
            "23304302": "Team 1",
            "23304303": "Team 2",
            "00123456": "Team 2",
            "99999999": "Team 3",
        }
    )

    grouped = attach_groups(class_list, path)

    assert "99999999" not in grouped["Student ID"].tolist()
    assert len(grouped) == len(class_list)


# ---------------------------------------------------------------------------
# One mark, every member
# ---------------------------------------------------------------------------


@pytest.fixture
def grouped(class_list, groups_file) -> pd.DataFrame:
    return attach_groups(
        class_list,
        groups_file(
            {
                "23304301": "Team 1",
                "23304302": "Team 1",
                "23304303": "Team 2",
                "00123456": "Team 2",
            }
        ),
    )


def test_every_member_gets_their_group_mark(grouped):
    """One piece of work, one sheet, one mark -- and a row per student on the
    departmental sheet, so the mark has to reach all of them."""
    marks = pd.DataFrame(
        {"Student ID": ["Team 1", "Team 2"], "grade": [65, 72]}
    )

    spread = spread_group_marks(marks, grouped)

    assert dict(zip(spread["Student ID"], spread["grade"])) == {
        "23304301": 65,
        "23304302": 65,
        "23304303": 72,
        "00123456": 72,
    }


def test_a_group_nobody_marked_leaves_its_members_blank(grouped):
    """Blank, not absent. A student missing from the sheet has no grade at
    all and nobody notices; a blank cell is visible."""
    marks = pd.DataFrame({"Student ID": ["Team 1"], "grade": [65]})

    spread = spread_group_marks(marks, grouped)

    assert len(spread) == 4
    assert spread.set_index("Student ID").loc["23304303", "grade"] != (
        spread.set_index("Student ID").loc["23304303", "grade"]
    ), "an unmarked group's members should be NaN"


def test_a_mark_for_a_group_nobody_is_in_is_refused(grouped):
    """Somebody's work would go missing silently otherwise."""
    marks = pd.DataFrame(
        {"Student ID": ["Team 1", "Team 9"], "grade": [65, 70]}
    )

    with pytest.raises(ValueError, match="Team 9"):
        spread_group_marks(marks, grouped)


# ---------------------------------------------------------------------------
# The two ends spell a group differently, by construction
# ---------------------------------------------------------------------------


def test_a_mark_named_by_its_feedback_sheet_still_finds_its_group(grouped):
    """The join that would otherwise fail on every group module.

    A sheet distributed into `Group 3`'s folder is called
    `Feedback sheet Group 3.xlsx`, and `catch_grades` takes the id as the
    last space-separated token of that filename -- so the mark arrives keyed
    `3` while the class list says `Team 1`, `Group 3`, or whatever the
    leader typed.
    """
    marks = pd.DataFrame({"Student ID": ["1", "2"], "grade": [65, 72]})

    spread = spread_group_marks(marks, grouped)

    assert dict(zip(spread["Student ID"], spread["grade"])) == {
        "23304301": 65,
        "23304302": 65,
        "23304303": 72,
        "00123456": 72,
    }


@pytest.mark.parametrize(
    "written, on_the_sheet",
    [
        pytest.param("Group 3", "3", id="word-dropped"),
        pytest.param("Team 03", "3", id="leading-zero"),
        pytest.param("3", "Group 3", id="the-other-way-round"),
        pytest.param("Team Alpha", "team alpha", id="not-numbered-at-all"),
    ],
)
def test_the_same_group_written_two_ways_is_one_group(
    class_list, groups_file, written, on_the_sheet
):
    grouped = attach_groups(
        class_list,
        groups_file(dict.fromkeys(class_list["Student ID"], written)),
    )
    marks = pd.DataFrame({"Student ID": [on_the_sheet], "grade": [65]})

    spread = spread_group_marks(marks, grouped)

    assert spread["grade"].tolist() == [65] * len(class_list)


def test_two_groups_that_cannot_be_told_apart_are_refused(
    class_list, groups_file
):
    """`Group 3` and `Team 3` both reduce to 3, so a sheet named for either
    would hand its mark to both. Better refused than shared."""
    grouped = attach_groups(
        class_list,
        groups_file(
            {
                "23304301": "Group 3",
                "23304302": "Group 3",
                "23304303": "Team 3",
                "00123456": "Team 3",
            }
        ),
    )
    marks = pd.DataFrame({"Student ID": ["3"], "grade": [65]})

    with pytest.raises(ValueError, match="cannot be told apart"):
        spread_group_marks(marks, grouped)
