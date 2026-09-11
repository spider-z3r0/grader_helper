"""Launches the module dashboard for someone who only has the package.

``uv tool install grader-helper`` gives you this package and its runtime
dependencies in an isolated venv, with only the entry points declared in
``[project.scripts]`` put on PATH -- not a git clone, not ``notebooks/``.
The dashboard notebook itself ships as a copy inside the package (see the
``force-include`` in pyproject.toml, and ``main()`` below finds that copy
and hands it to marimo.

Runs marimo as ``sys.executable -m marimo`` rather than relying on a
``marimo`` command being on PATH: `uv tool install` does not expose console
scripts from a dependency, only from the installed package itself.
"""

import subprocess
import sys
from importlib import resources


def main() -> None:
    resource = resources.files("grader_helper") / "_dashboard_app.py"
    if not resource.is_file():
        raise FileNotFoundError(
            "The dashboard notebook is missing from this install "
            f"({resource}). This is a packaging bug, not something to work "
            "around -- reinstall grader-helper."
        )
    # `as_file` stays open for the subprocess call, not just path
    # resolution: for a zip-backed install it materialises a temp copy that
    # is only guaranteed to exist inside this block.
    with resources.as_file(resource) as notebook:
        subprocess.run(
            [sys.executable, "-m", "marimo", "run", str(notebook)], check=True
        )


if __name__ == "__main__":
    main()
