#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The dashboard notebook must run, and must offer the right thing.

Pointing at a folder has four answers and the notebook shows a different
face for each, so what is checked here is which face: a module folder is
displayed, an empty one is offered setup, and a folder whose module.toml
will not load is offered nothing at all -- setting it up again would mean
overwriting the module's memory to fix a typo.

`marimo.App.run()` executes every cell and raises whatever a cell raises,
which is the other half of the point: these cells run on every click, and a
folder the reader picked by accident must not be able to crash the page.

A test cannot click a file browser, so the notebook takes its folder from
`GRADER_HELPER_MODULE` when nothing is selected. That is a real feature --
it is how you launch pointed at a module -- not a hook that exists only
here.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import importlib.util
import pathlib as pl
import re
import sys
from dataclasses import dataclass

import pytest

pytest.importorskip("marimo", reason="marimo is a dev dependency")

from grader_helper.models import (  # noqa: E402 -- after the skip
    MODULE_FILENAME,
    FolderState,
    ModuleFile,
    init_module,
    load_module,
)


@dataclass(frozen=True)
class Ran:
    """What one run of the notebook produced."""

    #: Every name its cells defined.
    names: dict

    #: The page, as the rendered HTML of every cell output. Checked as well
    #: as the names because a cell can define exactly the right values and
    #: still render them wrongly -- mo.md dedents by the common leading
    #: whitespace, so a multi-line value interpolated into an indented block
    #: turns the headings after it into paragraphs, silently.
    page: str


@pytest.fixture
def run_dashboard(monkeypatch, repo_root):
    """Run every cell of the dashboard against a folder, and return what it made."""

    def _run(folder: pl.Path) -> Ran:
        monkeypatch.setenv("GRADER_HELPER_MODULE", str(folder))
        monkeypatch.chdir(repo_root)
        monkeypatch.syspath_prepend(str(repo_root))

        # The repo directory is itself called grader_helper and holds a shim
        # __init__.py, so an already-imported `grader_helper` may be bound to
        # the shim rather than the package -- which star-re-exports the public
        # API but has no path for a submodule like `grader_helper.models`.
        # Dropping the binding makes the notebook import the real package,
        # the way it does for someone running marimo from the repo root.
        # test_walkthrough.py guards the same hazard for the same reason.
        for name in [
            n for n in sys.modules
            if n == "grader_helper" or n.startswith("grader_helper.")
        ]:
            monkeypatch.delitem(sys.modules, name)

        path = repo_root / "notebooks" / "module_dashboard.py"
        spec = importlib.util.spec_from_file_location("module_dashboard", path)
        notebook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(notebook)

        outputs, definitions = notebook.app.run()
        page = "".join(getattr(output, "text", "") for output in outputs)
        return Ran(names=definitions, page=page)

    return _run


# ---------------------------------------------------------------------------
# The three faces
# ---------------------------------------------------------------------------


def test_a_module_folder_is_displayed_not_offered_setup(run_dashboard, tmp_path):
    folder = tmp_path / "PS4034"
    folder.mkdir()
    init_module(folder, "PS4034", "Research Methods", "2025/26", "KOM")

    shown = run_dashboard(folder)

    assert shown.names["loaded"]
    assert not shown.names["offer"]
    assert shown.names["found"].module.code == "PS4034"


def test_an_empty_folder_is_offered_setup(run_dashboard, tmp_path):
    folder = tmp_path / "PS4034"
    folder.mkdir()

    shown = run_dashboard(folder)

    assert shown.names["offer"]
    assert not shown.names["loaded"]


def test_a_broken_module_file_is_offered_nothing(run_dashboard, tmp_path):
    """The one that protects a module's memory.

    A weight typo is fixed by editing the weight. Offering setup here would
    mean init_module with overwrite=True, and that file holds the graders,
    the quiz rules and every status flag recorded so far.
    """
    folder = tmp_path / "PS4034"
    folder.mkdir()
    (folder / MODULE_FILENAME).write_text(
        'schema_version = 1\n\n[module]\ncode = "PS4034"\nname = "RM"\n'
        'year = "2025/26"\nleader = "KOM"\n\n[[assessment]]\nid = "cw1"\n'
        'type = "coursework"\nname = "Coursework 1"\nmarks_out_of = 100\n'
        "weight = 40\n",
        encoding="utf-8",
    )

    shown = run_dashboard(folder)

    # `==`, not `is`: the fixture drops the package from sys.modules so the
    # notebook imports its own copy, and the enum member it holds is a
    # different object from this one. FolderState subclasses str precisely so
    # that comparing it by value still works.
    assert shown.names["found"].state == FolderState.UNREADABLE
    assert not shown.names["offer"]
    assert not shown.names["loaded"]


