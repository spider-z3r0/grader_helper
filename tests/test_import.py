#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The package must import using only its declared runtime dependencies.

These tests run in a subprocess so that ``sys.modules`` reflects exactly
what importing grader_helper pulls in, uncontaminated by the test session.
"""

import subprocess
import sys
import textwrap

import pytest

# Declared in [dependency-groups] dev, NOT in [project] dependencies. A dev
# environment therefore has them installed even though an end user's
# `pip install grader-helper` does not -- which is precisely how an
# accidental import of one goes unnoticed until release.
DEV_ONLY_PACKAGES = ["matplotlib", "marimo", "jupyter", "faker", "pytest"]


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
    )


def test_package_imports():
    """Bare `import grader_helper` must succeed."""
    result = _run("import grader_helper")
    assert result.returncode == 0, (
        f"import grader_helper failed:\n{result.stderr}"
    )


@pytest.mark.parametrize("package", DEV_ONLY_PACKAGES)
def test_package_does_not_import_dev_only_dependency(package):
    """Importing grader_helper must not pull in a dev-only package.

    Regression guard for the stray `from matplotlib.pylab import f` in
    dataframe_operations/__init__.py. matplotlib was correctly dropped from
    the runtime dependencies, so that import makes a published release fail
    at import time for every user on every platform -- while remaining
    invisible in a dev environment, where matplotlib is installed.
    """
    result = _run(
        f"""
        import sys
        import grader_helper
        assert "{package}" not in sys.modules, (
            "grader_helper imported {package}, which is not a runtime dependency"
        )
        """
    )
    assert result.returncode == 0, result.stderr.strip().splitlines()[-1]


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
