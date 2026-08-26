# Development notes

Decisions, hard-won facts, and where the work stands. Written for whoever
picks this up next — including future me.

## Conventions

```python
import pathlib as pl        # pl is pathlib
import polars as pr         # pr is polars (not yet in use)
```

House convention, non-negotiable. Note it inverts the usual polars idiom, so
public docstrings should show the import line.

**Supported platforms: Windows first-class, macOS second. Linux is not a
target** — though the pure-logic tests run there, which is what makes CI and
container work possible.

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

Done, on `claude/repo-review-98isz0`, 191 tests:

- Platform handling corrected — COM init is the only OS conditional; xlwings
  works on macOS too, so it must not be gated on Windows
- `tests/` untracked from `.gitignore`; CI on windows-latest + macos-latest
- Characterisation suite over scoring, grades, allocation, folder naming
- 2026 grade bands; Excel-compatible rounding
- Group allocation by `Group` column (was a MultiIndex nothing produced)
- `import_brightspace_classlist(group=True)` strips `#`; finds the group
  column however named; refuses a class list with ungrouped students
- `Person` / `Assessment` / `Module` models and `module.toml` round-tripping

### Next

1. **`init_module`** — write a starter `module.toml` with the explanatory
   comments in place
2. **Rewire the three component-dependent functions** to read from `Module`
   rather than regexing column names. This is what unblocks the departmental
   file:
   - `calculate_total_module_score` — currently **drops `MCQ (10)` from the
     total** (returns 63 where the sheet says 70), because it only counts
     columns containing "Coursework"
   - `sort_order_columns` — drops 4 of the 10 departmental columns
   - `prepare_data_for_departmental_template` — passes only the `(100)`
     columns to `check_for_weighted_columns`, so it always reports them
     missing; and calls `make_letter_grade(df)` with a DataFrame when that
     takes a scalar
3. **Quiz collection** — Kev has separate code for this
4. **Polars migration** — only once the above are correct
5. **Marimo dashboard** — library-first; `marimo run` gives a code-free app
   view, which is the non-technical-colleague story

### Untested, and needing care

`distribute_feedback_sheets`, `save_grader_sheets`, `save_distributed_graders`,
`ingest_completed_graderfiles`. All write Excel; all need covering before
polars goes near them.

### Known gaps

- `make_sub_date` cannot parse `"0000 AM"` (`%I` is 12-hour). Brightspace
  appears to use `"1200 AM"`, so it may never bite. `xfail`.
- `sort_order_columns` cannot handle the full departmental layout. `xfail`,
  and resolved by item 2 above.
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
