#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Packaging metadata must be well formed.

A malformed requirement string in pyproject.toml is not a minor annoyance:
uv parses the project on *every* invocation, so one bad entry breaks
``uv venv``, ``uv lock``, ``uv sync`` and ``uv tree`` alike -- i.e. it
blocks all tooling, including the ability to run this suite.
"""

import tomllib

import pytest
from packaging.requirements import InvalidRequirement, Requirement


@pytest.fixture
def pyproject(repo_root):
    with open(repo_root / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def _invalid(requirements):
    bad = []
    for r in requirements:
        try:
            Requirement(r)
        except InvalidRequirement as e:
            bad.append((r, str(e).splitlines()[0]))
    return bad


def test_runtime_requirements_are_valid_pep508(pyproject):
    bad = _invalid(pyproject["project"]["dependencies"])
    assert not bad, f"invalid runtime requirement(s): {bad}"


def test_dependency_group_requirements_are_valid_pep508(pyproject):
    """Regression guard for ``"faker = 38.2.0"``.

    That entry is valid TOML (it is a quoted string) but invalid PEP 508,
    so tomllib parses it happily and uv then rejects the whole project.
    """
    bad = []
    for group, reqs in pyproject.get("dependency-groups", {}).items():
        bad.extend((group, r, err) for r, err in _invalid(reqs))
    assert not bad, f"invalid dependency-group requirement(s): {bad}"
