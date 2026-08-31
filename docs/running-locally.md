# Running this version locally (Windows)

For testing the `develop` branch on your own machine. PowerShell throughout;
`uv` does the Python and dependency work, so you never activate a venv by
hand.

Verified against Python 3.13 and the CI setup in `.github/workflows/test.yml`.

## 1. Prerequisites

You need `git` and `uv`. Check:

```powershell
git --version
uv --version
```

If `uv` is missing:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen PowerShell afterwards so `uv` is on `PATH`. You do **not**
need to install Python yourself — step 3 does it.

## 2. Get the code

**First time**, clone and switch to `develop`:

```powershell
cd $HOME\Documents          # or wherever you keep projects
git clone https://github.com/spider-z3r0/grader_helper.git
cd grader_helper
git switch develop
```

**Already have a clone**, update it:

```powershell
cd $HOME\Documents\grader_helper
git fetch origin
git switch develop
git pull origin develop
```

If `git switch develop` says the branch is unknown, your clone predates it —
`git fetch origin` first, then try again.

Confirm you are on the right commit:

```powershell
git log --oneline -1
git status --short --branch
```

You want `develop` and a clean tree.

## 3. Install

```powershell
uv python install 3.13
uv sync --group dev
```

`uv sync` creates `.venv\` in the repo and installs everything from
`uv.lock`, so you get exactly the versions CI uses. The `--group dev` brings
in pytest, marimo and faker.

On Windows this also installs `xlwings` and `pywin32`, which drive Excel via
COM. They install whether or not Excel is present; nothing here needs Excel
running.

## 4. Verify

```powershell
uv run pytest -q
```

Expect **276 passed, 1 xfailed**. The xfail is `make_sub_date` on `"0000 AM"`
and is deliberate.

To match CI exactly (it deselects tests needing a real Excel install):

```powershell
uv run pytest -q -m "not excel"
```

Same result today — there are no `excel`-marked tests yet.

Useful variations:

```powershell
uv run pytest -q tests\test_end_to_end.py      # the whole pipeline
uv run pytest -q -k departmental               # anything matching a name
uv run pytest -v tests\test_end_to_end.py      # one line per test
```

## 5. Generate a module to play with

This writes a complete fake module to disk — `module.toml`, a Brightspace
class-list export, submission folders in Brightspace format, and **real
`.xlsx` feedback sheets with marks in `D30`**:

```powershell
uv run python tests\fake_module.py $HOME\Documents\scratch\PS4001
```

It prints where everything went. Have a look:

```powershell
cd $HOME\Documents\scratch\PS4001
Get-Content module.toml
Get-ChildItem -Recurse -Directory | Select-Object -First 20
Get-ChildItem -Recurse -Filter "Feedback sheet *.xlsx" | Select-Object -First 5
```

Open one of the feedback sheets in Excel and you will find the mark in `D30`.
The cohort is fixed, not random — 12 students, including one who never
submitted, one who submitted twice, an id with a leading zero, and one whose
total lands on exactly 64.5.

Regenerate any time; pass a different path or delete the folder first.

## 6. Explore it in marimo

```powershell
uv run marimo edit
```

That opens marimo in your browser. Make a new notebook and paste this in — it
is the walkthrough, already verified end to end:

```python
import pathlib as pl
import sys

import pandas as pd

sys.path.insert(0, "tests")          # so `fake_module` is importable
from fake_module import make_fake_module

from grader_helper import (
    calculate_weighted_score,
    catch_grades,
    import_brightspace_classlist,
    load_module,
    prepare_data_for_departmental_template,
    scan_multiple_subs,
)

fake = make_fake_module(pl.Path.home() / "Documents" / "scratch" / "PS4001_nb")
module = load_module(fake.root)

# Paths come off the model: a.submissions_path, a.grading_output_path,
# a.rubric_path -- no arguments, no hand-built strings.

classlist = import_brightspace_classlist(fake.classlist)

