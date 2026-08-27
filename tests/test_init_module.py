#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Creating a starter module.toml.

The file is hand-edited after it is written, so what matters is not that
init_module produces *a* file but that it produces one the author can work
with: it loads without being edited first, its explanatory comments survive
every later save, and it will not quietly replace a module's memory.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl

import pytest

from grader_helper.models import (
    MODULE_FILENAME,
    ModuleFile,
    init_module,
    load_module,
)


# ---------------------------------------------------------------------------
# What it writes
# ---------------------------------------------------------------------------


def test_a_starter_file_loads_without_being_edited(tmp_path):
    """The default weights sum to 100, so it is valid as written.

    A starter file that refuses to load until you fix it is a worse starting
    point than no file at all.
    """
    init_module(tmp_path, "PS4001", "Advanced Research Methods", "2025/26", "KOM")

    module = load_module(tmp_path)

    assert module.code == "PS4001"
    assert module.name == "Advanced Research Methods"
    assert module.year == "2025/26"
    assert module.leader.initials == "KOM"
    assert sum(a.weight for a in module.assessments) == 100


def test_it_writes_module_toml_inside_a_directory(tmp_path):
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")

    assert (tmp_path / MODULE_FILENAME).exists()


def test_it_accepts_the_file_path_itself(tmp_path):
    target = tmp_path / "PS4001.toml"

    result = init_module(target, "PS4001", "Research Methods", "2025/26", "KOM")

    assert target.exists()
    assert result.path == target


def test_the_starter_shape_demonstrates_both_column_cases(tmp_path):
    """Two-column and one-column assessments, so the rule is visible.

    Coursework marked out of 100 and worth less gets a raw and a weighted
    column; an MCQ marked on its own contribution gets one. Someone reading
    the file they were handed can see both without being told.
    """
    module = init_module(
        tmp_path, "PS4001", "Research Methods", "2025/26", "KOM"
    ).module

    assert module.grade_sheet_columns == [
        "Coursework 1 (100)",
        "Coursework 1 (40)",
        "Coursework 2 (100)",
        "Coursework 2 (50)",
        "MCQ (10)",
    ]


def test_the_explanatory_comments_are_present(tmp_path):
    """The comments are the point -- they carry what the keys cannot."""
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")

    text = (tmp_path / MODULE_FILENAME).read_text(encoding="utf-8")

    assert "marks_out_of" in text
    assert "weight" in text
    assert "sum to 100" in text
    assert "preserves your comments" in text


def test_the_module_code_and_name_head_the_file(tmp_path):
    init_module(tmp_path, "PS4001", "Advanced Research Methods", "2025/26", "KOM")

    text = (tmp_path / MODULE_FILENAME).read_text(encoding="utf-8")

    assert "# PS4001 -- Advanced Research Methods" in text


# ---------------------------------------------------------------------------
# It round-trips
# ---------------------------------------------------------------------------


def test_the_comments_survive_a_save(tmp_path):
    """What init_module writes, ModuleFile.save must not damage.

    This is the join between the two halves: a generated file is a
    hand-editable file, so it has to obey the same guarantee.
    """
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")
    before = (tmp_path / MODULE_FILENAME).read_text(encoding="utf-8")

    handle = ModuleFile.load(tmp_path)
    handle.set_status("cw1", graders_allocated=True)

    after = (tmp_path / MODULE_FILENAME).read_text(encoding="utf-8")
    for line in before.splitlines():
        if line.startswith("#"):
            assert line in after, f"comment lost: {line}"


def test_status_is_appended_and_reloads(tmp_path):
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")

    ModuleFile.load(tmp_path).set_status("cw2", grades_collected=True)

    assert load_module(tmp_path).assessment("cw2").status.grades_collected


def test_a_generated_file_keeps_the_same_guarantee_as_a_hand_written_one(tmp_path):
    """Everything init_module wrote survives byte for byte; [status] is added.

    This is the join between the two halves. A generated file is a
    hand-editable file, so it has to obey the guarantee ModuleFile.save makes
    about the author's sections -- and here the "author" is init_module.
    """
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")
    path = tmp_path / MODULE_FILENAME
    before = path.read_text(encoding="utf-8")

    ModuleFile.load(tmp_path).set_status("cw1", sheets_distributed=True)

    written = path.read_text(encoding="utf-8")
    assert written.startswith(before)
    assert written[len(before):].lstrip().startswith("[status.")


# ---------------------------------------------------------------------------
# What it refuses
# ---------------------------------------------------------------------------


def test_it_will_not_replace_an_existing_file(tmp_path):
    """That file is the module's memory. Losing it is not a small mistake."""
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")

    with pytest.raises(FileExistsError, match="overwrite=True"):
        init_module(tmp_path, "PS4002", "Something Else", "2025/26", "SOB")

    assert load_module(tmp_path).code == "PS4001"


def test_overwrite_replaces_it_when_asked(tmp_path):
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")

    init_module(
        tmp_path, "PS4002", "Something Else", "2025/26", "SOB", overwrite=True
    )

    assert load_module(tmp_path).code == "PS4002"


