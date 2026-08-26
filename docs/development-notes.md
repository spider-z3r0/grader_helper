# Development notes

Decisions, hard-won facts, and where the work stands. Written for whoever
picks this up next — including future me.

## The aim

**Mature this into a library on polars, and a marimo dashboard on top of it.
The library is for technical users; the dashboard is for everyone else.**

Two audiences, one codebase:

- **The library** — importable, scriptable, for colleagues who are happy in
  Python. This is what has to be correct, because the app inherits whatever
  it gets wrong.
- **The dashboard** — a marimo app for colleagues who should never have to
  see a line of code. `marimo run` serves a notebook as an app with the code
  hidden, which is the whole reason marimo is the choice: one artefact is
  both the development surface and the delivered tool.

Library first, always. The dashboard is a view onto the library, never a
place where logic lives — anything the app can do, a script must be able to
do too.

### Platforms

**Windows is first-class. macOS is supported wherever that costs Windows
nothing, and is dropped the moment it would.** Linux is not a target, though
the pure-logic tests run there, which is what makes CI and container work
possible.

That rule is a tie-breaker, not a grudge: where a single approach serves
both, use it. `xlwings` is the case in point — it drives Excel via COM on
Windows and AppleScript on macOS, so gating it on Windows alone was a
defect, not a simplification.

### Sequencing

Correctness, then polars, then the app. The migration waits on the
Excel-writing functions being covered by tests (see **Untested, and needing
care**) — porting code whose behaviour nothing pins down is how silent
breakage gets in.

Two practical notes for whoever starts the migration:

- **polars is not declared in `pyproject.toml` yet.** The packaging guard
  refuses an import the package does not declare, so `pr` will fail the
  suite until it is added to `dependencies`. That guard is working as
  intended; add the dependency, do not weaken the test.
- **marimo is a dev dependency.** It stays that way while the app is
  developed. Shipping the dashboard to end users means promoting it to a
  runtime dependency, probably behind an optional extra so library users do
  not pull in an app framework they will never launch.

## Branches

**`develop` is the one long-lived branch.** Work goes there; it merges into
`main` when a chunk is finished and green. `models` is a parked archive from
August 2025 — the earlier YAML/src-layout attempt, superseded by the
pydantic and `module.toml` models — kept for reference, not for building on.

Claude Code sessions are assigned a fresh `claude/<slug>` branch by default,
which is how five branches accumulated. **Tell each new session to work on
`develop` and not create its own.** Consolidating afterwards is avoidable
work.

## Conventions

```python
import pathlib as pl        # pl is pathlib
import polars as pr         # pr is polars (not yet in use)
```

House convention, non-negotiable. Note it inverts the usual polars idiom, so
public docstrings should show the import line.

## Sources of truth

**The departmental grade sheet is authoritative**, because it is verifiable
outside this code: anyone can open it and read the grades. Where our
arithmetic and the sheet disagree, the sheet wins. `Dept_grade_sheet_Template_2026.xlsx`,
tab `GradeTemplate`.

Its 20 sample rows are committed as `tests/resources/gradetemplate_samples.csv`
with the values Excel itself computed. `tests/test_departmental_golden.py`
asserts we reproduce every one.

### Grade bands (2026 scale)

From the `EHS grades UG modules` tab and `GradeTemplate` rows 7–17. Defined
once in code as `GRADE_BANDS`, each carrying award equivalent and QPV.

| Band | ≥ | Award | QPV |
|---|---|---|---|
| A1 | 80 | First Honours | 4.0 |
| A2 | 75 | First Honours | 3.6 |
| B1 | 70 | Honours 2.1 | 3.2 |
| B2 | 65 | Honours 2.1 | 3.0 |
| B3 | 60 | Honours 2.2 | 2.8 |
| C1 | 55 | Honours 2.2 | 2.6 |
| C2 | 50 | Third Honours | 2.4 |
| C3 | 40 | Third Honours | 2.0 |
| D1 | 35 | Compensated Fail | 1.6 |
| F | 0 | Fail | 0.0 |

Changed from the previous scale: **D2 retired**, C3 widened to 40–50, D1
shifted to 35–40, F lost its lower bound.

