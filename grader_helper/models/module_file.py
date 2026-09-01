#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Reading and writing ``module.toml``.

The file is meant to be edited by hand as well as by this package, so
comments and layout have to survive a save. That only works if writing
*mutates the parsed document* rather than re-serialising the model:

    doc = tomlkit.parse(text)          # keeps comments and formatting
    module = Module.model_validate(..) # pydantic validates
    doc["assessment"][0]["status"]["grades_collected"] = True
    path.write_text(tomlkit.dumps(doc))

``tomlkit.dumps(module.model_dump())`` would throw away exactly what tomlkit
was chosen for. :class:`ModuleFile` therefore holds the document and the
model together, and :meth:`ModuleFile.save` walks the model into the
document leaf by leaf, leaving untouched keys -- and every comment -- alone.

Two rules make that hold:

**Only keys already in the file are updated.** Appending a key or a
sub-table to an existing table places it after that table's trailing
comment, and tomlkit attaches a trailing comment to the table it follows --
so a comment written to introduce the *next* section silently migrates into
the previous one. Never appending means never displacing.

**Status lives in its own ``[status]`` section, not inside
``[[assessment]]``.** Progress flags are the one thing the tool writes that
the author did not, so they need somewhere it is safe to append: the end of
the document, where there is nothing to displace. It also draws the honest
line -- ``[module]``, ``[paths]`` and ``[[assessment]]`` are the author's
configuration and are only ever read or updated in place; ``[status]`` is
the tool's memory.