def test_a_folder_that_is_not_there_does_not_crash_the_page(run_dashboard, tmp_path):
    shown = run_dashboard(tmp_path / "no-such-module")

    assert shown.names["found"].state == FolderState.MISSING
    assert not shown.names["offer"]


# ---------------------------------------------------------------------------
# What the form would write
# ---------------------------------------------------------------------------


def test_the_form_defaults_make_a_module_that_loads(run_dashboard, tmp_path):
    """The form's own defaults, put through the function the button calls.

    A test cannot press the button, so this checks the thing the button
    would hand over: the specs the assessment rows produce untouched. They
    have to describe a module that loads, for the same reason the starter
    file does -- a first module you must fix before it will open is a worse
    starting point than none.
    """
    empty = tmp_path / "PS4034"
    empty.mkdir()

    shown = run_dashboard(empty)

    assert shown.names["weights"] == 100
    init_module(
        empty, "PS4034", "Research Methods", "2025/26", "KOM",
        assessments=shown.names["specs"],
    )
    written = load_module(empty)

    assert [a.id for a in written.assessments] == ["cw1", "cw2", "mcq"]
    assert sum(a.weight for a in written.assessments) == 100


def test_the_defaults_ask_for_no_collection_rules(run_dashboard, tmp_path):
    """Every starter row is marked by a human, so none is collected.

    A pass mark that arrives by default is the bad case: an MCQ carrying
    one is scored as a single quiz passed -- worth one mark -- rather than
    read straight off the export.
    """
    folder = tmp_path / "PS4034"
    folder.mkdir()

    shown = run_dashboard(folder)

    for spec in shown.names["specs"]:
        assert not {"pass_mark", "free_passes"} & spec.keys(), spec


def test_the_rules_are_written_when_the_row_is_ticked(run_dashboard, tmp_path):
    """Ticked or not, not the type.

    A test cannot tick a checkbox, so this drives the notebook's own row
    conversion with both answers. Which is also the distinction being
    guarded: an MCQ may be collected from Brightspace or marked by hand, and
    its type does not say which.
    """
    folder = tmp_path / "PS4034"
    folder.mkdir()

    ran = run_dashboard(folder)
    spec_for = ran.names["assessment_spec"]
    # Built from a real form row rather than a dict written out here, so that
    # a field added to the form does not quietly go untested -- and does not
    # break this with a KeyError either.
    row = {
        **ran.names["rows"].value[0],
        "id": "quizzes", "type": "quiz", "name": "Quizzes",
        "marks_out_of": 10, "weight": 10, "pass_mark": 80, "free_passes": 1,
    }

    ticked = spec_for({**row, "collected": True})
    unticked = spec_for({**row, "collected": False})

    assert (ticked["pass_mark"], ticked["free_passes"]) == (80, 1)
    assert not {"pass_mark", "free_passes"} & unticked.keys()


def test_a_ticked_row_makes_a_module_that_collects_its_quizzes(run_dashboard, tmp_path):
    """End of the path: a ticked row, written, read back off the disk."""
    folder = tmp_path / "PS4034"
    folder.mkdir()

    ran = run_dashboard(folder)
    spec_for = ran.names["assessment_spec"]
    blank = ran.names["rows"].value[0]
    specs = [
        spec_for({**blank, "id": "cw1", "type": "coursework",
                  "name": "Coursework 1", "marks_out_of": 100, "weight": 90,
                  "collected": False}),
        spec_for({**blank, "id": "quizzes", "type": "quiz", "name": "Quizzes",
                  "marks_out_of": 10, "weight": 10, "collected": True,
                  "pass_mark": 80, "free_passes": 1}),
    ]
    init_module(folder, "PS4034", "Research Methods", "2025/26", "KOM",
                assessments=specs)

    quizzes = load_module(folder).assessment("quizzes")

    assert (quizzes.pass_mark, quizzes.free_passes) == (80.0, 1)
    assert quizzes.raw_column == "Quizzes (10)"


# ---------------------------------------------------------------------------
# What the page actually renders
# ---------------------------------------------------------------------------


def test_the_module_page_has_its_sections(run_dashboard, tmp_path):
    """Headings, not paragraphs that begin with hashes.

    `mo.md` dedents a block by its common leading whitespace, so a
    multi-line value interpolated at column zero into an indented block
    leaves every following line over-indented -- and markdown then renders
    the headings and tables as plain text. It fails silently and only in the
    browser, which is why it is checked here.
    """
    folder = tmp_path / "PS4034"
    folder.mkdir()
    init_module(folder, "PS4034", "Research Methods", "2025/26", "KOM")

    page = run_dashboard(folder).page

    # Sliced, because the summary is the first thing rendered after the
    # folder report and the step sections below add headings of their own.
    expected = [
        "PS4034 — Research Methods",
        "Assessment",
        "Marking setup",
        "Progress",
        "Produced once for the module",
        "Files",
    ]
    headings = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", page)

    assert headings[: len(expected)] == expected