`NG` means **no participation**, not a very low mark. The sheet computes
`IF(ROUND(total,2) > 0, <bands>, "NG")` and excludes NG from the average QPV.
So exactly 0 → NG; anything above 0 below the threshold → F.

### Rounding — two rules, both grade-affecting

**Round the total, never the components.** The sheet stores `D = C/100*40`
as `29.6` and rounds only at `H = ROUND(SUM(D,F,G), 0)`. Rounding each
component instead shifts totals and can cross a band boundary. This also
keeps the student's reported mark and the audited mark in step: a student
told they scored 66.5 has 66.5 carried into the grade sheet.

**Use `excel_round`, not Python's `round`.** Python, numpy and pandas all use
banker's rounding (half to *even*); Excel's `ROUND` goes half *away from
zero*. On the sample data, `64.5` → Python 64 (B3), Excel 65 (**B2**).

### Brightspace formats

Submission folder names:

```
27236-46025 - 23304308 Angood - 05 March 2026 612 PM
|             |        |        |
|             |        |        submission timestamp
|             |        surname
|             student ID   <-- everything orients on this
Brightspace's own id, changes per assignment
```

The student ID is the **first token after the first `" - "`**. The README's
old example is out of date and puts the name where the ID goes.

Class list export columns: `OrgDefinedId, Username, Last Name, First Name,
Email, End-of-Line Indicator`. `Username` carries a leading `#`
(`#56170559`); the student ID is that with the `#` stripped.

## module.toml

Config the author writes, plus state the tool writes. Two rules keep a save
from damaging a hand-edited file — both discovered by watching it break:

1. **Only keys already in the file are updated.** Appending a key or
   sub-table places it after that table's trailing comment, and tomlkit
   binds trailing comments to the *preceding* table — so a comment
   introducing the next section silently migrates into the previous one.
2. **`[status.<id>]` lives in its own section**, appended at the end of the
   document where there is nothing to displace. `[module]`, `[paths]` and
   `[[assessment]]` are the author's and are only read or updated in place.

Tests assert the author's sections come back byte-identical with only
`[status]` added, and that every comment survives.

### The two-numbers rule

An assessment carries `marks_out_of` and `weight`. Every grade-sheet column
falls out of those, so the code is *told* a module's shape rather than
inferring it from column-name regexes:

| | marks_out_of | weight | columns |
|---|---|---|---|
| Coursework 1 | 100 | 40 | `Coursework 1 (100)`, `Coursework 1 (40)` |
| MCQ | 10 | 10 | `MCQ (10)` — one column |

Ten weekly quizzes, each pass worth 1%, are **one** assessment marked out of
10 and worth 10 — the quiz count and the marks available are the same number,
so no extra field is needed.

Paths are relative to `module.toml`; the root is the file's own directory.
Nothing absolute is stored, because these live under OneDrive where absolute
paths differ per machine.

## Where the work stands

Done, 218 tests:

- Platform handling corrected — COM init is the only OS conditional; xlwings
  works on macOS too, so it must not be gated on Windows
- `tests/` untracked from `.gitignore`; CI on windows-latest + macos-latest
- Characterisation suite over scoring, grades, allocation, folder naming
- 2026 grade bands; Excel-compatible rounding
- Group allocation by `Group` column (was a MultiIndex nothing produced)
- `import_brightspace_classlist(group=True)` strips `#`; finds the group
  column however named; refuses a class list with ungrouped students
- `Person` / `Assessment` / `Module` models and `module.toml` round-tripping
- The four grade-sheet functions read from `Module` instead of regexing
  column names — see below
- `init_module` writes a starter `module.toml`, comments and all

### The rewire onto `Module`

The departmental file is unblocked. `sort_order_columns`,
`check_for_weighted_columns`, `calculate_total_module_score` and
`prepare_data_for_departmental_template` now take a `Module` and are *told*
the sheet's shape. The `Module` argument is **required**: the inference path
is gone rather than kept as a fallback, because it either crashed or produced
wrong totals, and leaving it reachable would mean testing it forever.

