#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Keeping status: what the code may set, and what only a person may.

The rule running through all of it: a step can know it produced a file, and
never that the file was sent, read or accepted. So the automatic flags come
from what a step *returned*, and the manual ones come from a person.

The load-bearing test is `test_a_step_that_did_nothing_sets_no_flag`. "It did
not raise" is not evidence, and a green tick against a step that did nothing
looks exactly like a real one.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl
import sys

import pytest

from grader_helper.file_operations.distribute_feedback_sheets import Distribution
from grader_helper.file_operations.save_distributed_graders import Allocation
from grader_helper.file_operations.write_departmental_sheet import DepartmentalWrite
from grader_helper.models import ModuleFile, ModuleStatus
from grader_helper.ingesting.ingest_completed_graderfiles import Collation
from grader_helper.recording import RULES, evidence_for
from grader_helper.si_upload import SiUpload

sys.path.insert(0, str(pl.Path(__file__).parent))
from fake_module import make_fake_module  # noqa: E402


@pytest.fixture
def handle(tmp_path) -> ModuleFile:
    make_fake_module(tmp_path / "PS4001", distributed=True, marked=True)
    return ModuleFile.load(tmp_path / "PS4001")


# --------------------------------------------------------------------------
# The evidence rules.


def test_a_step_that_did_nothing_sets_no_flag():
    """The whole point. `distribute_feedback_sheets` can match nothing at all
    -- forty folders, no ids recognised -- and not raise. A flag set off that
    is a green tick against a step that did not happen."""
    nothing = Distribution(copied={}, skipped={}, unmatched=["a", "b"])
    flag, satisfied, scope = evidence_for(nothing)

    assert flag == "sheets_distributed"
    assert satisfied is False
    assert scope == "assessment"


def test_an_unrecognised_folder_is_enough_to_withhold_the_flag():
    """Thirty-nine of forty is not finished, and the tick would hide the one."""
    almost = Distribution(
        copied={"1": pl.Path("a")}, skipped={}, unmatched=["mystery folder"]
    )
    assert evidence_for(almost)[1] is False

    done = Distribution(copied={"1": pl.Path("a")}, skipped={}, unmatched=[])
    assert evidence_for(done)[1] is True


def test_a_rerun_that_skipped_everything_still_counts():
    """Sheets already in place are distributed sheets. Skipping is what a
    second run is *supposed* to do -- they may already carry marks."""
    rerun = Distribution(copied={}, skipped={"1": pl.Path("a")}, unmatched=[])
    assert evidence_for(rerun)[1] is True


def test_the_allocation_and_collation_artefacts_need_students_in_them():
    """The artefact is the evidence -- `distributed.xlsx` existing is what says
    the graders were allocated, `completed_grades` that the marks came back.
    An empty file is neither, and its existence alone would say otherwise."""
    assert evidence_for(Allocation(pl.Path("distributed.xlsx"), students=40)) == (
        "graders_allocated", True, "assessment"
    )
    assert evidence_for(Allocation(pl.Path("distributed.xlsx"), students=0))[1] is False

    assert evidence_for(Collation(pl.Path("completed_grades.csv"), students=40)) == (
        "grades_collected", True, "assessment"
    )
    assert evidence_for(Collation(pl.Path("completed_grades.csv"), students=0))[1] is False


def test_every_assessment_flag_can_now_be_recorded():
    """All four, from an artefact rather than by hand."""
    from grader_helper.models.assessment import AssessmentStatus

    covered = {
        rule.flag for rule in RULES.values() if rule.scope == "assessment"
    }
    manual = {"moderated"}  # a person read the pack; nothing on disk says so
    assert covered | manual == set(AssessmentStatus.model_fields)


def test_the_departmental_sheet_needs_rows_in_it():
    assert evidence_for(DepartmentalWrite(pl.Path("x.xlsx"), written=12))[1] is True
    assert evidence_for(DepartmentalWrite(pl.Path("x.xlsx"), written=0))[1] is False


def test_the_si_upload_needs_marks_and_a_matching_roll():
    filled = SiUpload(pl.Path("a.CSV"), filled=12, not_enrolled=[], unmarked=[])
    assert evidence_for(filled)[1] is True

    # A student with a mark whom SI has no row for means the two records
    # disagree, which is not a finished step.
    mismatched = SiUpload(
        pl.Path("a.CSV"), filled=12, not_enrolled=["99999999"], unmarked=[]
    )
    assert evidence_for(mismatched)[1] is False

    empty = SiUpload(pl.Path("a.CSV"), filled=0, not_enrolled=[], unmarked=[])
    assert evidence_for(empty)[1] is False


