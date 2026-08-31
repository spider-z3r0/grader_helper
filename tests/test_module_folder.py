#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Pointing the tool at a folder.

The first thing anyone does, and the four answers it has. What is being
guarded here is mostly the *distinctions*: an empty folder and a folder
holding a broken module.toml both fail to produce a module, and treating
them alike would either refuse to set up a new module or offer to overwrite
an existing one's memory.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl

import pytest

from grader_helper.models import (
    MODULE_FILENAME,
    FolderState,
    ModuleFile,
    init_module,
    inspect_module_folder,
)


# ---------------------------------------------------------------------------
# Fixtures: one folder per state
# ---------------------------------------------------------------------------


@pytest.fixture
def initialised(tmp_path) -> pl.Path:
    """A folder with a module in it."""
    folder = tmp_path / "PS4034-initialised"
    folder.mkdir()
    init_module(folder, "PS4034", "Research Methods", "2025/26", "KOM")
    return folder


@pytest.fixture
def empty(tmp_path) -> pl.Path:
    """A folder for a module that has not been set up yet."""
    folder = tmp_path / "PS4034-empty"
    folder.mkdir()
    return folder


@pytest.fixture
def broken(tmp_path) -> pl.Path:
    """A module.toml whose weights sum to 90.

    Written by hand rather than through init_module, because init_module
    validates and would refuse -- which is the point of it. This is the file
    you get by editing a good one and mistyping a weight.
    """
    folder = tmp_path / "PS4034-broken"
    folder.mkdir()
    (folder / MODULE_FILENAME).write_text(
        "schema_version = 1\n"
        "\n"
        "[module]\n"
        'code = "PS4034"\n'
        'name = "Research Methods"\n'
        'year = "2025/26"\n'
        'leader = "KOM"\n'
        "\n"
        "[[assessment]]\n"
        'id = "cw1"\n'
        'type = "coursework"\n'
        'name = "Coursework 1"\n'
        "marks_out_of = 100\n"
        "weight = 40\n"
        "\n"
        "[[assessment]]\n"
        'id = "cw2"\n'
        'type = "coursework"\n'
        'name = "Coursework 2"\n'
        "marks_out_of = 100\n"
        "weight = 50\n",
        encoding="utf-8",
    )
    return folder


# ---------------------------------------------------------------------------
# The four states
# ---------------------------------------------------------------------------


def test_a_module_folder_loads(initialised):
    found = inspect_module_folder(initialised)

    assert found.state is FolderState.LOADED
    assert found.loaded
    assert found.module.code == "PS4034"
    assert isinstance(found.file, ModuleFile)
    assert found.error is None


def test_an_empty_folder_is_uninitialised(empty):
    found = inspect_module_folder(empty)

    assert found.state is FolderState.UNINITIALISED
    assert found.module is None
    assert found.error is None


def test_a_broken_module_file_is_unreadable_not_empty(broken):
    """The distinction the whole type exists for.

    Both this and an empty folder fail to produce a module. Only one of them
    should be offered initialisation.
    """
    found = inspect_module_folder(broken)

    assert found.state is FolderState.UNREADABLE
    assert found.module is None
    assert "90" in found.error and "100" in found.error


def test_a_path_that_is_not_there_is_missing(tmp_path):
    found = inspect_module_folder(tmp_path / "no-such-module")

    assert found.state is FolderState.MISSING


def test_a_file_that_is_not_a_module_file_is_missing(tmp_path):
    """A mistyped path, not a module folder whose file happens to be odd."""
    stray = tmp_path / "notes.txt"
    stray.write_text("not a module", encoding="utf-8")

    assert inspect_module_folder(stray).state is FolderState.MISSING


# ---------------------------------------------------------------------------
# What a caller does with the answer
# ---------------------------------------------------------------------------


def test_only_an_empty_folder_may_be_initialised(initialised, empty, broken, tmp_path):
    """The guard that protects a module's memory.

    init_module refuses to overwrite, so offering it for a broken file would
    mean passing overwrite=True -- and that file holds the graders, the quiz
    rules and every status flag recorded so far. A weight typo must be fixed
    by editing, never by starting again.
    """
    assert inspect_module_folder(empty).can_initialise
    assert not inspect_module_folder(initialised).can_initialise
    assert not inspect_module_folder(broken).can_initialise
    assert not inspect_module_folder(tmp_path / "nowhere").can_initialise


def test_it_says_where_the_file_is_or_would_go(empty, broken):
    """Both offers need a path: one to write to, one to send you to edit."""
    assert inspect_module_folder(empty).file_path == empty / MODULE_FILENAME
    assert inspect_module_folder(broken).file_path == broken / MODULE_FILENAME


def test_it_accepts_the_module_file_itself(initialised):
    """So a caller holding the file does not have to remember `.parent`."""
    found = inspect_module_folder(initialised / MODULE_FILENAME)

    assert found.state is FolderState.LOADED
    assert found.folder == initialised


# ---------------------------------------------------------------------------
# It reports rather than raises
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "contents",
    [
        pytest.param("this is not toml at all {{{", id="malformed-toml"),
        pytest.param("", id="empty-file"),
        pytest.param('schema_version = 99\n[module]\ncode = "X"\n', id="future-schema"),
    ],
)
def test_a_file_it_cannot_read_is_an_answer_not_an_exception(tmp_path, contents):
    """A dashboard cell runs on every click; it must not be able to crash.

    Whatever a hand-edited file does wrong, the caller's move is the same --
    show the message, point at the file -- so the set of exceptions is not
    worth enumerating, and none of them may escape.
    """
    folder = tmp_path / "PS4034"
    folder.mkdir()
    (folder / MODULE_FILENAME).write_text(contents, encoding="utf-8")

    found = inspect_module_folder(folder)

    assert found.state is FolderState.UNREADABLE
    assert found.error
    assert isinstance(found.cause, Exception)
