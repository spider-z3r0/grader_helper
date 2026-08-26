#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Shared fixtures for the grader_helper test suite.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl
import sys

import pytest

REPO_ROOT = pl.Path(__file__).parent.parent


@pytest.fixture
def repo_root() -> pl.Path:
    """The repository root, i.e. the directory holding pyproject.toml."""
    return REPO_ROOT


@pytest.fixture
def resources_dir() -> pl.Path:
    """Static test assets that ship with the suite."""
    return pl.Path(__file__).parent / "resources"


@pytest.fixture
def feedback_sheet_tree(tmp_path) -> pl.Path:
    """A minimal submissions tree containing one feedback sheet.

    The files are empty -- these fixtures exist to exercise the *discovery*
    and *delegation* logic, not the Excel reading itself. Tests that need
    real workbooks are marked ``excel``.
    """
    student = tmp_path / "OMALLEY, KEVIN(12345678)"
    student.mkdir()
    (student / "Feedback sheet 12345678.xlsx").write_bytes(b"")
    return tmp_path


def pytest_report_header(config):
    return f"grader_helper: platform={sys.platform}"