def test_an_unknown_result_is_refused_rather_than_guessed_at():
    """Setting a flag on no evidence is worse than not setting one."""
    with pytest.raises(TypeError, match="Nothing knows what"):
        evidence_for(pl.Path("some/file.xlsx"))


def test_every_rule_names_a_real_flag():
    """A rule pointing at a flag that does not exist would fail only when it
    fired, which could be a term later."""
    from grader_helper.models.assessment import AssessmentStatus

    for result_type, rule in RULES.items():
        fields = (
            ModuleStatus.model_fields
            if rule.scope == "module"
            else AssessmentStatus.model_fields
        )
        assert rule.flag in fields, (
            f"{result_type.__name__} claims {rule.flag!r} on the {rule.scope} "
            "status, which has no such field"
        )
        assert rule.scope in ("module", "assessment")


# --------------------------------------------------------------------------
# Recording, and the file.


def test_record_sets_the_flag_and_saves(handle):
    done = Distribution(copied={"1": pl.Path("a")}, skipped={}, unmatched=[])
    handle.record(done, "cw1")

    reloaded = ModuleFile.load(handle.path.parent).module
    assert reloaded.assessment("cw1").status.sheets_distributed is True
    assert reloaded.assessment("cw2").status.sheets_distributed is False


def test_record_leaves_the_flag_alone_when_the_step_fell_short(handle):
    """Not an error -- a half-finished step is a normal state of affairs."""
    nothing = Distribution(copied={}, skipped={}, unmatched=["mystery"])
    handle.record(nothing, "cw1")

    reloaded = ModuleFile.load(handle.path.parent).module
    assert reloaded.assessment("cw1").status.sheets_distributed is False


def test_record_needs_an_id_for_a_per_assessment_result(handle):
    done = Distribution(copied={"1": pl.Path("a")}, skipped={}, unmatched=[])
    with pytest.raises(ValueError, match="per-assessment result"):
        handle.record(done)


def test_module_level_results_need_no_id(handle):
    handle.record(DepartmentalWrite(pl.Path("x.xlsx"), written=12))

    assert ModuleFile.load(handle.path.parent).module.status.departmental_sheet_written


def test_module_status_survives_a_reload(handle):
    handle.set_module_status(sent_to_department=True, si_submitted=True)
    status = ModuleFile.load(handle.path.parent).module.status

    assert status.sent_to_department is True
    assert status.si_submitted is True


def test_module_status_and_assessment_status_do_not_clobber_each_other(handle):
    """Both land on a field called `status`, and the first version of the
    reader set the module's before popping the assessments' -- which silently
    ate every assessment flag in the file."""
    handle.set_status("cw1", sheets_distributed=True, grades_collected=True)
    handle.set_module_status(sent_to_department=True)

    module = ModuleFile.load(handle.path.parent).module
    assert module.assessment("cw1").status.sheets_distributed is True
    assert module.assessment("cw1").status.grades_collected is True
    assert module.status.sent_to_department is True


def test_the_module_status_lives_in_its_own_table(handle):
    """Not [status.module]: an assessment legitimately called "module" would
    collide with it, and [status] is keyed by assessment id."""
    handle.set_module_status(si_file_written=True)
    text = handle.path.read_text()

    assert "[module_status]" in text
    assert "[status.module]" not in text


def test_the_manual_flags_start_false_and_nothing_sets_them(handle):
    """The code cannot know a file reached a person, so it must never say so."""
    handle.record(DepartmentalWrite(pl.Path("x.xlsx"), written=12))
    handle.record(SiUpload(pl.Path("a.CSV"), filled=12, not_enrolled=[], unmarked=[]))

    status = ModuleFile.load(handle.path.parent).module.status
    assert status.departmental_sheet_written is True
    assert status.si_file_written is True
    assert status.sent_to_department is False, "only a person can know this"
    assert status.si_submitted is False, "only a person can know this"


def test_set_module_status_refuses_an_unknown_flag(handle):
    with pytest.raises(AttributeError, match="not a module status flag"):
        handle.set_module_status(definitely_finished=True)


def test_the_authors_sections_are_untouched_by_a_status_write(handle):
    """The file's own rule: [module], [paths] and [[assessment]] are the
    author's, and only [status] and [module_status] are appended to."""
    before = handle.path.read_text()
    author_lines = [
        line for line in before.splitlines()
        if line.startswith(("[module", "[paths", "[[assessment"))
        and line != "[module_status]"
    ]

    handle.set_module_status(sent_to_department=True)
    after = handle.path.read_text()

    for line in author_lines:
        assert line in after, f"{line} was lost writing module status"
