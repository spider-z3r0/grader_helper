# grader_helper — start here

Tooling for running assessment on a UL psychology module: Brightspace
downloads in, departmental grade sheet out.

**Read this file, then stop.** `docs/development-notes.md` is ~6k tokens and
covers everything; read only the section you need, using the map below.
Reading it whole at the start of every session is the main way context gets
wasted here.

## Before you touch anything

- **Work on `develop`.** Do not create a new branch. Sessions are assigned a
  fresh `claude/<slug>` by default — ignore it and switch to `develop`.
  It merges to `main` when a chunk is green.
- **`uv run pytest -q`** is the suite. It should be green before and after
  you touch anything; the count is in the notes' "Where the work stands".
- **`uv run`, never bare `python`.** The venv is not on the path.

## Non-negotiables

```python
import pathlib as pl        # pl is pathlib
import polars as pr         # pr is polars
```

House convention, and it inverts the usual polars idiom, so public docstrings
should show the import line.

- **Windows is first-class. macOS is supported wherever that costs Windows
  nothing.** Linux is not a target, though the pure-logic tests run there.
- **The departmental grade sheet is the source of truth.** Where our
  arithmetic and the sheet disagree, the sheet wins.
- **`excel_round`, never Python's `round`.** Python rounds half to even,
  Excel half away from zero. On an exact half that is a different letter
  grade.
- **Nothing absolute is stored in `module.toml`.** These modules live under
  OneDrive; absolute paths break the moment they sync elsewhere.

## Where to look

| working on | read |
|---|---|
| anything domain-shaped | **The domain** — roles, lifecycle, moderation |
| grades, bands, rounding | **Sources of truth** |
| `module.toml`, models, paths | **module.toml**, **The assessment folder layout** |
| Brightspace folder names | **Sources of truth → Brightspace formats** |
| the Excel read/write functions | **The Excel round trip** |
| writing the departmental sheet | **Building the departmental sheet** |
| moderation samples, borderline | **Moderation packs** |
| the SI upload file | **The SI upload** |
| status flags, `record()` | **Keeping status** |
| quizzes, pass marks, free passes | **Quiz collection** |
| group work, group marking | **Group work** |
| the dashboard / app | `docs/dashboard-scope.md` first, then **Pointing at a folder** |
| what to build next | **Next** |
| something looks broken | **Known gaps** — it may be known |

All in `docs/development-notes.md` unless a path is given.
`docs/running-locally.md` is the Windows setup and marimo walkthrough; you
rarely need it. `docs/dashboard-scope.md` is the scope for the app and is
where a session about it starts.

## House practices

- **Verify a guard by reintroducing the bug.** A test that has never been
  seen to fail is not yet a test. This catches bad tests, not just bad code —
  it has already caught two here.
- **`xfail(strict=True)`**, so a fixed bug turns the marker into a failure
  and stale markers cannot accumulate.
- **The container is a bad oracle for packaging.** It accumulates whatever
  gets installed while exploring, so an undeclared dependency looks fine here
  and breaks on a clean machine. Two guards exist; do not weaken them, add
  the dependency.
- **Say what you actually verified.** This project has a habit of writing
  down what was checked and how, in commit messages and in the notes. Keep
  it.

## Things that are easy to get wrong

- `catch_grades` and `ingest_completed_graderfiles` are **not alternatives**.
  They are two halves of one audit run by different people. See **The
  domain**.
- `alphabetise_folders` returns `None` and writes `folder_rename_log.csv`;
  the handoff to `brightspace_name_folders` is that file, not a value.
- The departmental sheet's weighting formula **divides by a whole number
  where it can** (`=E30/2`, not `=E30/100*50`). The long form looks tidier
  and moves marks: `x/2` is exact in floating point and `x/100*50` is not,
  and the total is rounded. See **Building the departmental sheet**.
- `notebooks/grading_walkthrough.py` is deliberately plain and explicit, with
  each assessment written out in full. Do not "improve" it into a selector;
  that is scheduled, and not yet.