Writes are atomic (temp file then ``os.replace``), because this one file is
the module's memory and a half-written save would lose it.
"""

import os
import pathlib as pl
import tempfile
from typing import Any

import tomlkit
from tomlkit.items import AoT, SingleKey, Table

from .module import SCHEMA_VERSION, Module
from .people import Person, as_person

#: Conventional filename at the module root.
MODULE_FILENAME = "module.toml"


class ModuleFile:
    """A ``module.toml`` on disk, its parsed document, and its model."""

    def __init__(self, path: pl.Path, document: tomlkit.TOMLDocument, module: Module):
        self.path = path
        self.document = document
        self.module = module

    # -------------------------------------------------------------- loading

    @classmethod
    def load(cls, path: pl.Path) -> "ModuleFile":
        """Load a module from ``path``, or from ``path/module.toml``."""
        path = pl.Path(path)
        if path.is_dir():
            path = path / MODULE_FILENAME

        if not path.exists():
            raise FileNotFoundError(
                f"No module file at {path}. Run init_module() to create one."
            )

        document = tomlkit.parse(path.read_text(encoding="utf-8"))
        return cls(path, document, _to_module(document, path))

    # -------------------------------------------------------------- saving

    def save(self, path: pl.Path | None = None) -> pl.Path:
        """Write the model back, preserving comments and layout."""
        target = pl.Path(path) if path is not None else self.path

        payload = self.module.model_dump(mode="json", exclude_none=True)
        assessments = payload.pop("assessments", [])
        statuses = {a["id"]: a.pop("status") for a in assessments if "status" in a}

        # Mirror the file's own shape: a [module] block, then [[assessment]].
        module_keys = {
            "code", "name", "year", "leader", "internal_moderator",
        }
        module_block = {k: payload.pop(k) for k in list(payload) if k in module_keys}

        # The author's sections: updated in place, never appended to.
        _sync(self.document, {"schema_version": payload.pop("schema_version")})
        _sync_table(self.document, "module", module_block)
        for key in ("paths",):
            if key in payload:
                _sync_table(self.document, key, payload.pop(key))
        _sync_aot(self.document, "assessment", assessments)

        # The tool's sections: appended at the end of the document, where
        # there is nothing to displace.
        _sync_table(self.document, "status", statuses, add_missing=True)
        _sync_table(
            self.document, "module_status", payload.pop("status", {}), add_missing=True
        )

        _atomic_write(target, tomlkit.dumps(self.document))
        self.path = target
        return target

    # ------------------------------------------------------------ shortcuts

    def record(self, result, assessment_id: str | None = None) -> "ModuleFile":
        """Set a status flag from what a step returned, and save.

        The automatic half of status keeping. Hand it whatever a step gave
        back -- a ``Distribution``, a ``Pack``, an ``SiUpload``, a
        ``DepartmentalWrite`` -- and the flag it justifies is set.

        **The evidence is the return value, not the absence of an
        exception.** `distribute_feedback_sheets` completes perfectly happily
        having matched nothing at all; recording `sheets_distributed = True`
        off that would put a green tick against a step that did nothing, which
        is this package's usual enemy wearing a different hat. What counts as
        done for each result type is in
        :mod:`grader_helper.recording`, beside the type that knows.

        A result whose evidence does *not* support the flag leaves the status
        alone and says so, rather than raising -- a half-finished step is a
        normal state of affairs, not a fault.

        Args:
        result: What a step returned.
        assessment_id (str | None): Required for a per-assessment result;
            ignored for a module-level one.

        Returns:
        ModuleFile: self, saved.

        Raises:
        TypeError: If nothing knows how to read evidence from `result`.
        ValueError: If a per-assessment result arrives without an id.

        Example:
            >>> distribution = distribute_feedback_sheets(...)
            >>> handle.record(distribution, assessment.id)
        """
        # Imported here rather than at module scope: the registry knows about
        # file_operations and moderation, both of which import models. A
        # function-local import keeps the layering honest without a cycle.
        from ..recording import evidence_for

        flag, satisfied, scope = evidence_for(result)

        if scope == "assessment":
            if assessment_id is None:
                raise ValueError(
                    f"{type(result).__name__} is a per-assessment result, so "
                    "record() needs the assessment id it belongs to."
                )
            if satisfied:
                return self.set_status(assessment_id, **{flag: True})
            return self

        if satisfied:
            setattr(self.module.status, flag, True)
            self.save()
        return self

    def set_assessment(self, assessment_id: str, **keys) -> "ModuleFile":
        """Record configuration on one assessment and save.

        Unlike `save`, this **adds** the keys when the file has not got them,
        which is what lets the app answer a question once instead of every
        time -- where the group sheets are, which column is the group. See
        :func:`add_key` for why appending is not enough.

        Args:
        assessment_id (str): Which assessment.
        **keys: Field names and values, validated against `Assessment`.

        Returns:
        ModuleFile: self, saved.

        Raises:
        KeyError: If there is no such assessment, in the model or the file.

        Example:
            >>> handle.set_assessment("cw1", group_sheets="groups.xlsx")
        """
        assessment = self.module.assessment(assessment_id)
        for name, value in keys.items():
            setattr(assessment, name, value)

        table = next(
            (
                t for t in _assessment_tables(self.document)
                if t.get("id") == assessment_id
            ),
            None,
        )
        if table is None:
            raise KeyError(
                f"No [[assessment]] with id {assessment_id!r} in "
                f"{self.path}. The model and the file disagree, which is not "
                "something to fix by writing a new block."
            )
        for name, value in keys.items():
            add_key(table, name, getattr(assessment, name))

        self.save()
        return self

    def set_paths(self, **keys: str) -> "ModuleFile":
        """Record where something lives in `[paths]`, and save.

        Adds the key when the file has not got it -- see
        :meth:`set_assessment`.

        Raises:
        KeyError: If the file has no `[paths]` table. Which one a module has
            is the author's to declare, and inventing the table would put it
            wherever the writer happened to be.
        """
        for name, value in keys.items():
            setattr(self.module.paths, name, value)

        table = self.document.get("paths")
        if table is None:
            raise KeyError(
                f"{self.path} has no [paths] table to record in. Add one, "
                "even empty, and this can fill it in."
            )
        for name, value in keys.items():
            add_key(table, name, value)

        self.save()
        return self

    def set_status(self, assessment_id: str, **flags: bool) -> "ModuleFile":
        """Flip status flags on one assessment and save.

        The move the dashboard makes after finishing a step.
        """
        status = self.module.assessment(assessment_id).status
        for flag, value in flags.items():
            if not hasattr(status, flag):
                raise AttributeError(
                    f"{flag!r} is not a status flag. Known flags: "
                    f"{list(type(status).model_fields)}"
                )
            setattr(status, flag, value)
        self.save()
        return self

    def set_module_status(self, **flags: bool) -> "ModuleFile":
        """Flip module-level status flags and save.

        The manual half. `sent_to_department` and `si_submitted` are the ones
        that matter here: nothing on disk can tell us a file reached a person,
        so somebody has to say so -- a button in the dashboard, or this call
        from a notebook.
        """
        for flag, value in flags.items():
            if not hasattr(self.module.status, flag):
                raise AttributeError(
                    f"{flag!r} is not a module status flag. Known flags: "
                    f"{list(type(self.module.status).model_fields)}"
                )
            setattr(self.module.status, flag, value)
        self.save()
        return self


def load_module(path: pl.Path) -> Module:
    """Load just the model, for read-only use."""
    return ModuleFile.load(path).module


def _to_module(document: tomlkit.TOMLDocument, path: pl.Path) -> Module:
    """Validate a parsed document into a Module.

    Shared by :meth:`ModuleFile.load` and :func:`init_module`, so a file this
    package writes is validated by exactly the path that reads it back. A
    starter file that would not load is a bug worth catching before it
    reaches the disk, not after.
    """
    data = _plain(document)

    found = data.get("schema_version", SCHEMA_VERSION)
    if found > SCHEMA_VERSION:
        raise ValueError(
            f"{path.name} declares schema_version {found}, but this "
            f"version of grader_helper understands {SCHEMA_VERSION}. "
            "Upgrade grader_helper."
        )

    # [[assessment]] reads better in the file than a plural key.
    if "assessment" in data and "assessments" not in data:
        data["assessments"] = data.pop("assessment")

    # Fold [status.<id>] back onto its assessment.
    status = data.pop("status", {}) or {}
    for assessment in data.get("assessments", []):
        recorded = status.get(assessment.get("id"))
        if recorded:
            assessment["status"] = recorded

    # The module's own status, in its own table -- and read *after* [status]
    # has been popped, because both land on the model's `status` field and
    # setting this first silently ate every assessment's flags.
    #
    # Deliberately not [status.module]: [status] is keyed by assessment id,
    # and an assessment legitimately called "module" would collide with it. A
    # separate table cannot.
    data["status"] = data.pop("module_status", {}) or {}

    # The module block is flattened into the model.
    module_block = data.pop("module", {})
    data = {**module_block, **data}
    data["root"] = path.parent

    return Module.model_validate(data)


# --------------------------------------------------------------------------
# document syncing
# --------------------------------------------------------------------------


def _plain(node: Any) -> Any:
    """tomlkit containers into plain dicts/lists, for pydantic."""
    if isinstance(node, (Table, tomlkit.TOMLDocument)) or isinstance(node, dict):
        return {k: _plain(v) for k, v in node.items()}
    if isinstance(node, AoT) or isinstance(node, list):
        return [_plain(v) for v in node]
    return node


def _sync(doc_node: Any, data: dict, add_missing: bool = False) -> None:
    """Update values in place.

    With ``add_missing`` false -- the default -- a key absent from the
    document is left absent. See the note in ModuleFile.save for why that
    matters beyond tidiness.
    """
    for key, value in data.items():
        if key not in doc_node and not add_missing:
            continue
        if isinstance(value, dict):
            _sync_table(doc_node, key, value, add_missing)
        elif isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            _sync_aot(doc_node, key, value)
        else:
            if key not in doc_node or doc_node[key] != value:
                doc_node[key] = value


def _sync_table(doc_node: Any, key: str, data: dict, add_missing: bool = False) -> None:
    if not data:
        return
    existing = doc_node.get(key)
    if not isinstance(existing, (Table, dict)):
        if not add_missing:
            return
        table = tomlkit.table()
        _sync(table, data, add_missing=True)
        doc_node[key] = table
        return
    _sync(existing, data, add_missing)


def _assessment_tables(document: Any) -> list:
    """The [[assessment]] tables, in file order."""
    aot = document.get("assessment")
    return list(aot) if isinstance(aot, (AoT, list)) else []


def add_key(table: Any, key: str, value: Any) -> None:
    """Set a key on a table, above its trailing blank lines and comments.

    Appending puts it *after* them, and tomlkit binds trailing trivia to the
    table it follows -- so a comment introducing the next section ends up
    reading as part of this one, with the new key orphaned below it::

        [[assessment]]
        id = "Assignment 1"

        # -------------------------------------------------------------
        # Where things live, relative to this file.
        # -------------------------------------------------------------
        group_sheets = "groups.xlsx"     <- appended here
        [paths]