df = classlist[["Student ID", "Last Name", "First Name"]].copy()
df["Name"] = df["First Name"] + " " + df["Last Name"]
df = df[["Student ID", "Name"]]

for assessment in module.assessments:
    marks = catch_grades(
        fake.submissions[assessment.id], fake.grade_cell
    ).rename(columns={"grade": assessment.raw_column})
    df = df.merge(marks, on="Student ID", how="left")

for assessment in module.assessments:
    if assessment.needs_weighting:
        calculate_weighted_score(df, assessment.raw_column, assessment.weight_fraction())

sheet = prepare_data_for_departmental_template(df, module)
sheet
```

Run `uv run marimo edit` **from the repo root** — the `sys.path.insert` above
is relative to it.

`scan_multiple_subs(fake.submissions["cw1"])` will show you the resubmitter.

When you have something worth keeping, `marimo run <notebook>.py` serves it as
an app with the code hidden, which is the non-technical-colleague view.

## 7. Open a real module

The walkthrough above builds a fake module to practise on. To work on a real
one:

```powershell
uv run marimo run notebooks\module_dashboard.py
```

`marimo run` serves it with the code hidden, which is the view to give a
colleague; `marimo edit` opens the same file with the code visible.

Choose the module's folder in the browser at the top — the one for a single
year of a single module, `OneDrive\teaching\2026\Sem1\PS4034`. If a
`module.toml` is in there it loads and the page shows the module: its
assessment, its weights, the columns each piece produces, what has been done
so far, and whether the folders it names exist. If the folder is empty you
get a form instead: how many pieces of assessment, then the two numbers for
each, and a button that writes `module.toml` and creates the folders.

Clicking down from your home folder to a module gets old. Set the browser's
starting point once:

```powershell
$env:GRADER_HELPER_START = "$env:OneDrive\teaching"
uv run marimo run notebooks\module_dashboard.py
```

`$env:GRADER_HELPER_MODULE` goes further and opens straight onto one module
folder. Neither is stored by grader_helper — `module.toml` is the only file
it writes, and it holds no absolute paths, so a module folder still works
after OneDrive syncs it to another machine.

If a `module.toml` is there but will not load, the page shows the error and
the path to edit, and does **not** offer to set the folder up again. That is
deliberate: the file holds the graders, the quiz rules and everything
recorded about progress. Fix the line it complains about, then click
**Re-read this folder**.

## Troubleshooting

**`uv` not recognised** — reopen PowerShell after installing it; the installer
edits `PATH` and the current session will not have picked it up.

**Script execution disabled** — you should not need to activate anything if
you use `uv run`. If you do want the venv active:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

`-Scope Process` lasts only for that window, which is the safe way to do it.

**`ModuleNotFoundError: fake_module`** — you are not in the repo root, or you
missed the `sys.path.insert(0, "tests")` line.

**`ModuleNotFoundError: grader_helper`** — you are running bare `python`
rather than `uv run python`, so the venv is not in play.

**Tests fail on a fresh clone** — check `uv sync --group dev` finished without
error, and that `git status` shows a clean tree on `develop`.

**Long paths.** The generated folder names are long, and OneDrive paths are
long to begin with. If you hit path-length errors, generate the fake module
somewhere short like `C:\dev\PS4001` rather than under OneDrive.

## What to expect, and what not to

Working end to end: module init, class-list import, resubmission detection,
grader assignment, feedback-sheet distribution, reading marks out of real
workbooks, and the departmental grade sheet.

Not covered, so treat with suspicion:

- **`brightspace_name_folders`** — no tests at all. It is the last step before
  re-upload. Note it takes the *rename log* written by `alphabetise_folders`
  (read back from `folder_rename_log.csv`), not the class list, and
  `alphabetise_folders` returns `None` — the handoff is a file, not a value.
- **No moderation pack.** Nothing samples submissions by letter grade yet.
