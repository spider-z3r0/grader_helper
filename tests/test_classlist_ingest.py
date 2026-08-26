#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Ingesting a Brightspace class list export.

Exercised against a real export shape. Brightspace ships these columns:

    OrgDefinedId, Username, Last Name, First Name, Email,
    End-of-Line Indicator

Username carries a leading '#', e.g. "#56170559", and the student ID is
that value with the '#' removed. Every downstream consumer -- folder
renaming, missing-submission detection, grade collation -- matches on the
bare digits parsed out of a submission folder name, so the '#' must be
stripped at ingest or nothing matches.
"""

import pandas as pd
import pytest

from grader_helper import import_brightspace_classlist, load_graders
from grader_helper.ingesting.import_brightspace_classlist import MissingGroupError

RAW_COLUMNS = [
    "OrgDefinedId",
    "Username",
    "Last Name",
    "First Name",
    "Email",
    "End-of-Line Indicator",
]


@pytest.fixture
def classlist_file(resources_dir):
    return resources_dir / "fake_class_list.xlsx"


@pytest.fixture
def group_classlist_file(classlist_file, tmp_path):
    """The same export with a Group Name column, as a group assignment has."""
    df = pd.read_excel(classlist_file)
    df["Group Name"] = [f"Team {i % 5 + 1}" for i in range(len(df))]
    out = tmp_path / "fake_class_list_groups.xlsx"
    df.to_excel(out, index=False)
    return out


def test_the_export_has_the_expected_raw_shape(classlist_file):
    """Pin the input shape, so a Brightspace change is a test failure."""
    df = pd.read_excel(classlist_file)
    assert list(df.columns) == RAW_COLUMNS
    assert df["Username"].str.startswith("#").all()


def test_individual_ingest_selects_and_renames(classlist_file):
    out = import_brightspace_classlist(classlist_file)
    assert list(out.columns) == ["Student ID", "Last Name", "First Name", "Score"]
    assert (out["Score"] == "").all()
    assert len(out) == 100


def test_individual_ingest_strips_the_hash(classlist_file):
    out = import_brightspace_classlist(classlist_file)
    assert not out["Student ID"].str.contains("#").any()
    assert out["Student ID"].str.match(r"^\d+$").all()


def test_group_ingest_selects_and_renames(group_classlist_file):
    out = import_brightspace_classlist(group_classlist_file, group=True)
    assert list(out.columns) == [
        "Student ID",
        "Last Name",
        "First Name",
        "Group",
        "Score",
    ]
    assert out["Group"].nunique() == 5


def test_group_ingest_strips_the_hash(group_classlist_file):
    """The group branch must strip '#' exactly as the individual one does.

    It previously did not: the branch carried a redundant re-rename of
    Username -- already done above, so dead code -- where the individual
    branch has the strip. Every downstream match then failed, because
    folder names yield bare digits. find_unsubmitted reported the entire
    cohort missing including students who had submitted, and
    alphabetise_folders failed every rename with 'Student Number not
    present in class list' for students who were on the list.
    """
    out = import_brightspace_classlist(group_classlist_file, group=True)
    assert not out["Student ID"].str.contains("#").any()
    assert out["Student ID"].str.match(r"^\d+$").all()


def test_both_modes_agree_on_student_id(classlist_file, group_classlist_file):
    """The same student must get the same ID either way."""
    individual = import_brightspace_classlist(classlist_file)
    grouped = import_brightspace_classlist(group_classlist_file, group=True)
    pd.testing.assert_series_equal(
        individual["Student ID"], grouped["Student ID"], check_names=False
    )


def test_normalise_lowercases_and_underscores_columns(classlist_file):
    out = import_brightspace_classlist(classlist_file, normalise=True)
    assert list(out.columns) == ["student_id", "last_name", "first_name", "score"]


def test_unsupported_filetype_returns_none(tmp_path):
    bad = tmp_path / "classlist.txt"
    bad.write_text("nope")
    assert import_brightspace_classlist(bad) is None


def test_missing_file_returns_none(tmp_path):
    assert import_brightspace_classlist(tmp_path / "nope.csv") is None


def test_load_graders_reads_one_name_per_line(resources_dir):
    assert load_graders(resources_dir / "graders.txt") == [
        "KOM",
        "SOB",
        "ABC",
        "DEF",
    ]


# ---------------------------------------------------------------------------
# Locating the group column
# ---------------------------------------------------------------------------
#
# A group column reaches the class list one of two ways: Brightspace's own
# group function exports it as "Group Name", or the module leader adds it by
# hand and may call it whatever they like. group=True has to cope with both.


def _classlist_with_group_column(classlist_file, tmp_path, column_name):
    df = pd.read_excel(classlist_file)
    df[column_name] = [f"Team {i % 5 + 1}" for i in range(len(df))]
    out = tmp_path / f"classlist_{column_name.replace(' ', '_')}.xlsx"
    df.to_excel(out, index=False)
    return out


@pytest.mark.parametrize(
    "column_name",
    [
        "Group Name",   # what Brightspace's group function exports
        "Group",        # already normalised
        "group name",   # module leader, lowercase
        "GROUP NAME",   # module leader, shouting
        "group",
        "Groups",
        "Team",         # a module leader thinking in teams
        "Group_Name",
    ],
)
def test_group_column_is_found_however_it_is_named(
    classlist_file, tmp_path, column_name
):
    path = _classlist_with_group_column(classlist_file, tmp_path, column_name)

    out = import_brightspace_classlist(path, group=True)

    assert out is not None, f"failed to find a group column named {column_name!r}"
    assert "Group" in out.columns
    assert out["Group"].nunique() == 5


def test_an_explicitly_named_group_column_is_honoured(classlist_file, tmp_path):
    """An escape hatch for a name nobody could reasonably guess."""
    path = _classlist_with_group_column(classlist_file, tmp_path, "Tutorial Cohort")

    out = import_brightspace_classlist(
        path, group=True, group_column="Tutorial Cohort"
    )

    assert out is not None
    assert out["Group"].nunique() == 5


def test_missing_group_column_reports_what_it_looked_for(
    classlist_file, capsys
):
    """A class list with no group column at all must say so clearly."""
    out = import_brightspace_classlist(classlist_file, group=True)

    assert out is None
    message = capsys.readouterr().out
    assert "group" in message.lower()
    # The message must name the columns that ARE present, so the user can see
    # what to rename.
    assert "Last Name" in message


# ---------------------------------------------------------------------------
# Students with no group
# ---------------------------------------------------------------------------
#
# A blank group is almost always an oversight -- a student who joined late,
# or a row the module leader missed. It must be raised loudly so it can be
# resolved, never quietly carried forward, because a NaN group silently
# becomes its own group at allocation and the student's work is marked
# outside their team.
#
# A student legitimately working alone is recorded with the SOLO sentinel.


def _classlist_with_groups(classlist_file, tmp_path, groups, name="groups.xlsx"):
    """Write a class list whose first len(groups) rows carry those groups."""
    df = pd.read_excel(classlist_file).head(len(groups)).copy()
    df["Group Name"] = groups
    out = tmp_path / name
    df.to_excel(out, index=False)
    return out


def test_blank_group_raises_and_names_the_student(classlist_file, tmp_path):
    path = _classlist_with_groups(
        classlist_file, tmp_path, ["Team 1", None, "Team 2"]
    )

    with pytest.raises(MissingGroupError) as excinfo:
        import_brightspace_classlist(path, group=True)

    message = str(excinfo.value)
    # The second row of the fixture is Alexander Miller, #57156377.
    assert "57156377" in message
    assert "Miller" in message


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_all_the_ways_a_group_can_be_blank(classlist_file, tmp_path, blank):
    path = _classlist_with_groups(classlist_file, tmp_path, ["Team 1", blank])
    with pytest.raises(MissingGroupError):
        import_brightspace_classlist(path, group=True)


def test_every_affected_student_is_listed(classlist_file, tmp_path):
    path = _classlist_with_groups(
        classlist_file, tmp_path, ["Team 1", None, None, None]
    )

    with pytest.raises(MissingGroupError) as excinfo:
        import_brightspace_classlist(path, group=True)

    message = str(excinfo.value)
    assert "3" in message  # the count
    for sid in ("57156377", "59299972", "51420861"):
        assert sid in message


def test_the_error_explains_both_remedies(classlist_file, tmp_path):
    path = _classlist_with_groups(classlist_file, tmp_path, ["Team 1", None])

    with pytest.raises(MissingGroupError) as excinfo:
        import_brightspace_classlist(path, group=True)

    message = str(excinfo.value).lower()
    assert "solo" in message


@pytest.mark.parametrize("sentinel", ["SOLO", "solo", "Solo", "individual", "ALONE"])
def test_solo_is_accepted_however_it_is_spelled(
    classlist_file, tmp_path, sentinel
):
    path = _classlist_with_groups(
        classlist_file, tmp_path, ["Team 1", sentinel, "Team 1"]
    )

    out = import_brightspace_classlist(path, group=True)

    assert out is not None
    assert out["Group"].notna().all()


def test_each_solo_student_is_their_own_group(classlist_file, tmp_path):
    """Otherwise every solo student is marked by the same grader.

    assign_graders_groups gives one grader per distinct group value, so if
    three solo students all carried the literal string "SOLO" they would be
    treated as a single three-person team.
    """
    path = _classlist_with_groups(
        classlist_file, tmp_path, ["Team 1", "SOLO", "SOLO", "SOLO"]
    )

    out = import_brightspace_classlist(path, group=True)

    solo = out[out["Group"].str.upper().str.startswith("SOLO")]
    assert len(solo) == 3
    assert solo["Group"].nunique() == 3, (
        f"solo students share a group: {solo['Group'].tolist()}"
    )


def test_solo_group_names_identify_the_student(classlist_file, tmp_path):
    path = _classlist_with_groups(classlist_file, tmp_path, ["SOLO"])

    out = import_brightspace_classlist(path, group=True)

    assert "56170559" in out["Group"].iloc[0]


def test_ordinary_groups_are_left_alone(classlist_file, tmp_path):
    path = _classlist_with_groups(
        classlist_file, tmp_path, ["Team 1", "Team 2", "Team 1"]
    )

    out = import_brightspace_classlist(path, group=True)

    assert out["Group"].tolist() == ["Team 1", "Team 2", "Team 1"]