That is the hazard `save` avoids by never adding a key at all. It is worth
avoiding rather than never adding, because a form that cannot record its
answer is a form that asks the same question every time.

The insertion point is the index after the last real key, found by walking
back over the entries with no key of their own -- which is exactly the
trailing whitespace and comments.
    """
    if key in table:
        table[key] = value
        return

    container = table.value
    body = container.body
    at = len(body)
    while at > 0 and body[at - 1][0] is None:
        at -= 1

    if at >= len(body):
        # Nothing trails the last key, so there is nothing to get in front
        # of. Appending is both correct and the only thing tomlkit will do:
        # _insert_at refuses an index past the end of the body.
        table[key] = value
        return
    container._insert_at(at, SingleKey(key), tomlkit.item(value))


def _sync_aot(doc_node: Any, key: str, rows: list[dict]) -> None:
    existing = doc_node.get(key)

    # Rebuild wholesale when the shape changed; otherwise update in place so
    # per-assessment comments survive.
    same_shape = (
        isinstance(existing, (AoT, list))
        and len(existing) == len(rows)
        and all(isinstance(item, (Table, dict)) for item in existing)
    )
    if not same_shape:
        aot = tomlkit.aot()
        for row in rows:
            table = tomlkit.table()
            _sync(table, row)
            aot.append(table)
        doc_node[key] = aot
        return

    for table, row in zip(existing, rows):
        _sync(table, row)


def _atomic_write(path: pl.Path, text: str) -> None:
    """Write via a temp file in the same directory, then replace.

    This file is the module's memory; a half-written save would lose it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        pl.Path(tmp_name).unlink(missing_ok=True)
        raise


