#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Choosing whose work is moderated, and assembling it.

Two things here are audit properties rather than arithmetic, and they are the
ones worth the most: a draw must be reproducible from its recorded seed, and a
student must be matched to their submission by parsing the folder name rather
than searching it. The first is what lets anyone answer "why this student?"
six months on; the second is what stops the wrong student's work reaching a
moderator.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl

import pandas as pd
import pytest

from grader_helper import (
    build_moderation_pack,
    flag_borderline,
    next_grade_up,
    read_moderation_manifest,
    sample_for_moderation,
)
from grader_helper.moderation.pack import MANIFEST_NAME, _submissions_by_student

# --------------------------------------------------------------------------
# Borderline.


@pytest.mark.parametrize(
    "total, expected",
    [
        (69, ("B1", 1.0)),   # one mark below a 2.1
        (64, ("B2", 1.0)),
        (39, ("C3", 1.0)),   # a compensated fail one mark below a pass
        (34, ("D1", 1.0)),
        (49, ("C2", 1.0)),
        (48, ("C2", 2.0)),
        (70, ("A2", 5.0)),   # just into B1, a long way off A2
        (80, None),          # the top band has nothing above it
        (100, None),
        (0, None),           # no participation is not one point below anything
    ],
)
def test_the_distance_to_the_next_grade(total, expected):
    assert next_grade_up(total) == expected


def test_a_borderline_student_is_one_mark_from_the_next_band():
    """The case the whole feature exists for.

    69 and 70 are one mark apart and a degree classification apart. If the
    marking is wrong anywhere, it costs the student most here.
    """
    marks = pd.DataFrame(
        {
            "Student ID": ["1", "2", "3", "4"],
            "Total % Grade": [69.0, 68.0, 87.0, 0.0],
            "Letter Grade": ["B2", "B2", "A1", "NG"],
        }
    )
    flagged = flag_borderline(marks)

    assert flagged["Borderline"].tolist() == [True, False, False, False]
    assert flagged["Next Grade"].tolist()[:2] == ["B1", "B1"]
    assert flagged["Points To Next"].tolist()[:2] == [1.0, 2.0]

    # Nothing is dropped -- the frame stays usable for everything else.
    for column in marks.columns:
        assert column in flagged.columns
    assert len(flagged) == len(marks)


def test_the_top_band_and_no_participation_are_never_borderline():
    marks = pd.DataFrame(
        {
            "Student ID": ["1", "2"],
            "Total % Grade": [99.0, 0.0],
            "Letter Grade": ["A1", "NG"],
        }
    )
    flagged = flag_borderline(marks, tolerance=50)

    assert flagged["Borderline"].tolist() == [False, False]
    assert flagged["Next Grade"].isna().all()


def test_a_wider_tolerance_catches_more():
    marks = pd.DataFrame(
        {
            "Student ID": ["1", "2", "3"],
            "Total % Grade": [69.0, 68.0, 67.0],
            "Letter Grade": ["B2", "B2", "B2"],
        }
    )
    assert flag_borderline(marks, tolerance=1)["Borderline"].sum() == 1
    assert flag_borderline(marks, tolerance=3)["Borderline"].sum() == 3


def test_refuses_a_tolerance_of_zero():
    marks = pd.DataFrame(
        {"Student ID": ["1"], "Total % Grade": [69.0], "Letter Grade": ["B2"]}
    )
    with pytest.raises(ValueError, match="greater than 0"):
        flag_borderline(marks, tolerance=0)


# --------------------------------------------------------------------------
# The draw.


@pytest.fixture
def cohort() -> pd.DataFrame:
    """Two students in most bands, one in D1, and a non-participant."""
    rows = [
        ("23304301", 82.0, "A1"), ("23304302", 85.0, "A1"),
        ("23304303", 76.0, "A2"), ("23304304", 78.0, "A2"),
        ("23304305", 71.0, "B1"), ("23304306", 73.0, "B1"),
        ("23304307", 66.0, "B2"), ("23304308", 69.0, "B2"),
        ("00123456", 61.0, "B3"), ("23304310", 63.0, "B3"),
        ("23304311", 39.0, "D1"),
        ("23304312", 0.0, "NG"),
    ]
    return pd.DataFrame(rows, columns=["Student ID", "Total % Grade", "Letter Grade"])


def test_the_same_seed_gives_the_same_sample(cohort):
    """The audit property. Without it there is no answer to 'why this student?'."""
    first = sample_for_moderation(cohort, n=1, seed=1234)
    again = sample_for_moderation(cohort, n=1, seed=1234)

    assert first.selected["Student ID"].tolist() == (
        again.selected["Student ID"].tolist()
    )


