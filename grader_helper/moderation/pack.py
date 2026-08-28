#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Assemble the internal moderation pack, and write down what is in it.

One folder per grade band, one sub-folder per assessment, holding a copy of
each sampled student's submission. That is what the second marker is handed.

Beside it goes ``moderation_sample.csv``, and the manifest matters as much as
the files. It records who was selected, from which band, on what mark, why,
and with which seed -- so the draw can be defended, reproduced, and later
assembled into the external examiner's pack. The notes' point that internal
packs must be kept rather than discarded is really a point about this file:
the folders can be rebuilt from it, and without it they cannot.

Submissions are matched by **parsing** the folder name rather than searching
it for the student id. A substring test finds `23304301` when it is looking
for `2330430`, and the wrong student's work in a moderation pack is worse
than none.

House convention: ``pl`` is pathlib, ``pr`` is polars.

    >>> import pathlib as pl
    >>> import polars as pr
"""

import pathlib as pl
import shutil
from datetime import datetime, timezone
from typing import NamedTuple

from ..dependencies import pd
from ..file_operations.scan_multiple_submissions import parse_brightspace_folder
from ..models import Module
from .sample import REASON_COLUMN, Sample

#: Written beside the pack. The record of what was drawn and why.
MANIFEST_NAME = "moderation_sample.csv"


class Pack(NamedTuple):
    """What `build_moderation_pack` produced."""

    #: The pack's root directory.
    root: pl.Path
    #: The manifest, which is the handoff to the external pack later.
    manifest: pl.Path
    #: assessment id -> how many students' work was copied for it.
    copied: dict[str, int]
    #: ``(student_id, assessment_id)`` where the student was selected but no
    #: submission folder exists. Named rather than left as an empty folder.
    missing: list[tuple[str, str]]

    def __str__(self) -> str:
        return (
            f"{self.root.name}: {sum(self.copied.values())} submissions, "
            f"{len(self.missing)} missing"
        )


def build_moderation_pack(
    module: Module,
    sample: Sample,
    destination: pl.Path | str,
    overwrite: bool = False,
    id_column: str = "Student ID",
    grade_column: str = "Letter Grade",
) -> Pack:
    """
    Copy the sampled students' work into a pack, and write the manifest.

    Args:
    module (Module): The module. Its assessments say where submissions live,
        so no folder names are spelled out here.
    sample (Sample): The selection, from `sample_for_moderation`.
    destination (pl.Path | str): Where the pack is written.
    overwrite (bool): Replace an existing pack. Defaults to False, because
        an existing pack may already have been moderated -- and because a
        second draw quietly merging into the first is how a pack ends up
        holding students nobody selected.
    id_column (str): The column holding the student id.
    grade_column (str): The column holding the letter grade.

    Returns:
    Pack: The paths, the count copied per assessment, and any selected
    student with no submission for an assessment.

    Note:
        A student with nothing submitted for one assessment is **named in
        `missing`**, not left as an empty folder. An empty folder in a
        moderation pack reads as work the moderator has already been through.

        An assessment with no submissions folder at all -- weekly quizzes,
        say -- is skipped without complaint. There is nothing to moderate and
        nothing has gone wrong.

    Raises:
    FileExistsError: If `destination` exists and `overwrite` is False.
    ValueError: If the sample selected nobody.

    Example:
        >>> sample = sample_for_moderation(sheet, n=1)
        >>> pack = build_moderation_pack(module, sample, module.root / "Moderation")
        >>> pack.missing
    """
    if not isinstance(module, Module):
        raise ValueError(
            "module must be a Module. Load it with load_module(), which knows "
            "where each assessment's submissions are."
        )
    if sample.selected.empty:
        raise ValueError(
            "The sample selected nobody, so there is no pack to build. Every "
            "student may be NG -- there is no work to moderate in that case."
        )

    destination = pl.Path(destination)
    if destination.exists() and any(destination.iterdir()):
        if not overwrite:
            raise FileExistsError(
                f"{destination} already holds a pack, which may already have "
                "been moderated. Pass overwrite=True to replace it. Merging a "
                "second draw into the first would leave the pack holding "
                "students nobody selected, with no way to tell which was which."
            )
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    wanted = {
        str(row[id_column]): str(row[grade_column])
        for _, row in sample.selected.iterrows()
    }

    copied: dict[str, int] = {}
    missing: list[tuple[str, str]] = []

    for assessment in module.assessments:
        submissions = assessment.submissions_path
        if not submissions.is_dir():
            # Nothing was ever downloaded for this one -- a quiz, or an exam
            # marked on paper. Not a fault.
            continue

        found = _submissions_by_student(submissions)
        if not found:
            continue

        copied[assessment.id] = 0
        for student_id, grade in wanted.items():
            folder = found.get(student_id)
            if folder is None:
                missing.append((student_id, assessment.id))
                continue
            target = destination / grade / assessment.name / folder.name
            shutil.copytree(folder, target, dirs_exist_ok=True)
            copied[assessment.id] += 1

    manifest = _write_manifest(destination, module, sample, missing)
    return Pack(root=destination, manifest=manifest, copied=copied, missing=missing)


def _submissions_by_student(submissions: pl.Path) -> dict[str, pl.Path]:
    """Student id -> their submission folder, for one assessment.

    Parsed, not searched. `parse_brightspace_folder` pulls the id out of the
    name properly; testing whether the id appears *anywhere* in the folder
    name matches a longer id that happens to contain it.

    Where a student submitted twice, the later folder wins -- the same
    resolution `scan_multiple_subs` exists to help a marker make, and the one
    the grader will have marked.
    """
    found: dict[str, pl.Path] = {}
    latest: dict[str, datetime] = {}
    for folder in sorted(submissions.iterdir()):
        if not folder.is_dir():
            continue
        parsed = parse_brightspace_folder(folder.name)
        if parsed is None:
            continue
        student_id, submitted_at = parsed
        if student_id not in latest or submitted_at >= latest[student_id]:
            latest[student_id] = submitted_at
            found[student_id] = folder
    return found


def _write_manifest(
    destination: pl.Path, module: Module, sample: Sample, missing: list
) -> pl.Path:
    """The record of the draw, written beside the work it selected."""
    manifest = sample.selected.copy()
    manifest.insert(0, "Module", module.code)
    manifest["Seed"] = sample.seed
    manifest["N Per Band"] = sample.n
    manifest["Drawn At"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest["Moderator"] = (
        str(module.internal_moderator) if module.internal_moderator else ""
    )
    manifest["Missing Submissions"] = [
        ", ".join(
            assessment_id
            for student, assessment_id in missing
            if student == str(student_id)
        )
        for student_id in manifest["Student ID"]
    ]

    path = destination / MANIFEST_NAME
    manifest.to_csv(path, index=False)
    return path


def read_moderation_manifest(pack: pl.Path | str) -> pd.DataFrame:
    """
    Read back the record of a draw.

    Args:
    pack (pl.Path | str): The pack directory, or the manifest itself.

    Returns:
    pd.DataFrame: The manifest, with the student id read as text so leading
    zeros survive.

    Note:
        This is how a second run reuses a sample rather than drawing a new
        one, and how the external pack is later assembled over the internal
        ones. Re-drawing is an explicit act, not what happens by default.

    Raises:
    FileNotFoundError: If there is no manifest to read.

    Example:
        >>> drawn = read_moderation_manifest(module.root / "Moderation")
        >>> drawn["Seed"].unique()
    """
    pack = pl.Path(pack)
    path = pack if pack.is_file() else pack / MANIFEST_NAME
    if not path.is_file():
        raise FileNotFoundError(
            f"No moderation manifest at {path}. A pack without one cannot say "
            "who was sampled or why, so it cannot be reused or defended -- "
            "draw a fresh sample with sample_for_moderation."
        )
    return pd.read_csv(path, dtype={"Student ID": str})