# --------------------------------------------------------------------------
# creating a starter file
# --------------------------------------------------------------------------
#
# The file is meant to be hand-edited, so what init_module writes is a
# *commented* file, not a minimal one. The comments carry the two rules a
# reader cannot infer from the keys -- that weights must sum to 100, and
# that an assessment's two numbers decide its grade-sheet columns -- and
# grader_helper preserves them across every later save.


#: A default shape that demonstrates both cases: two courseworks marked out
#: of 100 and worth less, so each gets a raw and a weighted column, and an
#: MCQ marked on its own contribution, which needs only one. Weights sum to
#: 100, so the starter file loads without being edited first.
STARTER_ASSESSMENTS: tuple[dict, ...] = (
    dict(id="cw1", type="coursework", name="Coursework 1", marks_out_of=100, weight=40),
    dict(id="cw2", type="coursework", name="Coursework 2", marks_out_of=100, weight=50),
    dict(id="mcq", type="mcq", name="MCQ", marks_out_of=10, weight=10),
)

_HEADER = """\
schema_version = {schema_version}

# ---------------------------------------------------------------------------
# {code} -- {name}
#
# Edit this by hand. grader_helper preserves your comments and layout, and
# only ever appends to its own [status] section at the end of the file.
#
# Paths are relative to this file, whose directory is the module root.
# Nothing absolute is stored, because these live under OneDrive where the
# absolute path differs between machines.
# ---------------------------------------------------------------------------

[module]
code = {code_v}
name = {name_v}
year = {year_v}
"""

