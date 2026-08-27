#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Reading and writing module.toml.

The file is hand-edited as well as machine-written, so the guarantee that
matters is that a save leaves the author's sections byte-identical and
appends only the tool's own [status] section.
"""

import pathlib as pl

import pytest

from grader_helper.models import MODULE_FILENAME, Module, ModuleFile, load_module

EXAMPLE = """\
schema_version = 1

# ---------------------------------------------------------------------------
# PS4001 -- edit by hand; grader_helper preserves your comments.
# ---------------------------------------------------------------------------

[module]
code = "PS4001"
name = "Advanced Research Methods"
year = "2025/26"

[module.leader]
initials = "KOM"
name = "Kevin O Malley"
email = "kevin.omalley@ul.ie"

[paths]
assessments = "assessments"
classlist = "classlist.csv"        # csv or xlsx, whichever you exported

# Weights must sum to 100 -- checked on load.
[[assessment]]
id = "cw1"
type = "coursework"
name = "Coursework 1"
marks_out_of = 100
weight = 40
graders = ["KOM", "SOB"]
grade_cell = "D30"       # where the mark sits in the feedback sheet

[[assessment]]
id = "cw2"
type = "coursework"
name = "Coursework 2"
marks_out_of = 100
weight = 50
graders = ["KOM"]

