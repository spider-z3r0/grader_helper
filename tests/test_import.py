#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The package must import using only its declared runtime dependencies."""

import ast
import subprocess
import sys
import textwrap

import pytest

# Declared in [dependency-groups] dev, NOT in [project] dependencies. A dev
# environment has them installed even though an end user's
# `pip install grader-helper` does not -- which is how an accidental import
# of one goes unnoticed until release.
DEV_ONLY_PACKAGES = {"matplotlib", "marimo", "jupyter", "faker", "pytest"}


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
    )


def _imported_names(tree: ast.AST):
    """Yield (top-level module name, lineno) for every import in `tree`."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0], node.lineno
        elif isinstance(node, ast.ImportFrom):
            # Relative imports have no external module to check.
            if node.level == 0 and node.module:
                yield node.module.split(".")[0], node.lineno


def test_package_imports():
    """Bare `import grader_helper` must succeed."""
    result = _run("import grader_helper")
    assert result.returncode == 0, (
        f"import grader_helper failed:\n{result.stderr}"
    )


def test_no_module_imports_a_dev_only_dependency(repo_root):
    """No module in the package may import a dev-only package.

    Regression guard for the stray `from matplotlib.pylab import f` in
    dataframe_operations/__init__.py. matplotlib was correctly dropped from
    the runtime dependencies, so that import made a published release fail
    at import time for every user on every platform.

    This is deliberately a static scan of our own source rather than a
    check of sys.modules after import. sys.modules cannot distinguish "our
    code imported matplotlib" from "a legitimate dependency imported it
    because it happened to be installed" -- and xlwings does exactly that:
    matplotlib is only an `all` extra of xlwings, but xlwings/utils.py
    imports it opportunistically at import time. So a sys.modules check
    passes on Linux (no xlwings) and fails on Windows and macOS (xlwings
    present, matplotlib present via the dev group) without either outcome
    saying anything about our code.
    """
    offenders = []
    for path in sorted((repo_root / "grader_helper").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name, lineno in _imported_names(tree):
            if name in DEV_ONLY_PACKAGES:
                rel = path.relative_to(repo_root)
                offenders.append(f"{rel}:{lineno} imports {name}")

    assert not offenders, "dev-only imports in package source:\n" + "\n".join(
        offenders
    )


def test_repo_root_does_not_shadow_the_package(repo_root):
    """The repo directory must not masquerade as the package.

    The repository directory is itself named ``grader_helper`` and used to
    contain a stale top-level ``__init__.py``. With the repo's *parent* on
    sys.path -- an ordinary situation for a script or notebook sitting
    beside the checkout -- ``import grader_helper`` resolved to the repo
    root rather than the real package, and that stale file raised
    ModuleNotFoundError because it imports ``brightspace_name_folders``
    from the top level when it actually lives in ``file_operations``.
    """
    result = _run(
        f"""
        import sys
        sys.path.insert(0, {str(repo_root.parent)!r})
        import grader_helper
        assert "grader_helper" in grader_helper.__file__
        """
    )
    assert result.returncode == 0, (
        "importing grader_helper with the repo's parent on sys.path failed:\n"
        + result.stderr
    )


# Import name -> distribution name, where they differ.
IMPORT_TO_DISTRIBUTION = {
    "pythoncom": "pywin32",
    "win32com": "pywin32",
    "calamine": "python-calamine",
    "dateutil": "python-dateutil",
    "yaml": "pyyaml",
}


def test_every_imported_package_is_declared(repo_root):
    """Third-party imports must appear in [project.dependencies].

    The mirror of the dev-only guard above, and the one that catches the
    more embarrassing failure: code that imports a package which happens to
    be installed locally but is not declared, so it works here and breaks
    on a clean install. matplotlib was that bug in one direction; pydantic
    was very nearly that bug in the other.
    """
    import sys
    import tomllib

    from packaging.requirements import Requirement

    with open(repo_root / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)

    declared = {
        Requirement(r).name.lower().replace("_", "-")
        for r in pyproject["project"]["dependencies"]
    }

    first_party = {"grader_helper"}
    stdlib = set(sys.stdlib_module_names)

    undeclared = {}
    for path in sorted((repo_root / "grader_helper").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name, lineno in _imported_names(tree):
            if name in stdlib or name in first_party or name.startswith("_"):
                continue
            distribution = IMPORT_TO_DISTRIBUTION.get(name, name)
            distribution = distribution.lower().replace("_", "-")
            if distribution not in declared:
                undeclared.setdefault(
                    distribution, f"{path.relative_to(repo_root)}:{lineno}"
                )

    assert not undeclared, (
        "imported but not declared in [project.dependencies]:\n"
        + "\n".join(f"  {dist}  (first seen at {where})"
                    for dist, where in sorted(undeclared.items()))
    )