_ASSESSMENT_PREAMBLE = """
# ---------------------------------------------------------------------------
# Assessment
#
# Each piece carries two numbers, and every grade-sheet column falls out of
# them:
#
#   marks_out_of  what the piece is marked on -- what a grader writes on the
#                 feedback sheet, and what the student is told they scored
#   weight        what it contributes to the module total, out of 100
#
# Where they differ you get two columns, raw and weighted; where they are
# equal there is nothing to weight, so there is one:
#
#   Coursework 1, out of 100, worth 40  ->  "Coursework 1 (100)"
#                                           "Coursework 1 (40)"
#   MCQ, out of 10, worth 10            ->  "MCQ (10)"
#
# Ten weekly quizzes, each pass worth 1%, are ONE assessment marked out of 10
# and worth 10 -- the quiz count and the marks available are the same number.
#
# A quiz assessment carries two more keys, because its mark is collected
# from Brightspace's per-quiz exports rather than written on a feedback
# sheet, and how it is collected is the module's rule:
#
#   pass_mark     the percentage one quiz must exceed to count as passed.
#                 Strictly above: at 80, a score of exactly 80 has failed
#   free_passes   quizzes that may be failed without losing a mark. Added to
#                 the count of passes, then capped at marks_out_of
#
# Eleven quizzes, ten marks, free_passes = 1 is "you may drop one week".
#
# A group assessment must say which kind it is, because the two are nothing
# alike on disk and neither is guessable from the download:
#
#   group = true
#   group_source = "brightspace"     the groups were made in Brightspace, so
#                                    they come down in the class list as a
#                                    group column, and the download has one
#                                    folder, one feedback sheet and one mark
#                                    per group
#
#   group = true
#   group_source = "module_leader"   the groups are yours, kept in sheets of
#                                    your own -- a folder of them, or one
#                                    file, named by group_sheets. The
#                                    download is the ordinary individual
#                                    shape -- one folder and one feedback
#                                    sheet per student -- so marks may
#                                    differ within a group. The sheets are
#                                    collected into one student-id-to-group
#                                    table before the marking is
#                                    allocated
#
# Either way a whole group goes to one marker, so a team's work is assessed
# by one person.
#
# Where a sheet has more than one column that could be the group -- a Team,
# a cohort code and a combined Group, say -- and they disagree about who is in
# a team with whom, loading refuses rather than guessing. Answer it once:
#
#   group_column = "Group"                 one column holds the whole key
#   group_column = ["Cohort", "Team"]      composed, joined with "_", so 2A
#                                          and 1 become "2A_1", for team
#                                          numbers that restart per cohort
#
# The weights must sum to 100. That is checked every time the file loads,
# because weights that do not sum to 100 make every student's total wrong and
# the error is invisible until the marks are audited.
#
# Each assessment gets a folder, and inside it:
#
#   <folder>/                  the rubric, and distributed.xlsx once allocated
#     submissions/             the unzipped Brightspace download
#     groups/                  your own group sheets, for group_source =
#                              "module_leader" only. group_sheets names this;
#                              a name with a suffix -- groups.xlsx -- is one
#                              file rather than a folder of them
#     grading_output/          grader workbooks, completed_grades.xlsx, and
#                              the collected group_membership.csv
#
# grading_output holds only what this tool writes, so it can be deleted and
# regenerated without touching anything you or Brightspace put there.
# ---------------------------------------------------------------------------
"""


def _toml_value(value) -> str:
    """Render a Python value as TOML, quoting and escaping properly."""
    return tomlkit.item(value).as_string()