# Ten weekly quizzes, each pass worth 1%. Marked out of 10, worth 10, so it
# needs only one column in the grade sheet.
[[assessment]]
id = "quizzes"
type = "quiz"
name = "Quizzes"
marks_out_of = 10
weight = 10
pass_mark = 80.0        # strictly above: exactly 80 has failed
free_passes = 1         # eleven quizzes are set, so one may be dropped
"""


@pytest.fixture
def module_dir(tmp_path):
    (tmp_path / MODULE_FILENAME).write_text(EXAMPLE, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def test_load_from_a_directory(module_dir):
    module = load_module(module_dir)
    assert module.code == "PS4001"
    assert module.leader.name == "Kevin O Malley"


def test_load_from_the_file_itself(module_dir):
    module = load_module(module_dir / MODULE_FILENAME)
    assert module.code == "PS4001"


def test_root_is_the_files_own_directory(module_dir):
    """Nothing absolute is stored; the root is where the file sits."""
    module = load_module(module_dir)
    assert module.root == module_dir
    assert module.classlist_path == (module_dir / "classlist.csv").resolve()


def test_the_module_is_portable(tmp_path, module_dir):
    """Moving the folder moves the module -- no absolute paths inside."""
    moved = tmp_path / "somewhere-else"
    moved.mkdir()
    (moved / MODULE_FILENAME).write_text(EXAMPLE, encoding="utf-8")

    module = load_module(moved)

    assert module.root == moved
    assert module.classlist_path == (moved / "classlist.csv").resolve()


def test_grade_sheet_columns_come_from_the_file(module_dir):
    assert load_module(module_dir).grade_sheet_columns == [
        "Coursework 1 (100)",
        "Coursework 1 (40)",
        "Coursework 2 (100)",
        "Coursework 2 (50)",
        "Quizzes (10)",
    ]


def test_quiz_rules_are_read_from_the_file(module_dir):
    """The module records how its quizzes are collected, not the script."""
    quizzes = load_module(module_dir).assessment("quizzes")

    assert quizzes.pass_mark == 80.0
    assert quizzes.free_passes == 1


def test_a_quiz_without_rules_still_loads(module_dir):
    """Files written before the keys existed must keep loading.

    Requiring pass_mark at load time would stop an existing module.toml
    opening at all, which is a heavy price for a rule that is only needed
    at the moment marks are collected. It is enforced there instead.
    """
    path = module_dir / MODULE_FILENAME
    path.write_text(
        EXAMPLE.replace("pass_mark = 80.0        # strictly above: exactly 80 has failed\n", "")
        .replace("free_passes = 1         # eleven quizzes are set, so one may be dropped\n", ""),
        encoding="utf-8",
    )

    quizzes = load_module(module_dir).assessment("quizzes")

    assert quizzes.pass_mark is None
    assert quizzes.free_passes == 0


def test_graders_read_from_shorthand(module_dir):
    module = load_module(module_dir)
    assert [g.initials for g in module.assessment("cw1").graders] == ["KOM", "SOB"]


def test_a_missing_file_says_how_to_make_one(tmp_path):
    with pytest.raises(FileNotFoundError, match="init_module"):
        load_module(tmp_path)


def test_a_newer_schema_is_refused(module_dir):
    path = module_dir / MODULE_FILENAME
    path.write_text(
        EXAMPLE.replace("schema_version = 1", "schema_version = 99"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Upgrade grader_helper"):
        load_module(module_dir)


def test_bad_weights_are_caught_on_load(module_dir):
    path = module_dir / MODULE_FILENAME
    path.write_text(EXAMPLE.replace("weight = 40", "weight = 45"), encoding="utf-8")
    with pytest.raises(Exception, match="sum to"):
        load_module(module_dir)


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------


def test_saving_leaves_the_authors_sections_untouched(module_dir):
    """The guarantee. Everything the author wrote survives byte for byte."""
    mf = ModuleFile.load(module_dir)
    mf.set_status("cw1", sheets_distributed=True)

    written = (module_dir / MODULE_FILENAME).read_text(encoding="utf-8")

    assert written.startswith(EXAMPLE)
    assert written[len(EXAMPLE):].lstrip().startswith("[status.")


def test_comments_survive(module_dir):
    mf = ModuleFile.load(module_dir)
    mf.set_status("cw1", sheets_distributed=True, graders_allocated=True)

    written = (module_dir / MODULE_FILENAME).read_text(encoding="utf-8")

    for comment in (
        "# PS4001 -- edit by hand; grader_helper preserves your comments.",
        "# Weights must sum to 100 -- checked on load.",
        "# Ten weekly quizzes, each pass worth 1%. Marked out of 10, worth 10, so it",
        "# csv or xlsx, whichever you exported",
        "# where the mark sits in the feedback sheet",
    ):
        assert comment in written, f"lost: {comment}"


def test_grader_shorthand_is_not_rewritten(module_dir):
    mf = ModuleFile.load(module_dir)
    mf.set_status("cw1", sheets_distributed=True)

    written = (module_dir / MODULE_FILENAME).read_text(encoding="utf-8")

    assert 'graders = ["KOM", "SOB"]' in written
    assert "[[assessment.graders]]" not in written


def test_status_survives_a_reload(module_dir):
    ModuleFile.load(module_dir).set_status(
        "cw1", sheets_distributed=True, graders_allocated=True
    )
    ModuleFile.load(module_dir).set_status("quizzes", grades_collected=True)

    module = load_module(module_dir)

    cw1 = module.assessment("cw1").status
    assert cw1.sheets_distributed and cw1.graders_allocated
    assert not cw1.grades_collected
    assert module.assessment("quizzes").status.grades_collected


def test_repeated_saves_are_stable(module_dir):
    """Saving twice must not keep growing or reshuffling the file."""
    ModuleFile.load(module_dir).set_status("cw1", sheets_distributed=True)
    once = (module_dir / MODULE_FILENAME).read_text(encoding="utf-8")

    ModuleFile.load(module_dir).set_status("cw1", sheets_distributed=True)
    twice = (module_dir / MODULE_FILENAME).read_text(encoding="utf-8")

    assert once == twice


def test_an_unknown_status_flag_is_refused(module_dir):
    mf = ModuleFile.load(module_dir)
    with pytest.raises(AttributeError, match="Known flags"):
        mf.set_status("cw1", finished=True)


def test_no_temp_files_are_left_behind(module_dir):
    ModuleFile.load(module_dir).set_status("cw1", sheets_distributed=True)
    leftovers = [p.name for p in module_dir.iterdir() if p.name != MODULE_FILENAME]
    assert leftovers == []


def test_a_failed_write_leaves_the_original_intact(module_dir, monkeypatch):
    """The file is the module's memory; a broken save must not eat it."""
    import grader_helper.models.module_file as mod

    original = (module_dir / MODULE_FILENAME).read_text(encoding="utf-8")

    def boom(*args, **kwargs):
        raise OSError("disk full")

    mf = ModuleFile.load(module_dir)
    monkeypatch.setattr(mod.os, "replace", boom)

    with pytest.raises(OSError):
        mf.save()

    assert (module_dir / MODULE_FILENAME).read_text(encoding="utf-8") == original
    assert [p.name for p in module_dir.iterdir()] == [MODULE_FILENAME]