def test_weights_that_do_not_sum_to_100_are_refused(tmp_path):
    with pytest.raises(ValueError, match="100"):
        init_module(
            tmp_path,
            "PS4001",
            "Research Methods",
            "2025/26",
            "KOM",
            assessments=[
                dict(id="cw1", type="coursework", name="Coursework 1",
                     marks_out_of=100, weight=40),
                dict(id="cw2", type="coursework", name="Coursework 2",
                     marks_out_of=100, weight=50),
            ],
        )


def test_nothing_is_written_when_validation_fails(tmp_path):
    """Validate before writing, so a bad file never reaches the disk."""
    with pytest.raises(ValueError):
        init_module(
            tmp_path,
            "PS4001",
            "Research Methods",
            "2025/26",
            "KOM",
            assessments=[
                dict(id="cw1", type="coursework", name="Coursework 1",
                     marks_out_of=100, weight=40),
            ],
        )

    assert not (tmp_path / MODULE_FILENAME).exists()
    assert list(tmp_path.iterdir()) == [], "a temp file was left behind"


# ---------------------------------------------------------------------------
# What the caller can vary
# ---------------------------------------------------------------------------


def test_custom_assessments_are_written(tmp_path):
    module = init_module(
        tmp_path,
        "PS4002",
        "Cognition",
        "2025/26",
        "KOM",
        assessments=[
            dict(id="exam", type="exam", name="Exam", marks_out_of=100, weight=70),
            dict(id="cw1", type="coursework", name="Coursework 1",
                 marks_out_of=50, weight=30, graders=["KOM", "SOB"]),
        ],
    ).module

    assert [a.id for a in module.assessments] == ["exam", "cw1"]
    assert [g.initials for g in module.assessment("cw1").graders] == ["KOM", "SOB"]
    assert module.grade_sheet_columns == [
        "Exam (100)",
        "Exam (70)",
        "Coursework 1 (50)",
        "Coursework 1 (30)",
    ]


def test_a_leader_with_detail_becomes_a_sub_table(tmp_path):
    init_module(
        tmp_path,
        "PS4001",
        "Research Methods",
        "2025/26",
        {"initials": "KOM", "name": "Kevin O Malley", "email": "kevin@ul.ie"},
    )

    text = (tmp_path / MODULE_FILENAME).read_text(encoding="utf-8")
    assert "[module.leader]" in text

    leader = load_module(tmp_path).leader
    assert leader.initials == "KOM"
    assert leader.email == "kevin@ul.ie"


def test_bare_initials_stay_bare(tmp_path):
    """The shorthand a hand-written file uses is the shorthand we write."""
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")

    text = (tmp_path / MODULE_FILENAME).read_text(encoding="utf-8")

    assert 'leader = "KOM"' in text
    assert "[module.leader]" not in text


def test_a_scalar_person_is_not_swallowed_by_a_preceding_sub_table(tmp_path):
    """The bug: once [module.leader] is open, a bare key after it is the
    leader's, not the module's.

    A detailed leader becomes [module.leader]; a moderator given as bare
    initials was then written after that heading, so TOML parsed it as
    Person(initials="KOM", name="...", internal_moderator="SOB"), pydantic
    ignored the unknown key, and the moderator vanished with no error.
    Scalars must all be written before any sub-table.
    """
    init_module(
        tmp_path,
        "PS4001",
        "Research Methods",
        "2025/26",
        {"initials": "KOM", "name": "Kevin O Malley"},   # -> a sub-table
        internal_moderator="SOB",                        # -> a scalar
    )

    module = load_module(tmp_path)

    assert module.leader.initials == "KOM"
    assert module.leader.name == "Kevin O Malley"
    assert module.internal_moderator is not None, (
        "the moderator was swallowed by [module.leader]"
    )
    assert module.internal_moderator.initials == "SOB"


def test_both_people_can_carry_detail(tmp_path):
    init_module(
        tmp_path,
        "PS4001",
        "Research Methods",
        "2025/26",
        {"initials": "KOM", "name": "Kevin O Malley"},
        internal_moderator={"initials": "SOB", "email": "s.o.b@ul.ie"},
    )

    module = load_module(tmp_path)

    assert module.leader.name == "Kevin O Malley"
    assert module.internal_moderator.email == "s.o.b@ul.ie"


def test_an_internal_moderator_is_optional(tmp_path):
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")
    assert load_module(tmp_path).internal_moderator is None

    init_module(
        tmp_path, "PS4001", "Research Methods", "2025/26", "KOM",
        internal_moderator="SOB", overwrite=True,
    )
    assert load_module(tmp_path).internal_moderator.initials == "SOB"


def test_paths_can_be_set(tmp_path):
    init_module(
        tmp_path, "PS4001", "Research Methods", "2025/26", "KOM",
        paths={"classlist": "classlist.csv", "departmental_sheet": "grades.xlsx"},
    )

    module = load_module(tmp_path)

    assert module.paths.classlist == "classlist.csv"
    assert module.classlist_path == (tmp_path / "classlist.csv").resolve()


def test_paths_stay_relative(tmp_path):
    """Nothing absolute is stored -- these files live under OneDrive."""
    init_module(
        tmp_path, "PS4001", "Research Methods", "2025/26", "KOM",
        paths={"classlist": "classlist.csv"},
    )

    text = (tmp_path / MODULE_FILENAME).read_text(encoding="utf-8")

    assert str(tmp_path) not in text