def _render_assessment(spec: dict) -> str:
    """One [[assessment]] block, keys in a readable order."""
    ordered = [
        "id", "type", "name", "marks_out_of", "weight",
        "pass_mark", "free_passes",
        "folder", "submissions", "grading_output",
        "rubric", "grade_cell", "graders",
        "group", "group_source", "group_sheets", "group_column", "due_date",
    ]
    lines = ["", "[[assessment]]"]
    for key in ordered:
        if key in spec and spec[key] is not None:
            lines.append(f"{key} = {_toml_value(spec[key])}")
    # Anything the caller passed that is not in the canonical order still
    # gets written, rather than being silently dropped.
    for key, value in spec.items():
        if key not in ordered and value is not None:
            lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def init_module(
    path: pl.Path,
    code: str,
    name: str,
    year: str,
    leader: "str | dict | Person",
    assessments: "list[dict] | None" = None,
    internal_moderator: "str | dict | Person | None" = None,
    paths: "dict | None" = None,
    overwrite: bool = False,
    create_dirs: bool = True,
) -> ModuleFile:
    """
    Write a starter ``module.toml``, with its explanatory comments in place.

    Args:
    path (pl.Path): The module root, or the file itself. A directory gets
        ``module.toml`` written inside it.
    code (str): Module code, e.g. "PS4001".
    name (str): Module title.
    year (str): Academic year, e.g. "2025/26".
    leader: The module leader -- initials, or a mapping with more detail.
    assessments (list[dict] | None): The module's assessment. Defaults to a
        worked example whose weights already sum to 100, so the file loads
        before it is edited.
    internal_moderator: Optional, same forms as ``leader``.
    paths (dict | None): Overrides for the ``[paths]`` block.
    overwrite (bool): Whether to replace an existing file. Defaults to False.
    create_dirs (bool): Also create the directories the module describes --
        the assessments root, and each assessment's own folder, submissions
        and grading_output. Defaults to True, because a module.toml naming
        folders that do not exist is a half-finished setup.

    Returns:
    ModuleFile: The file, its parsed document and its validated model.

    Raises:
    FileExistsError: If a module file is already there and ``overwrite`` is
        False. That file is the module's memory; clobbering it is not
        something to do by accident.
    ValueError: If the result would not be a valid module -- most often
        weights that do not sum to 100.

    Example:
        >>> init_module(pl.Path("PS4001"), "PS4001", "Research Methods", "2025/26", "KOM")
    """
    path = pl.Path(path)
    if path.is_dir() or not path.suffix:
        path = path / MODULE_FILENAME

    if path.exists() and not overwrite:
        raise FileExistsError(
            f"{path} already exists. That file is the module's memory -- its "
            "assessment, its graders and everything grader_helper has "
            "recorded about progress -- so it is not replaced by accident. "
            "Pass overwrite=True if you really mean to start again."
        )

    specs = [dict(spec) for spec in (assessments or STARTER_ASSESSMENTS)]

    text = _HEADER.format(
        schema_version=SCHEMA_VERSION,
        code=code,
        name=name,
        code_v=_toml_value(code),
        name_v=_toml_value(name),
        year_v=_toml_value(year),
    )

    # A person is written as a sub-table when there is detail to carry, and
    # as bare initials when there is not -- the same shorthand the reader
    # accepts, so a hand-written file and a generated one look alike.
    #
    # Scalars must all be written BEFORE any sub-table. Once [module.leader]
    # is open, a bare `internal_moderator = "SOB"` after it belongs to the
    # leader, not to [module] -- so the moderator is parsed as an unknown key
    # on Person, ignored, and silently lost.
    people = [
        (key, as_person(person))
        for key, person in (
            ("leader", leader),
            ("internal_moderator", internal_moderator),
        )
        if person is not None
    ]

    for key, person in people:
        rendered = person.model_dump()
        if isinstance(rendered, str):
            text += f"{key} = {_toml_value(rendered)}\n"

    for key, person in people:
        rendered = person.model_dump()
        if not isinstance(rendered, str):
            text += f"\n[module.{key}]\n"
            for field, value in rendered.items():
                text += f"{field} = {_toml_value(value)}\n"

    path_block = {"assessments": "assessments", **(paths or {})}
    text += "\n[paths]\n"
    for key, value in path_block.items():
        if value is not None:
            text += f"{key} = {_toml_value(value)}\n"

    text += _ASSESSMENT_PREAMBLE
    for spec in specs:
        text += _render_assessment(spec)

    # Validate before writing, through the same path that reads a file back.
    # A starter file that would not load is worth catching here rather than
    # leaving on disk for the author to puzzle over.
    document = tomlkit.parse(text)
    module = _to_module(document, path)

    _atomic_write(path, text)

    if create_dirs:
        # After the write, so a module.toml that failed validation leaves no
        # directories behind either.
        for directory in module.directories:
            directory.mkdir(parents=True, exist_ok=True)

    return ModuleFile(path, document, module)
