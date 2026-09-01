#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Driving a whole assessment from the app's own buttons.

The dashboard's steps are functions rather than code inside a button guard
precisely so this can exist: a test cannot click, but it can call exactly
what a click calls. So this runs a coursework the way a module leader
does -- allocate, distribute, wait for the marking, collect and reconcile,
rename the folders back -- against a real module on disk, and then collects
a term of quizzes.

What it is really checking is that the app is not merely a page that renders.
Each step has to leave the right artefacts behind, and the status it records
has to survive a reload, because the leader closes the page between the
distribution and the marks coming back.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import importlib.util
import shutil
import sys

import pandas as pd
import pytest

pytest.importorskip("marimo", reason="marimo is a dev dependency")
from openpyxl import load_workbook  # noqa: E402

from grader_helper import extract_studentid_grade  # noqa: E402
from grader_helper.models import ModuleFile  # noqa: E402

sys.path.insert(0, "tests")


@pytest.fixture
def module_on_disk(tmp_path, repo_root):
    """A whole fake module, before any of the work has been done."""
    sys.path.insert(0, str(repo_root / "tests"))
    from fake_module import make_fake_module

    root = tmp_path / "PS4001"
    make_fake_module(root, distributed=False, marked=False, quizzes=True)
    return root


@pytest.fixture
def dashboard(monkeypatch, repo_root):
    """The notebook, run against a folder, returning the names it defined."""

    def _run(folder):
        monkeypatch.setenv("GRADER_HELPER_MODULE", str(folder))
        monkeypatch.chdir(repo_root)
        monkeypatch.syspath_prepend(str(repo_root))
        for name in [
            n for n in sys.modules
            if n == "grader_helper" or n.startswith("grader_helper.")
        ]:
            monkeypatch.delitem(sys.modules, name)

        path = repo_root / "notebooks" / "module_dashboard.py"
        spec = importlib.util.spec_from_file_location("module_dashboard", path)
        notebook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(notebook)
        return notebook.app.run()[1]

    return _run


def mark_the_sheets(assessment, graders):
    """Stand in for the graders, who are the slow part of a real module.

    Two separate acts, because that is what the audit exists to compare: the
    mark is written into the feedback sheet the student receives, and then
    *copied by hand* into the grader's own workbook.
    """
    written = {}
    for index, sheet in enumerate(
        sorted(assessment.submissions_path.glob("*/Feedback sheet *.xlsx"))
    ):
        workbook = load_workbook(sheet)
        workbook.active[assessment.grade_cell] = 40 + (index * 7) % 55
        workbook.save(sheet)
        written[sheet.stem.split(" ")[-1]] = sheet

    for grader in graders:
        grader_file = assessment.grading_output_path / f"{grader}.xlsx"
        allocated = pd.read_excel(grader_file, dtype={"Student ID": str})
        marks = []
        for student in allocated["Student ID"]:
            sheet = written.get(student)
            found = (
                extract_studentid_grade(sheet, assessment.grade_cell)
                if sheet
                else None
            )
            marks.append(found[1] if found else None)
        allocated["Mark"] = marks
        allocated.to_excel(grader_file, index=False)