What that fixed:

- `calculate_total_module_score` sums `weighted_column or raw_column` per
  assessment. An MCQ out of 10 worth 10 has no weighted column, so its raw
  mark *is* its contribution — which is exactly the component the old
  `"Coursework"`-substring filter dropped. Row 30 of the sample data was
  returning 63 (B3) where the sheet says 70 (B1).
- `prepare_data_for_departmental_template` maps `make_letter_grade` over the
  totals instead of calling it with the DataFrame. It previously raised
  `ValueError("Score must be an integer or float.")` on every run — the main
  entry point could not complete at all.
- `sort_order_columns` builds the departmental order from
  `module.grade_sheet_columns` and **never drops a column**: anything the
  module does not describe is appended rather than discarded. The old version
  lost 4 of the sheet's 10 columns.
- `check_for_weighted_columns` is given the full column list and reports real
  names (`Coursework 1 (40)`), not guesses (`Coursework 1`).

Two things worth knowing:

- **Ordering is now the author's declared order in `module.toml`**, not
  "coursework number ascending, weight descending". For the departmental
  layout the two agree; declared order is the rule that generalises.
- **A blank mark counts as zero**, matching Excel's `SUM` in the sheet. A
  student blank throughout totals 0, which is `NG` — no participation, which
  is what a row of blanks means.

`tests/test_departmental_golden.py` now runs the 20 sample rows end to end
through `prepare_data_for_departmental_template` and asserts every total,
every letter grade and the column layout against what Excel computed. All
three defects above were re-introduced one at a time and watched to fail
before the change was committed.

### `init_module`

Writes a starter `module.toml` whose comments carry what the keys cannot:
the two-numbers rule, the worked example of when an assessment gets two
columns and when it gets one, and the fact that weights must sum to 100.
`models/module_file.py` had told users to "Run init_module() to create one"
since the models landed; the promise is now kept.

Two things it refuses, both deliberate:

- **It will not replace an existing file.** That file is the module's
  memory — assessment, graders, and everything recorded about progress — so
  overwriting it takes an explicit `overwrite=True`.
- **It validates before writing.** The text is parsed and run through the
  same `_to_module` path that reads a file back, so a starter file that
  would not load never reaches the disk. Weights that do not sum to 100
  raise, and the directory is left empty.

The default shape is the departmental one — cw1 (100/40), cw2 (100/50), MCQ
(10/10) — chosen because it sums to 100, so the file loads before it is
edited, and because it shows both the two-column and one-column cases in a
file the author is already reading.

Validation was extracted out of `ModuleFile.load` into `_to_module` so both
the reader and the writer use it. A file this package writes is therefore
checked by exactly the path that reads it back.

### Next

1. **Quiz collection** — Kev has separate code for this
2. **Polars migration** — only once the above are correct; see
   **The aim → Sequencing** for what it is gated on
3. **Marimo dashboard** — the non-technical-colleague story, built strictly
   on top of the library

### Untested, and needing care

`distribute_feedback_sheets`, `save_grader_sheets`, `save_distributed_graders`,
`ingest_completed_graderfiles`. All write Excel; all need covering before
polars goes near them.

### Known gaps

- `make_sub_date` cannot parse `"0000 AM"` (`%I` is 12-hour). Brightspace
  appears to use `"1200 AM"`, so it may never bite. `xfail`.
- `assignment/visualise.py` defines its function inside `main()`, so it is
  unreachable and unexported. Delete or fix; do not port.
- A `.pyc` is tracked despite `.gitignore` listing `__pycache__/`. Ignore
  rules do not apply to already-tracked files: `git rm --cached` it.

## Working practices that earned their keep

- **The container is a bad oracle for packaging.** It accumulates whatever
  gets installed during exploration, so an undeclared dependency looks fine
  there and breaks on a clean machine. Two guards now exist: the package may
  not import what it does not declare, nor what is declared dev-only.
- **`xfail(strict=True)`** — a fixed bug turns the marker into a failure, so
  stale markers cannot accumulate.
- **Verify a guard by reintroducing the bug.** A test that has never been
  seen to fail is not yet a test.
