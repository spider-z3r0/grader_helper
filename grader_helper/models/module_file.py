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
from tomlkit.items import AoT, Table

from .module import SCHEMA_VERSION, Module

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

        # The module block is flattened into the model.
        module_block = data.pop("module", {})
        data = {**module_block, **data}
        data["root"] = path.parent

        return cls(path, document, Module.model_validate(data))

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

        # The tool's section: appended at the end of the document, where
        # there is nothing to displace.
        _sync_table(self.document, "status", statuses, add_missing=True)

        _atomic_write(target, tomlkit.dumps(self.document))
        self.path = target
        return target

    # ------------------------------------------------------------ shortcuts

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


def load_module(path: pl.Path) -> Module:
    """Load just the model, for read-only use."""
    return ModuleFile.load(path).module


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