def test_a_coursework_runs_from_the_buttons(module_on_disk, dashboard):
    """Allocate, distribute, mark, collect, reconcile, rename back."""
    names = dashboard(module_on_disk)
    module = names["found"].module
    cw1 = module.assessment("cw1")
    class_list = names["class_list"]
    graders = [g.initials for g in cw1.graders]

    assert class_list is not None, "the class list must be read off module.toml"

    # --- 1. allocate ------------------------------------------------------
    master, workbooks, allocation = names["allocate_marking"](cw1, class_list)

    assert (cw1.folder_path / "distributed.xlsx").exists()
    assert sorted(p.stem for p in workbooks.values()) == sorted(graders)
    assert set(allocation["grader"]) <= set(graders)
    assert ModuleFile.load(module_on_disk).module.assessment(
        "cw1"
    ).status.graders_allocated, "the flag has to survive a reload of the file"

    # --- 1a. one student submitted twice ----------------------------------
    # Real cohorts do this, and nothing downstream will run until it is
    # resolved: two folders for one student cannot both be renamed for
    # marking. Which attempt counts is the leader's call, so the app asks.
    plan = names["resolve_resubmissions"](cw1, "latest")

    assert plan.removed, "the fake module has a resubmitter; it should be found"
    assert all(folder.exists() for folder in plan.removed), "a plan deletes nothing"

    names["resolve_resubmissions"](cw1, "latest", apply=True)

    assert not any(folder.exists() for folder in plan.removed)

    # --- 2. distribute ----------------------------------------------------
    distribution, log = names["distribute_sheets"](cw1, class_list)

    assert (cw1.submissions_path / "folder_rename_log.csv").exists()
    assert len(log) > 0
    assert list(cw1.submissions_path.glob("*/Feedback sheet *.xlsx"))

    # The fixture ships a `__MACOSX` folder, because unzipping on a Mac makes
    # one and a real download has whatever the leader's machine put there.
    # It is genuinely unrecognised, so the flag is withheld: a run that
    # matched every student but one has not finished, and the tick would hide
    # the one it missed.
    assert distribution.unmatched == ["__MACOSX"]
    assert not ModuleFile.load(module_on_disk).module.assessment(
        "cw1"
    ).status.sheets_distributed, "an unmatched folder must withhold the flag"

    # Clear it the way a leader would, and the same step records.
    shutil.rmtree(cw1.submissions_path / "__MACOSX")
    distribution, log = names["distribute_sheets"](cw1, class_list)

    assert not distribution.unmatched
    assert ModuleFile.load(module_on_disk).module.assessment(
        "cw1"
    ).status.sheets_distributed

    # --- the graders do their part ----------------------------------------
    mark_the_sheets(cw1, graders)

    # --- 3. collect and reconcile ----------------------------------------
    collation, audit = names["collect_marks"](cw1)

    assert (cw1.grading_output_path / "completed_grades.xlsx").exists()

    # Not `audit.agree`: a real cohort has a student who never submitted. They
    # are on the class list, so a grader was allocated them and they reach the
    # collated file with no feedback sheet to read -- which is normal, and is
    # the whole reason the kinds are told apart rather than counted.
    assert audit.transcription_slips.empty, (
        "a mark on a student's sheet differs from the one the department "
        f"would be sent: {audit.transcription_slips}"
    )
    assert audit.not_allocated.empty
    assert len(audit.not_submitted) == len(audit.disagreements)
    assert ModuleFile.load(module_on_disk).module.assessment(
        "cw1"
    ).status.grades_collected

    # --- 4. put the folders back ------------------------------------------
    renamed = sorted(p.name for p in cw1.submissions_path.iterdir() if p.is_dir())
    restoration = names["rename_back"](cw1)
    restored = sorted(p.name for p in cw1.submissions_path.iterdir() if p.is_dir())

    assert restored != renamed, "the folders were not renamed back"
    assert set(restored) == set(log["Original Name"]), (
        "they must go back to the exact name Brightspace gave, or the "
        "re-upload does not match"
    )
    assert restoration


def test_the_quizzes_run_from_their_own_button(module_on_disk, dashboard):
    """The other path: no allocation, no sheets, nothing to reconcile."""
    names = dashboard(module_on_disk)
    quizzes = names["found"].module.assessment("quizzes")

    marks = names["collect_quizzes"](quizzes, names["class_list"])

    assert len(marks) == len(names["class_list"]), (
        "every student on the class list needs a row, including those who sat "
        "no quiz -- a missing row takes a component out of a module total"
    )
    assert marks[quizzes.raw_column].between(0, quizzes.marks_out_of).all()
    assert ModuleFile.load(module_on_disk).module.assessment(
        "quizzes"
    ).status.grades_collected


def test_a_step_refuses_to_replace_what_it_already_wrote(module_on_disk, dashboard):
    """Re-running allocation is not free: it changes who marks whom.

    So it refuses unless the page's tick says otherwise, rather than quietly
    reassigning a cohort somebody has already started marking.
    """
    names = dashboard(module_on_disk)
    cw1 = names["found"].module.assessment("cw1")
    class_list = names["class_list"]

    names["allocate_marking"](cw1, class_list)

    with pytest.raises(FileExistsError):
        names["allocate_marking"](cw1, class_list)

    names["allocate_marking"](cw1, class_list, replace=True)


