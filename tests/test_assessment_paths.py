#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""How an assessment finds its own folders.

An Assessment holds relative *names* -- "cw1", "submissions" -- because
module.toml stores nothing absolute: these modules live under OneDrive, where
the absolute path differs per machine. Turning those names into paths needs
the module root, which the Assessment does not otherwise know, so Module
binds it on load.

That binding is the thing these tests protect. If it silently stops
happening, every path property raises; if it silently starts being
serialised, an absolute path leaks into a file that is deliberately all
relative.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl

import pytest

from grader_helper.models import (
    MODULE_FILENAME,
    Assessment,
    ModuleFile,
    init_module,
    load_module,
)


@pytest.fixture
def module(tmp_path):
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")
    return load_module(tmp_path)


# ---------------------------------------------------------------------------
# The fields
# ---------------------------------------------------------------------------


def test_the_sub_directories_have_defaults(module):
    assessment = module.assessment("cw1")

    assert assessment.submissions == "submissions"
    assert assessment.grading_output == "grading_output"
    # `folder` is left unset by the starter file and falls back to the id,
    # so the common case needs no line in module.toml at all.
    assert assessment.folder is None
    assert assessment.folder_path.name == "cw1"


def test_a_file_written_before_these_fields_existed_still_loads(tmp_path):
    """Backwards compatibility, stated as the thing that must not break.

    Every new field has a default, so a module.toml that predates them is
    still valid -- it just gets the conventional layout.
    """
    (tmp_path / MODULE_FILENAME).write_text(
        'schema_version = 1\n'
        '\n'
        '[module]\n'
        'code = "PS4001"\n'
        'name = "Research Methods"\n'
        'year = "2025/26"\n'
        'leader = "KOM"\n'
        '\n'
        '[[assessment]]\n'
        'id = "cw1"\n'
        'type = "coursework"\n'
        'name = "Coursework 1"\n'
        'marks_out_of = 100\n'
        'weight = 100\n',
        encoding="utf-8",
    )

    assessment = load_module(tmp_path).assessment("cw1")

    assert assessment.submissions == "submissions"
    assert assessment.submissions_path == tmp_path / "assessments" / "cw1" / "submissions"


def test_the_folder_defaults_to_the_assessment_id(tmp_path):
    init_module(
        tmp_path, "PS4001", "Research Methods", "2025/26", "KOM",
        assessments=[dict(id="essay", type="coursework", name="Essay",
                          marks_out_of=100, weight=100)],
    )

    assert load_module(tmp_path).assessment("essay").folder_path.name == "essay"


# ---------------------------------------------------------------------------
# The paths
# ---------------------------------------------------------------------------


def test_each_path_lands_where_the_layout_says(module, tmp_path):
    """Asserted against the literal tree, not against the same join again."""
    assessment = module.assessment("cw1")
    cw1 = tmp_path / "assessments" / "cw1"

    assert assessment.folder_path == cw1
    assert assessment.submissions_path == cw1 / "submissions"
    assert assessment.grading_output_path == cw1 / "grading_output"


def test_the_argument_was_the_parent_and_the_result_is_the_child(module, tmp_path):
    """The distinction that made the old method form confusing.

    folder_path is *this assessment's* folder, sitting inside the assessments
    directory -- not the assessments directory itself.
    """
    assessment = module.assessment("cw1")

    assert assessment.folder_path != module.assessments_dir
    assert assessment.folder_path.parent == module.assessments_dir


def test_a_rubric_sits_inside_the_assessments_own_folder(tmp_path):
    init_module(
        tmp_path, "PS4001", "Research Methods", "2025/26", "KOM",
        assessments=[dict(id="cw1", type="coursework", name="Coursework 1",
                          marks_out_of=100, weight=100,
                          rubric="Feedback sheet BLANK.xlsx")],
    )

    assessment = load_module(tmp_path).assessment("cw1")

    assert assessment.rubric_path == assessment.folder_path / "Feedback sheet BLANK.xlsx"


def test_no_rubric_means_no_rubric_path(module):
    """The starter file names no rubric, so there is no path to give."""
    assert module.assessment("cw1").rubric_path is None


def test_directories_lists_everything_the_assessment_needs(module, tmp_path):
    assessment = module.assessment("cw1")

    assert set(assessment.directories) == {
        assessment.folder_path,
        assessment.submissions_path,
        assessment.grading_output_path,
    }


# ---------------------------------------------------------------------------
# The binding
# ---------------------------------------------------------------------------


def test_an_unbound_assessment_refuses_rather_than_guessing(tmp_path):
    """A wrong path is worse than an error.

    An Assessment built on its own has no idea where the module lives, so it
    says so instead of returning something plausible relative to the cwd.
    """
    loose = Assessment(
        id="cw1", type="coursework", name="Coursework 1",
        marks_out_of=100, weight=100,
    )

    with pytest.raises(ValueError, match="does not know where it lives"):
        loose.folder_path


def test_binding_survives_a_reload(tmp_path):
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")

    reloaded = load_module(tmp_path).assessment("cw2")

    assert reloaded.submissions_path.is_absolute()
    assert reloaded.submissions_path.parent.name == "cw2"


def test_the_bound_root_is_not_serialised(tmp_path):
    """Nothing absolute leaves the model. This is what PrivateAttr buys.

    model_dump is the exposed surface -- `module.model_dump_json()` is how you
    inspect a module in a notebook, and it is what any future export would go
    through. A bound root showing up there puts one machine's absolute path
    into whatever it is pasted into.

    Note the file itself is protected by a different rule: ModuleFile.save
    only updates keys already present, so a new field could not be appended
    to [[assessment]] anyway. Asserting on the file alone therefore passes
    even when the root *is* a serialisable field -- which is exactly what this
    test caught.
    """
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")
    module = load_module(tmp_path)

    dumped = module.model_dump()
    for assessment in dumped["assessments"]:
        assert "assessments_root" not in assessment
        assert "_assessments_root" not in assessment

    assert str(tmp_path) not in module.model_dump_json()


def test_the_authors_file_is_untouched_by_a_status_save(tmp_path):
    """The separate guarantee: only [status] is ever appended."""
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")
    path = tmp_path / MODULE_FILENAME
    before = path.read_text(encoding="utf-8")

    ModuleFile.load(tmp_path).set_status("cw1", graders_allocated=True)

    written = path.read_text(encoding="utf-8")
    assert written.startswith(before)
    assert str(tmp_path) not in written


# ---------------------------------------------------------------------------
# Creating the layout
# ---------------------------------------------------------------------------


def test_init_module_creates_the_whole_tree(tmp_path):
    init_module(tmp_path, "PS4001", "Research Methods", "2025/26", "KOM")

    module = load_module(tmp_path)

    assert module.assessments_dir.is_dir()
    for assessment in module.assessments:
        for directory in assessment.directories:
            assert directory.is_dir(), directory


def test_create_dirs_false_writes_only_the_file(tmp_path):
    init_module(
        tmp_path, "PS4001", "Research Methods", "2025/26", "KOM",
        create_dirs=False,
    )

    assert (tmp_path / MODULE_FILENAME).exists()
    assert not (tmp_path / "assessments").exists()


def test_nothing_is_created_when_the_module_is_invalid(tmp_path):
    """Validation runs before anything touches the disk."""
    with pytest.raises(ValueError, match="100"):
        init_module(
            tmp_path, "PS4001", "Research Methods", "2025/26", "KOM",
            assessments=[dict(id="cw1", type="coursework", name="Coursework 1",
                              marks_out_of=100, weight=40)],
        )

    assert list(tmp_path.iterdir()) == []
