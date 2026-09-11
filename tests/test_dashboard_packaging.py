#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""`grader-dashboard` must find the notebook in a real built wheel.

The container is a bad oracle for packaging: `uv sync` installs this project
straight from the source tree, so a dev environment has notebooks/
module_dashboard.py on disk regardless of whether the force-include in
pyproject.toml is even spelled correctly. The only thing that tells the
truth is a real wheel build -- so this test builds one and looks inside it,
the same way the dev-only-import guards in test_import.py distrust the
container for undeclared dependencies.
"""

import shutil
import subprocess
import zipfile

import pytest


def test_wheel_contains_the_dashboard_notebook(repo_root, tmp_path):
    """The force-include must actually place the notebook in the wheel.

    Regression guard: `grader_helper/dashboard_launcher.py` looks for
    `grader_helper/_dashboard_app.py` via importlib.resources. If the
    [tool.hatch.build.targets.wheel.force-include] entry in pyproject.toml
    is ever removed, renamed, or mistyped, `grader-dashboard` fails for
    every `uv tool install` user -- the one audience this exists for -- and
    nothing in the dev environment would notice, because notebooks/
    module_dashboard.py is right there on disk regardless.
    """
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is not on PATH; cannot build the wheel to inspect it")

    result = subprocess.run(
        [uv, "build", "--wheel", "-o", str(tmp_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"wheel build failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"

    with zipfile.ZipFile(wheels[0]) as wheel:
        names = wheel.namelist()
        assert "grader_helper/_dashboard_app.py" in names, (
            "notebooks/module_dashboard.py is not force-included into the "
            f"wheel as grader_helper/_dashboard_app.py. Wheel contents:\n"
            + "\n".join(sorted(names))
        )

        packaged = wheel.read("grader_helper/_dashboard_app.py").decode()
        source = (repo_root / "notebooks" / "module_dashboard.py").read_text()
        assert packaged == source, (
            "the packaged dashboard notebook does not match "
            "notebooks/module_dashboard.py -- force-include is pulling "
            "from somewhere else, or the packaged copy is stale"
        )