def test_a_draw_without_a_seed_returns_the_one_it_used(cohort):
    """An unrecorded seed is the same as no seed at all.

    So the draw generates one and hands it back, and passing it in
    reproduces the selection exactly.
    """
    drawn = sample_for_moderation(cohort, n=1)
    assert isinstance(drawn.seed, int)

    repeated = sample_for_moderation(cohort, n=1, seed=drawn.seed)
    assert repeated.selected["Student ID"].tolist() == (
        drawn.selected["Student ID"].tolist()
    )


def test_different_seeds_generally_disagree(cohort):
    """If every seed gave the same answer the seed would be doing nothing."""
    draws = {
        tuple(sample_for_moderation(cohort, n=1, seed=seed).selected["Student ID"])
        for seed in range(20)
    }
    assert len(draws) > 1


def test_one_student_per_band_and_never_the_non_participant(cohort):
    drawn = sample_for_moderation(cohort, n=1, seed=7)
    bands = drawn.selected["Letter Grade"].tolist()

    assert sorted(bands) == ["A1", "A2", "B1", "B2", "B3", "D1"]
    assert "NG" not in bands, "a student who submitted nothing has nothing to moderate"
    assert "23304312" not in drawn.selected["Student ID"].tolist()


def test_a_band_that_cannot_fill_its_quota_is_named(cohort):
    """Not an error -- a band with one student can only offer one -- but the
    moderator should know the sample is thinner there than asked for."""
    drawn = sample_for_moderation(cohort, n=2, seed=7)

    assert drawn.short_bands == {"D1": 1}
    assert (drawn.selected["Letter Grade"] == "D1").sum() == 1
    assert (drawn.selected["Letter Grade"] == "A1").sum() == 2


def test_requested_students_are_included_and_named(cohort):
    drawn = sample_for_moderation(cohort, n=1, seed=7, also=["23304311"])
    reasons = drawn.selected.set_index("Student ID")["Selected Because"]

    assert "requested" in reasons["23304311"]


def test_refuses_a_requested_student_who_is_not_in_the_marks(cohort):
    """A typo here means somebody the leader wanted looked at silently is not."""
    with pytest.raises(ValueError, match="not in the marks"):
        sample_for_moderation(cohort, n=1, seed=7, also=["99999999"])


def test_borderline_students_can_be_taken_as_well(cohort):
    """The approach the department is discussing instead of the per-band draw."""
    flagged = sample_for_moderation(cohort, n=1, seed=7, borderline="flag")
    included = sample_for_moderation(cohort, n=1, seed=7, borderline="include")

    # 69 is one mark below B1; 39 is one below C3.
    borderline_ids = {"23304308", "23304311"}
    assert borderline_ids <= set(included.selected["Student ID"])
    assert len(included.selected) >= len(flagged.selected)

    reasons = included.selected.set_index("Student ID")["Selected Because"]
    assert "borderline" in reasons["23304308"]


def test_a_student_can_be_selected_for_more_than_one_reason(cohort):
    included = sample_for_moderation(
        cohort, n=2, seed=7, borderline="include", also=["23304308"]
    )
    reasons = included.selected.set_index("Student ID")["Selected Because"]["23304308"]

    assert "borderline" in reasons and "requested" in reasons


def test_refuses_an_unknown_borderline_mode(cohort):
    with pytest.raises(ValueError, match="borderline must be one of"):
        sample_for_moderation(cohort, n=1, borderline="maybe")


# --------------------------------------------------------------------------
# Matching a student to their work.


def test_submissions_are_matched_by_parsing_not_by_substring(tmp_path):
    """`2330430` must not be handed `23304301`'s work.

    The prototype tested whether the id appeared anywhere in the folder name.
    A shorter id that is a prefix of a longer one matches the wrong student,
    and the wrong student's work in a moderation pack is worse than none.
    """
    for name in (
        "27236-46025 - 2330430 Short - 05 March 2026 612 PM",
        "27236-46025 - 23304301 Longer - 05 March 2026 612 PM",
    ):
        (tmp_path / name).mkdir()

    found = _submissions_by_student(tmp_path)

    assert set(found) == {"2330430", "23304301"}
    assert "Short" in found["2330430"].name
    assert "Longer" in found["23304301"].name


def test_a_resubmission_resolves_to_the_later_folder(tmp_path):
    """The one the grader will have marked."""
    early = "27236-46025 - 23304307 Hayes - 05 March 2026 600 PM"
    late = "27236-46025 - 23304307 Hayes - 05 March 2026 700 PM"
    for name in (early, late):
        (tmp_path / name).mkdir()

    assert _submissions_by_student(tmp_path)["23304307"].name == late