def test_distribution_never_replaces_a_feedback_sheet(module_on_disk, dashboard):
    """A sheet already in a student's folder may carry a mark.

    There is no tick that changes this, so running distribution twice must
    leave the marks alone rather than handing back a blank sheet.
    """
    names = dashboard(module_on_disk)
    cw1 = names["found"].module.assessment("cw1")
    class_list = names["class_list"]

    names["allocate_marking"](cw1, class_list)
    names["resolve_resubmissions"](cw1, "latest", apply=True)
    names["distribute_sheets"](cw1, class_list)
    mark_the_sheets(cw1, [g.initials for g in cw1.graders])

    sheet = sorted(cw1.submissions_path.glob("*/Feedback sheet *.xlsx"))[0]
    before = load_workbook(sheet).active[cw1.grade_cell].value

    names["distribute_sheets"](cw1, class_list)

    assert load_workbook(sheet).active[cw1.grade_cell].value == before


@pytest.fixture
def marked_module(tmp_path, repo_root):
    """A module whose marking is already done, ready to be collated.

    The departmental template is the department's own workbook, which lives
    in this repo. A real module keeps its own copy, so this puts one in the
    module folder and names it -- by editing the file directly, because
    ModuleFile.save only ever updates keys that are already there.
    """
    sys.path.insert(0, str(repo_root / "tests"))
    from fake_module import make_fake_module

    root = tmp_path / "PS4001"
    make_fake_module(root, distributed=True, marked=True, quizzes=True)

    shutil.copy(
        repo_root / "Dept grade sheet Template 2026.xlsx", root / "template.xlsx"
    )
    module_file = root / "module.toml"
    module_file.write_text(
        module_file.read_text(encoding="utf-8").replace(
            "[paths]", '[paths]\ndepartmental_template = "template.xlsx"', 1
        ),
        encoding="utf-8",
    )
    return root


def test_the_module_level_steps_run_from_the_buttons(marked_module, dashboard):
    """Collate, the departmental sheet, the moderation pack, SI's upload."""
    names = dashboard(marked_module)
    module = names["found"].module
    class_list = names["class_list"]

    # --- 5. collate -------------------------------------------------------
    marks, sheet = names["collate_the_module"](module, class_list, "feedback")

    assert len(sheet) == len(class_list), "every enrolled student reaches the sheet"
    assert "Total % Grade" in sheet.columns and "Letter Grade" in sheet.columns
    assert set(module.grade_sheet_columns) <= set(marks.columns)

    # --- 6. the departmental sheet ---------------------------------------
    path, written = names["write_the_departmental_sheet"](
        module, sheet, module.root / "PS4001 grades.xlsx"
    )

    assert path.exists()
    assert written.written == len(sheet)
    assert ModuleFile.load(marked_module).module.status.departmental_sheet_written

    # --- 7. the moderation pack ------------------------------------------
    sample = names["draw_the_sample"](sheet, 1, "include")
    pack = names["build_the_pack"](module, sample, module.root / "Moderation")

    assert pack.manifest.is_file()
    assert len(sample.selected) > 0
    assert ModuleFile.load(marked_module).module.status.moderation_pack_built

    # --- 8. SI's upload ---------------------------------------------------
    upload = names["fill_si_upload"](
        module, sheet, module.root / "PS4001_upload.CSV"
    )

    assert upload.filled > 0
    assert not upload.not_enrolled
    assert ModuleFile.load(marked_module).module.status.si_file_written


def test_the_sample_can_be_drawn_again_from_its_own_seed(marked_module, dashboard):
    """What makes a draw defensible months later.

    The pack records the seed it drew with, so "why these students?" has an
    answer that can be re-run rather than asserted.
    """
    names = dashboard(marked_module)
    module = names["found"].module
    _, sheet = names["collate_the_module"](module, names["class_list"], "feedback")

    first = names["draw_the_sample"](sheet, 1, "include")
    again = names["draw_the_sample"](sheet, 1, "include", seed=first.seed)

    assert list(again.selected["Student ID"]) == list(first.selected["Student ID"])