def test_written_is_shown_apart_from_sent(run_dashboard, tmp_path):
    """The split the status model is built around.

    The code can see that it wrote the departmental sheet. Whether the sheet
    reached the department is in somebody's head, so the page must not let
    the first stand for the second.
    """
    folder = tmp_path / "PS4034"
    folder.mkdir()
    init_module(folder, "PS4034", "Research Methods", "2025/26", "KOM")
    handle = ModuleFile.load(folder)
    handle.module.status.departmental_sheet_written = True
    handle.save()

    page = run_dashboard(folder).page
    row = re.search(
        r"<td>departmental sheet</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>", page
    )

    assert row.groups() == ("yes", "-")


# ---------------------------------------------------------------------------
# Set up here, marked later
# ---------------------------------------------------------------------------


def test_a_module_set_up_here_is_ready_to_be_marked(run_dashboard, tmp_path):
    """The point of the form: no hand-editing before the first real step.

    Allocation needs the graders, distribution needs the blank feedback
    sheet, and catching the marks needs the cell they land in. A module that
    has to be opened in a text editor before any of that runs is a setup
    form that did not finish the job.
    """
    folder = tmp_path / "PS4034"
    folder.mkdir()

    ran = run_dashboard(folder)
    blank = ran.names["rows"].value[0]
    specs = [
        ran.names["assessment_spec"](
            {
                **blank,
                "id": "cw1", "type": "coursework", "name": "Coursework 1",
                "marks_out_of": 100, "weight": 100, "collected": False,
                # Lower case and loosely spaced, the way it gets typed.
                "graders": " kom ,sob ",
                "rubric": "Feedback sheet.xlsx",
                "grade_cell": "B12",
            }
        )
    ]
    init_module(folder, "PS4034", "Research Methods", "2025/26", "KOM",
                assessments=specs)

    cw1 = load_module(folder).assessment("cw1")

    assert [g.initials for g in cw1.graders] == ["KOM", "SOB"]
    assert cw1.grade_cell == "B12"
    assert cw1.rubric_path == folder / "assessments" / "cw1" / "Feedback sheet.xlsx"


def test_what_was_left_blank_is_left_out(run_dashboard, tmp_path):
    """An absent key is a question not yet answered.

    `graders = []` is a different claim -- it says nobody marks this -- and
    writing it for a form field nobody filled in would put an answer in the
    file that no one gave.
    """
    folder = tmp_path / "PS4034"
    folder.mkdir()

    shown = run_dashboard(folder)

    for spec in shown.names["specs"]:
        assert not {"graders", "rubric", "grade_cell"} & spec.keys(), spec

    init_module(folder, "PS4034", "Research Methods", "2025/26", "KOM",
                assessments=shown.names["specs"])
    written = (folder / MODULE_FILENAME).read_text(encoding="utf-8")

    assert "graders" not in written


def test_the_page_names_what_marking_still_needs(run_dashboard, tmp_path):
    """Discovered on the page, not at the first click.

    Allocation needs graders, distribution needs the blank sheet, and
    catching the marks needs the cell. A module missing any of them is not
    markable, and finding that out from a traceback halfway through a step
    is worse than being told before starting.
    """
    folder = tmp_path / "PS4034"
    folder.mkdir()

    ran = run_dashboard(folder)
    blank = ran.names["rows"].value[0]
    spec_for = ran.names["assessment_spec"]
    init_module(
        folder, "PS4034", "Research Methods", "2025/26", "KOM",
        assessments=[
            spec_for({**blank, "id": "cw1", "type": "coursework",
                      "name": "Coursework 1", "marks_out_of": 100, "weight": 60,
                      "collected": False, "graders": "KOM, SOB",
                      "rubric": "Feedback sheet.xlsx", "grade_cell": "B12"}),
            spec_for({**blank, "id": "cw2", "type": "coursework",
                      "name": "Coursework 2", "marks_out_of": 100, "weight": 30,
                      "collected": False, "graders": "KOM"}),
            spec_for({**blank, "id": "quizzes", "type": "quiz", "name": "Quizzes",
                      "marks_out_of": 10, "weight": 10, "collected": True,
                      "pass_mark": 80, "free_passes": 1}),
        ],
    )

    page = run_dashboard(folder).page

    # cw2 is named, with both of the things it is short of.
    assert "cw2" in page and "no feedback sheet or mark cell" in page
    # cw1 is complete, and the quizzes need none of it -- nobody marks a quiz.
    assert "cw1</code> has no" not in page
    assert "quizzes</code> has no" not in page
    assert "collected from Brightspace" in page