# --------------------------------------------------------------------------
# The pack.


@pytest.fixture
def module_and_sheet(tmp_path):
    """PS4003 collated: four assessments, only one with submissions on disk."""
    import sys

    sys.path.insert(0, str(pl.Path(__file__).parent))
    from fake_module import make_third_module

    from grader_helper import (
        collate_module_marks,
        import_brightspace_classlist,
        prepare_data_for_departmental_template,
    )
    from grader_helper.models import ModuleFile

    fake = make_third_module(tmp_path / "PS4003")
    module = ModuleFile.load(tmp_path / "PS4003").module
    class_list = import_brightspace_classlist(module.classlist_path)
    by_id = fake.expected.set_index("Student ID")

    marks = collate_module_marks(
        module,
        class_list,
        source="feedback",
        marks={"mcq": by_id["mcq"].to_dict(), "exam": by_id["exam"].to_dict()},
    )
    return module, prepare_data_for_departmental_template(marks, module)


def test_the_pack_holds_one_folder_per_band_and_assessment(module_and_sheet, tmp_path):
    module, sheet = module_and_sheet
    drawn = sample_for_moderation(sheet, n=1, seed=42)
    pack = build_moderation_pack(module, drawn, tmp_path / "Moderation")

    for _, student in drawn.selected.iterrows():
        band = pack.root / str(student["Letter Grade"])
        assert band.is_dir(), f"no folder for band {student['Letter Grade']}"

    # Only the coursework has a download. The quizzes, MCQ and exam have no
    # submissions folder content and are skipped without complaint.
    assert set(pack.copied) == {"cw1"}
    assert pack.copied["cw1"] == len(drawn.selected) - len(pack.missing)


def test_a_selected_student_with_no_submission_is_named_not_left_empty(
    module_and_sheet, tmp_path
):
    """An empty folder in a pack reads as work the moderator has been through."""
    module, sheet = module_and_sheet
    # 23304311 is the fixture's non-submitter.
    drawn = sample_for_moderation(sheet, n=1, seed=42, also=["23304311"])
    pack = build_moderation_pack(module, drawn, tmp_path / "Moderation")

    assert ("23304311", "cw1") in pack.missing


def test_the_manifest_records_the_draw(module_and_sheet, tmp_path):
    """Who, from which band, why, and with which seed."""
    module, sheet = module_and_sheet
    drawn = sample_for_moderation(sheet, n=1, seed=42, also=["00123456"])
    pack = build_moderation_pack(module, drawn, tmp_path / "Moderation")

    assert pack.manifest.name == MANIFEST_NAME
    manifest = read_moderation_manifest(pack.root)

    assert set(manifest["Seed"]) == {42}
    assert set(manifest["Module"]) == {module.code}
    assert manifest["Selected Because"].notna().all()
    assert len(manifest) == len(drawn.selected)

    # The id keeps its leading zeros through the write and the read back.
    assert "00123456" in manifest["Student ID"].tolist()


def test_the_manifest_reproduces_the_draw(module_and_sheet, tmp_path):
    """The recorded seed is enough to get the same students again."""
    module, sheet = module_and_sheet
    drawn = sample_for_moderation(sheet, n=1)
    pack = build_moderation_pack(module, drawn, tmp_path / "Moderation")

    recorded = int(read_moderation_manifest(pack.root)["Seed"].iloc[0])
    again = sample_for_moderation(sheet, n=1, seed=recorded)

    assert again.selected["Student ID"].tolist() == (
        drawn.selected["Student ID"].tolist()
    )


def test_refuses_to_merge_a_second_draw_into_an_existing_pack(
    module_and_sheet, tmp_path
):
    """The prototype's `dirs_exist_ok=True` plus an unseeded draw meant a
    re-run added a *different* student to each band, leaving the pack holding
    people nobody selected and no way to tell which was which."""
    module, sheet = module_and_sheet
    destination = tmp_path / "Moderation"
    build_moderation_pack(module, sample_for_moderation(sheet, n=1, seed=1), destination)

    with pytest.raises(FileExistsError, match="already holds a pack"):
        build_moderation_pack(
            module, sample_for_moderation(sheet, n=1, seed=2), destination
        )

    replaced = build_moderation_pack(
        module, sample_for_moderation(sheet, n=1, seed=2), destination, overwrite=True
    )
    assert int(read_moderation_manifest(replaced.root)["Seed"].iloc[0]) == 2


def test_a_pack_without_a_manifest_refuses_to_be_read(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError, match="cannot say"):
        read_moderation_manifest(tmp_path / "empty")
