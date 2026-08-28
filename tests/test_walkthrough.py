#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The walkthrough notebook must actually run.

`docs/running-locally.md` has described the walkthrough as "already verified
end to end" since it was written, and that was true when someone last ran
it by hand. This makes it a fact the suite checks: `marimo.App.run()`
executes every cell and raises whatever a cell raises, so a library change
that breaks the notebook fails here rather than in front of a colleague.

The notebook is driven into `tmp_path` through `GRADER_HELPER_SCRATCH`,
which exists for exactly this. One test, not several, because running it
builds a whole module on disk and there is no reason to do that twice.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import importlib.util
import sys

import pytest

pytest.importorskip("marimo", reason="marimo is a dev dependency")


@pytest.fixture
def walkthrough(tmp_path, monkeypatch, repo_root):
    """Run every cell of the notebook, and return what it defined."""
    monkeypatch.setenv("GRADER_HELPER_SCRATCH", str(tmp_path))
    # The notebook does sys.path.insert(0, "tests"), which is relative to the
    # working directory -- the same requirement running-locally.md gives a
    # reader ("run marimo edit from the repo root").
    monkeypatch.chdir(repo_root)
    # And the repo root ahead of whatever else is on the path, which is what
    # running from there gives you.
    monkeypatch.syspath_prepend(str(repo_root))

    # By the time any test runs, `grader_helper` is already in sys.modules,
    # and in a bare `pytest tests/test_walkthrough.py` it is bound to the
    # repo directory's shim __init__.py rather than to the package -- the
    # repo directory is itself called grader_helper, and its parent is on
    # sys.path. The shim star-re-exports the public API, so
    # `from grader_helper import catch_grades` still works and the breakage
    # is invisible until something imports a *submodule*: fake_module's
    # `from grader_helper.dataframe_operations import ...`, which the shim
    # has no path for.
    #
    # Dropping the binding makes the notebook import the real package, the
    # way it does for someone running marimo from the repo root. delitem
    # rather than `del` so it is put back afterwards and the rest of the
    # session is unaffected. test_import.py guards the same hazard, but in a
    # subprocess, which is why it does not catch this one.
    for name in [
        n for n in sys.modules
        if n == "grader_helper" or n.startswith("grader_helper.")
    ]:
        monkeypatch.delitem(sys.modules, name)

    path = repo_root / "notebooks" / "grading_walkthrough.py"
    spec = importlib.util.spec_from_file_location("grading_walkthrough", path)
    notebook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(notebook)

    _, definitions = notebook.app.run()
    return definitions


def test_the_walkthrough_runs_and_collects_the_quizzes(walkthrough):
    """One assertion per thing a reader is being shown.

    The marks are the load-bearing one: `fake_module` builds the eleven
    exports backwards from the mark each student should end up with, so
    matching that column means the notebook read the exports, applied the
    module's own rules and reconciled against the class list -- not merely
    that it ran without raising.
    """
    fake = walkthrough["FAKE"]
    quizzes = walkthrough["A3"]
    marks = walkthrough["quiz_marks"]

    # The module built with quizzes rather than the MCQ.
    assert [a.id for a in walkthrough["MODULE"].assessments] == [
        "cw1", "cw2", "quizzes",
    ]
    assert quizzes.raw_column == "Quizzes (10)"

    # Read off the file, not passed in by the notebook.
    assert (quizzes.pass_mark, quizzes.free_passes) == (80.0, 1)

    collected = marks.set_index("Student ID")["Quizzes (10)"]
    assert collected.to_dict() == (
        fake.expected.set_index("Student ID")["mcq"].to_dict()
    )

    # The two edges the notebook shows by name.
    assert collected["23304309"] == 0, "the non-participant must not be given a free pass"
    assert collected["23304308"] == 10, "nine passes plus the free pass, capped"

    # And the progress each section records. All three, because cw1 went
    # without a record_progress cell until someone ran the notebook to the
    # end and read its own status output back.
    recorded = walkthrough["ModuleFile"].load(fake.root).module
    assert {
        a.id: a.status.grades_collected for a in recorded.assessments
    } == {"cw1": True, "cw2": True, "quizzes": True}
