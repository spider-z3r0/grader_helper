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

Correctness, then polars, then the app. The Excel-writing functions that
gated the migration are now covered and repaired (see **The Excel round
trip**), so polars is unblocked — the round-trip tests are what a port has
to keep passing.

Two practical notes for whoever starts the migration:

- **polars is not declared in `pyproject.toml` yet.** The packaging guard
  refuses an import the package does not declare, so `pr` will fail the
  suite until it is added to `dependencies`. That guard is working as
  intended; add the dependency, do not weaken the test.
- **marimo is a dev dependency.** It stays that way while the app is
  developed. Shipping the dashboard to end users means promoting it to a
  runtime dependency, probably behind an optional extra so library users do
  not pull in an app framework they will never launch.

## The domain

What the software is modelling. Written down because none of it is guessable
from the code, and getting it wrong produces plausible output rather than an
error.

### The people

| role | does |
|---|---|
| **Grader** | Marks submissions. May be the module leader or someone else. |
| **Module leader (ML)** | Owns the module. Allocates graders, collates marks, verifies internally, assembles moderation packs, submits final marks. |
| **Internal moderator** | A member of staff **not on the teaching team**. Reviews a sample of the marked work. |
| **External examiner** | Outside the institution. Takes a view of the whole module at the end. |

`Module.leader` and `Module.internal_moderator` exist as `Person` fields.
There is no field for the external examiner yet.

### The lifecycle of one assessment

1. **Download** the submissions from Brightspace and unzip them.
2. **Alphabetise** the folders into UL format, so they sort by surname.
   Refuses while any student has more than one submission — resolving those
   is a judgement call.
3. **Allocate** graders across the class list. Written to
   `distributed.xlsx` at the assessment root, and to one workbook per grader
   in `grading_output/`.
4. **Distribute** a blank feedback sheet into each student's folder.
5. **Grader marks.** The feedback sheet *calculates* a final score in its
   grade cell, and the grader **copies that value** into their own grade
   sheet.
6. **ML collates.** `ingest_completed_graderfiles` concatenates the grader
   sheets into `completed_grades.xlsx` — a filled-in `distributed.xlsx`.
7. **ML reconciles.** `catch_grades` reads the feedback sheets and the two
   records are compared. **Step 5 is a manual copy, and this is the control
   that catches it going wrong.** The student receives the feedback sheet;
   the department receives the collated file; they must agree.
8. **ML verifies internally** — usually by second-marking *n* submissions
   per grader. A check on the graders, done inside the teaching team.
9. **Internal moderation** — see below.
10. **Rename** the folders back to Brightspace format for re-upload.

Steps 1–7 and 10 exist in code. Steps 8 and 9 do not.

### Moderation

Internal and external moderation are closely related, and the relationship is
the thing to get right: **the external pack is assembled from the internal
packs, not sampled separately.**

**Internal moderation** happens per assessment, once the ML has collated and
internally verified. The pack goes to a member of staff who is *not* on the
teaching team, and contains two things:

- a **random selection of *n* submissions per grade band**, where *n* depends
  on the size of the cohort; and
- **any cases the ML flags** for a second opinion — typically a student
  sitting on a boundary that matters, an A2 that might be an A1, or a mark
  that might be a pass or a fail.

So a pack is `sample per band` + `ML-flagged cases`. Two sources, one pack.
The flagged cases are the ML's judgement and cannot be derived from the
marks alone, so whatever builds the pack has to accept them as input.

**External moderation** happens once the whole module is complete. The
external examiner is sent a pack containing **all of the internal moderator
packs**, so they can take a higher-level view across the module rather than
assessment by assessment.

That has a direct consequence for how this gets built: internal packs are
the unit of work, and the external pack is an assembly step over them. Build
the internal pack well and the external one is mostly collection. It also
means internal packs must be *kept*, not discarded once the internal
moderator reports back.

Open decisions, both the ML's to make rather than the tool's:

- **what *n* is**, as a function of cohort size
- **what counts as a band for sampling** — the ten letter grades, or coarser
  groupings

`Assessment.status.moderated` is the only hook that exists today.

### Where a mark can go wrong

Worth keeping in view, because most of the checks in this package exist for
one of these:

- **The transcription at step 5.** A human copying a number. Caught by the
  reconciliation at step 7.
- **Excel round-tripping the student id.** `'00123456'` reads back as
  `123456`; merging then raises rather than mismatching quietly. Id columns
  are read as text explicitly.
- **Rounding.** Excel rounds half away from zero, Python half to even. On an
  exact half that is a different letter grade.
- **Dropping a component.** A total that misses an assessment is still a
  plausible number. The `Module` knows what to sum, so it cannot silently
  omit one.
- **A resubmission.** Two folders, one student; whichever feedback sheet is
  found gets read. Resolve before marking, not after.

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
import polars as pr         # pr is polars
```

House convention, non-negotiable. Note it inverts the usual polars idiom, so
public docstrings should show the import line. In use since quiz collection,
which is the first module written in polars.

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

1. **Only keys already in the file are updated** — by `save`. Appending a
   key or sub-table places it after that table's trailing comment, and
   tomlkit binds trailing comments to the *preceding* table, so a comment
   introducing the next section silently migrates into the previous one.
   `set_assessment` and `set_paths` *can* add a key, by inserting above that
   trivia rather than after it — see **Where the group sheets are**. `save`
   itself stays conservative.
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

Done, 747 tests on Linux and 748 with a real Excel:

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
- `init_module` writes a starter `module.toml`, comments and all, and
  creates the folders it describes
- The assessment folder layout is modelled — see below
- The departmental sheet is built for whatever assessments a module has,
  and rebuilding the template's own shape reproduces it cell for cell — see
  **Building the departmental sheet**
- The four Excel-writing functions covered and repaired — see below
- A whole fake module on disk, and an end-to-end test over it
- Quiz collection: a folder of Brightspace quiz exports folded into one
  mark, with the rules recorded in `module.toml` -- see below. The first
  polars in the package
- `collate_module_marks`: a whole module's marks in one frame, whatever
  kind of assessment they came from -- see below
- `inspect_module_folder` and the **module dashboard**: point the tool at a
  folder and it loads the module there or offers to set one up -- see
  **Pointing at a folder**
- The dashboard runs a whole module end to end: resolve resubmissions,
  allocate, distribute, collect and reconcile, rename back, collect the
  quizzes, collate, the departmental sheet, the moderation pack and SI's
  upload. See **Running an assessment from the app**
- `reconcile_marks` and `resolve_multiple_subs`: two steps that existed only
  as notebook code, one of which was subtly wrong
- Group assessments: the two kinds distinguished in `module.toml`, the
  leader's own group sheets collected, and allocation wired to the
  assessment -- see **Group assessments**
- `simulate-marking`: fills in marks nobody marked, on both records and
  with deliberate discrepancies, so everything after marking can be run.
  Takes a module or a pair of folders -- see **Simulating the marking**

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

### Pointing at a folder

The first thing anyone does, and the front door to `init_module`. Two pieces:
`inspect_module_folder` in `models/module_folder.py`, and
`notebooks/module_dashboard.py` on top of it.

**Four answers, not two.** `ModuleFile.load` raises `FileNotFoundError` for
"nothing here" and a `ValidationError` for "a module.toml that will not
load", and a caller that catches both in one `except` cannot tell them
apart -- yet they need opposite offers:

| state | what it is | what is offered |
|---|---|---|
| `LOADED` | a module.toml that loaded | the module |
| `UNINITIALISED` | a directory with no module.toml | the setup form |
| `UNREADABLE` | a module.toml that will not load | the error, and the path to edit |
| `MISSING` | nothing at that path | "check the path" |

`can_initialise` is true for `UNINITIALISED` **only**. A broken file is
deliberately excluded: `init_module` refuses to overwrite, so offering setup
there would mean `overwrite=True`, and that file holds the graders, the quiz
rules and every status flag recorded so far. A mistyped weight is fixed by
correcting the weight.

`inspect_module_folder` never raises. Whatever a hand-edited TOML does wrong
-- malformed syntax, a future `schema_version`, the wrong encoding -- the
caller's move is the same, so it is returned as data. That is what lets a
dashboard cell call it on every click without being able to crash the page.

**The dashboard has no memory, by design.** No recents list, no stored
teaching root, no config file: you say which module you are on by choosing
its folder. Two environment variables exist -- `GRADER_HELPER_START` opens
the browser somewhere other than home, `GRADER_HELPER_MODULE` preselects a
folder -- and neither is written by anything. `module.toml` stays the only
file this package writes, and it still holds nothing absolute.

Three things worth knowing about the form:

- **The offer decision is made once.** `offer` is computed in one cell and
  used by the five below it. A copy per cell is a copy that can disagree,
  and the dangerous disagreement is a cell offering to overwrite the
  module.toml the cell above it just reported as broken.
- **The collection rules follow a tick, not the type.** `pass_mark` and
  `free_passes` are written only when a row is ticked *collected from
  Brightspace exports*. Inferring from the type looks tidy and is wrong: an
  MCQ may be collected or marked by hand, the type does not say which, and
  an MCQ that acquires a pass mark of 80 by default is scored as one quiz
  passed -- worth a single mark -- instead of read straight off. Which types
  may be ticked is `COLLECTED_TYPES`, lifted out of the validator that
  enforces it so the form and the model cannot drift.
- **Validation stays in the model.** The form shows the running weight total
  and nothing else; everything that can be wrong is caught by `init_module`,
  which validates before it touches the disk, and its message is displayed.
  Nothing is written when it refuses.

**What the page shows for a loaded module** is its assessment, the columns
each piece produces, per-assessment progress, and the module's own flags —
written beside sent, kept apart, because the code can see that it wrote the
departmental sheet and only a person knows whether it reached the
department. See **Keeping status**.

**One marimo trap, found here and worth knowing.** `mo.md` dedents a block
by its common leading whitespace, so a multi-line value interpolated at
column zero into an indented f-string sets that common indent to nothing and
leaves every following line over-indented — and markdown renders the
headings after it as paragraphs and the tables as text. It fails silently,
and only in the browser. The summary is therefore built as a list of lines
at column zero and joined, and the test asserts on the rendered HTML rather
than on the values the cell defined.

**The form collects what the marking steps read**: graders, the blank
feedback sheet and the cell the mark lands in, as well as the two numbers.
That is the difference between a module the page can display and one it can
run — allocation needs the graders, distribution needs the sheet, and
catching the marks needs the cell — so a module set up here needs no
hand-editing before the first step. What is left blank is left out of the
file rather than written empty: `graders = []` says nobody marks this, which
is an answer, where an absent key is a question not yet answered. The page
then names any assessment short of the three, and exempts the ones collected
from Brightspace, because nobody marks a quiz.

Verified by reintroducing nine bugs and watching the right tests fail:
treating an unreadable file as an empty folder (5 tests), `can_initialise`
as "anything not loaded" (1), offering setup for anything that did not load
(2), inferring collection from the type (2), the indented-f-string dedent
above (1), showing *written* in the *sent* column (1), taking the graders
field as one name rather than a comma-separated list (1), writing the blank
fields into the file anyway (1), and counting a quiz as not ready to mark
(1).

Not done here: the dashboard shows a module and sets one up, but does not
yet run a step against it. That is the next chunk.

### Running an assessment from the app

The dashboard's steps are functions, not code inside a button guard, and that
is the load-bearing decision. A test cannot click, so a step written into a
guard can only be checked by reading it. Written as
`allocate_marking(assessment, class_list, replace=False)` and friends, the
suite drives a whole module through exactly what a click calls --
`tests/test_dashboard_steps.py` runs a coursework from allocation to renamed
folders against a real module on disk, and the quizzes after it.

The order the page offers, which is the order the work happens in:

| | step | what it leaves behind |
|---|---|---|
| 1 | allocate the marking | `distributed.xlsx`, a workbook per grader |
| 1a | resolve multiple submissions | one folder per student |
| 2 | distribute the feedback sheets | a sheet in every folder, folders renamed |
| | *the graders mark* | |
| 3 | collect and reconcile | `completed_grades.xlsx`, the audit |
| 4 | rename the folders back | Brightspace's own names |
| — | collect the quiz marks | one column, for a collected assessment |
| 5 | collate the module | every mark in one frame, totalled and banded |
| 6 | the departmental sheet | the department's workbook, laid out and filled |
| 7 | the moderation pack | `Moderation/`, with its manifest and seed |
| 8 | SI's upload | SI's own file, two columns filled |
| 9 | the manual flags | moderated, sent, lodged |

Three things driving a real module surfaced, none of them in the page:

**Resubmissions block everything, and resolving them deletes work.**
`alphabetise_folders` refuses while a student has two folders -- both cannot
become `SURNAME, NAME(id)` -- so nothing downstream runs until one goes.
That step existed only in the walkthrough, where it sorted the folder *names*
and kept the first. As text `01 April` sorts before `05 March`, so "keep the
earliest" kept the April submission: the wrong one, silently, and only for
students who straddle a month. `resolve_multiple_subs` orders by the
timestamp instead, has **no default** for which attempt counts -- that is an
academic judgement, not ours -- and works out what it would delete without
touching anything, so the page can show it first. The walkthrough now calls
it rather than keeping its own copy.

**The reconciliation was notebook-only too.** `reconcile_marks` is the audit
over the manual copy between the feedback sheet and the grader's own sheet.
It separates the three kinds rather than counting them, because a student who
never submitted reaches the collated file with no sheet to read *every time*,
and a check that reports that as a disagreement stops being read. Two blanks
are not a disagreement either: nobody marked that student, and the records
agree about it. `not_submitted`, `not_allocated` and `transcription_slips` are
the three, and only the last is the failure the audit exists for.

**A withheld flag has to be visible.** `record` refuses to set
`sheets_distributed` when a folder was left unrecognised -- a run that matched
every student but one has not finished. The page said "Distributed" anyway.
It now reports the flag rather than the click, and when it is withheld says
which folders caused it and that anything not a student submission
(`__MACOSX` from unzipping on a Mac, a folder the leader added) can be moved
out. The end-to-end test asserts the flag is withheld while `__MACOSX` is
there and set once it is gone.

Two smaller ones: pressing **distribute** twice is an ordinary thing to do,
and used to fail with "no Brightspace-style folders found" because the first
press had renamed them -- it now only renames what is still in Brightspace
format. And a feedback sheet is **never** replaced, with no tick that changes
it: an existing sheet may carry a mark. The tick covers only the allocation
and the grader workbooks, which nothing but this tool writes.

**Collating is a button, not something the page does on its own**, because
it reads every feedback sheet on the module. Everything after it works from
what it produced, which is what keeps the reactivity simple: the frame is a
cell variable, so there is no state to carry across clicks. `source` is
offered as a choice and never as a fallback — "feedback" is what the
students received, "collated" is what the graders reported, they are
supposed to agree, and substituting one for the other silently would hide
the disagreement worth knowing about.

**Two paths a module needs and did not have keys for.**
`departmental_template` is the department's blank workbook: it is their file
and it changes year to year, so a module keeps its own copy rather than the
package shipping one and quietly using last year's. `si_file` already
existed. The setup form asks for both; a module.toml written before they
existed has to be hand-edited, because the writer only ever updates keys
already in the file, and the page prints the exact lines to add.

**The manual flags are answered one at a time.** Chained, a click on
"moderated" with no assessment chosen fell through and set one of the module
flags instead — a flag nobody asked for, on a record nobody was looking at.

Not done: the scratch copy. Every step writes straight into the module
folder, which was a deliberate choice for a rehearsal on last year's data
(see `docs/dashboard-scope.md`) and is still the thing to design before
anyone else runs this.

### Next

The route to a module a leader can run end to end, in order. Each step
assumes the one before it works.

1. ~~**Quiz / MCQ collection**~~ — done. The rules are recorded in
   `module.toml`, and the walkthrough drives a term of quizzes end to end.
   See **Quiz collection**.
2. ~~**Write everything to the departmental grade file**~~ — done.
   `build_departmental_sheet` lays the workbook out for whatever assessments
   a module has and `write_departmental_sheet` puts the marks in. See
   **Building the departmental sheet**.
3. ~~**Moderation packs**~~ — the internal pack is done; the external one
   is not. Both decisions were the ML's and both are made: *n* = 1 for now
   (and never more than 2 or 3), and a band is a letter grade, A1 down to
   NG. See **Moderation packs**. The external pack is an assembly over the
   internal ones and is now possible, because each internal pack keeps its
   manifest.
4. ~~**Final marks for upload to SI**~~ — done. SI issues the file and we
   fill in two columns of it. See **The SI upload**.
5. ~~**Module initialisation as a workflow**~~ — done. A module leader
   chooses how many pieces of assessment and fills in the two numbers for
   each, rather than hand-editing `module.toml`. See **Pointing at a
   folder**.
6. **Marimo dashboard** — a coursework runs from it end to end, and the
   quizzes with it. See **Running an assessment from the app**. What is left
   is the module-level half: collate, departmental sheet, moderation pack,
   SI upload, and the three manual flags. **Scope and open
   questions are in `docs/dashboard-scope.md`**; start a session on the app
   there rather than here. Two things were already decided there — it works
   on a scratch copy and promotes to the real module folder, and it is built
   for Kev first and hardened for a colleague second — and multi-module
   discovery has since been answered: one folder at a time, chosen in the
   browser, no stored list. See **Pointing at a folder**.
7. **Marks back off a Brightspace-managed group assessment** — the one
   place a group assessment is not yet joined up end to end, and independent
   of 6. Allocation, distribution and marking all work; what is missing is
   the fan-out on the way back. A grader's workbook for that kind is one row
   per group, so `ingest_completed_graderfiles` gives `Group` + `Mark`, and
   `collate_module_marks` wants `Student ID` + `Mark`. Two joins to make:

   - `_from_collated` expanding a group-keyed collated file onto the class
     list's group column;
   - `catch_grades` reading `Feedback sheet Team 3.xlsx`, where
     `extract_studentid_grade` takes the last space-separated token of the
     stem and so returns `"3"`. Everything after `"Feedback sheet "` is the
     right rule for both kinds, but changing the existing one is a behaviour
     change to a covered function — a `key=` argument is the smaller move.

   A **leader-managed** group assessment needs none of this: its download,
   its feedback sheets and its collation are the ordinary individual path,
   which is exactly why the two kinds are separated at the model.

**Polars migration** is unblocked but not scheduled: the Excel round-trip
tests are the contract a port has to keep, and it can land whenever it stops
being a distraction from the list above.

#### PS4002, and why there are two modules in the walkthrough

The notebook ends with two modules, not one. **PS4001** is the template's own
shape and exists to walk the marking process; **PS4002** — one coursework
worth 30 and two MCQs worth 35 each — exists to show the sheet builder doing
the thing a module leader used to do by hand.

It is deliberately much shorter. The marking pipeline is written out twice
already, so PS4002 skips it: the coursework gets feedback sheets, and the two
MCQs are "sat on paper" and handed in through `collate_module_marks(marks=)`,
which is what that argument is for. Same cohort, same class list — the same
students taking a second module.

Its **two MCQs are on different scales on purpose**. An MCQ is sometimes
graded out of 100 and then weighted, and sometimes graded out of however many
questions it had; both happen, so the fixture carries one of each rather than
the same case twice. MCQ 1 is out of 100 worth 35, MCQ 2 is out of 10 worth
35, and the sheet holds `=E30/100*35` beside `=G30/10*35`.

Keep an assessment there that is not marked out of 100. Every other one in
the project is out of 100 or on its own weight, so nothing had ever scaled
*up* — and the scale-up is what found the collation bug above on its first
run.

#### PS4003, and the three sources

**PS4003** — coursework, weekly quizzes, an MCQ and an exam — is the third
module in the walkthrough, and it is there for a different reason from
PS4002. PS4002 is about the *sheet*: a block the template has no room for.
PS4003 is about the *collation*.

Its four assessments arrive by three routes in a single call:

| | comes from | read by |
|---|---|---|
| Coursework 1 | feedback sheets in the download | `catch_grades` |
| Quizzes | Brightspace's own exports | `collect_quiz_marks` |
| MCQ, Exam | marked on paper | handed in via `marks=` |

PS4001 covers the first two and PS4002 the first and third. Nothing had put
all three in one module, so nothing showed that `collate_module_marks`
chooses **per assessment** — by asking what each one *has* — rather than per
module. `test_one_collation_reads_three_different_sources` is the guard, and
it names which route broke rather than failing somewhere downstream.

Two shapes it adds to the sheet, both of which the earlier modules lack:

- **A raw column in the middle of the block.** Ten quiz marks worth ten need
  no weighted column, so `E30` reaches the total directly while `D30`, `G30`
  and `I30` reach it through theirs: `=ROUND(SUM(D30,E30,G30,I30),0)`. Summing
  only the weighted columns drops it; summing every column double-counts the
  marks that were weighted. Both are easy hand-edits and both give a
  plausible number.
- **The exact-divisor weighting in the wild.** The MCQ is 100 marks worth 20,
  and 100/20 is 5, so it gets `=F30/5` while the coursework and exam get
  `/100*30` and `/100*40`. One module, both forms.

Its quizzes are **ten for ten marks with no free pass**, so a mark is simply
the number passed. PS4001 sets eleven for ten and forgives one. Keeping both
is deliberate: the rules are read off the assessment in `module.toml`, and a
fixture that only ever showed one set of them would not prove that.

#### A note on the walkthrough notebook

`notebooks/grading_walkthrough.py` is deliberately plain and explicit, with
cw1, cw2 and the quizzes written out in full rather than driven by a
selector. That is the point while the process is still being stepped through
and checked -- every value visible, nothing hidden behind a widget.
Convenience features belong in step 6, not before.

The quiz section is four cells against the coursework's ten, and the
shortness is the content: every step of the coursework path exists because a
human copies a number by hand, and nobody marks a quiz. No allocation, no
distribution, no transcription, and so nothing to reconcile.

**The notebook is now run by the suite.** `marimo.App.run()` executes every
cell and raises whatever a cell raises, so `tests/test_walkthrough.py` drives
the whole thing into a tmp directory and checks the marks it produced against
the fixture's own expected column. "Verified end to end" was a claim in
`docs/running-locally.md`; it is now something that fails when it stops being
true. `GRADER_HELPER_SCRATCH` exists only so the test can redirect `ROOT`
away from the user's home.

### Quiz collection

Brightspace exports **one CSV per quiz**, so collecting a term of them is a
fold rather than a read: `collect_quiz_marks` joins the exports on the
student id, counts the passes, and returns one column named by the
assessment — `Quizzes (10)` falls out of the two-numbers rule, it is not
spelled anywhere.

Three of the decisions in it are policy rather than arithmetic, and all
three are the module leader's:

- **`pass_mark`.** A quiz is passed when its percentage is **strictly
  above** the mark. At 80.0 a student who scored exactly 80% has failed.
  That is the rule as stated for the module this was written for, and it is
  a parameter precisely because no other module has to share it.
- **`free_passes`.** *n* quizzes may be failed without losing a mark: added
  to the count, then **capped at `marks_out_of`**. Worth being clear that
  this is not the same as dropping the worst quiz — it lifts everyone by
  *n*, where dropping the worst only helps those near the top. Eleven
  quizzes, ten marks, one free pass is the shape it was written for.
- **The non-participant.** The free pass is **not** given to a student who
  sat no quiz at all. The departmental sheet awards NG where the module
  total is zero and excludes it from the average QPV, so handing a ghost
  student 1% quietly converts their NG into an F. Two routes reach that
  student and both are closed: absent from every export (the class list
  supplies the 0), and present with an empty `%` — opened the quiz, never
  submitted (the `sat_any` check).

**No rounding here.** The percentage is compared as Brightspace reports it.
Rounding *up* to the boundary would promote a fail to a pass, which invents
a mark rather than reading one. `excel_round` belongs where totals are
formed for the sheet, not where a threshold is tested.

**The `#`, again.** The quiz export writes `Username` as `#56170559`,
exactly as the class list does. Left on, the join against the class list
does not fail — it matches nothing, and every student comes back twice with
half their row empty. Same trap, second location.

**Every column is read as text** (`infer_schema_length=0`), for the leading
zero. Only one test reaches that guard: an export whose username carries the
`#` is inferred as text anyway, so the flag is only load-bearing where the
id arrives as a bare number.

**Two refusals**, both because the alternative is awarding a mark nobody
chose: more than one row for a student in one export (multiple attempts —
which one counts is a rule about the module), and more than one export named
for the same quiz (which would count it twice for everybody).

#### The rules live in `module.toml`

`pass_mark` and `free_passes` are fields on `Assessment`, so a module
records how its own quizzes are collected rather than leaving it to whatever
script happens to call the function. There is **no default pass mark**:
with neither the assessment nor the caller supplying one,
`collect_quiz_marks` raises. A threshold nobody chose is exactly the kind of
invisible policy that produces a plausible wrong mark, and no module has to
share another's.

Three decisions inside that:

- **Flat scalars, not a `[assessment.quiz]` sub-table.** The file writer's
  one real hazard is that a scalar written after a sub-table is parsed *into*
  that sub-table — the reason `init_module` writes every person's scalars
  before opening `[module.leader]`. Flat keys cannot trip it.
- **`pass_mark` is not required at load time.** Requiring it would stop an
  existing `module.toml` opening at all, which is a heavy price for a rule
  only needed at the moment marks are collected. It is enforced there.
- **`pass_mark = 0` is legal and meaningful.** With the strictly-above rule
  it means any score above nothing passes: the quiz is an engagement mark.
  So the check is `ge=0`, not `gt=0`.

Two validators refuse configurations that would otherwise produce plausible
output: quiz rules on a coursework or exam (there a "pass mark" reads as a
compensation threshold, which is a different thing this package does not
implement), and `free_passes >= marks_out_of`, which awards every student
full marks without a quiz being sat.

Adding the fields could not disturb an existing file, and the reason is
worth knowing: `ModuleFile.save` syncs the author's sections with
`add_missing=False`, so a key absent from the document stays absent.
`free_passes = 0` on the model is never written into a file that lacks it.

#### The fixture

`make_fake_module(..., quizzes=True)` replaces the MCQ with eleven weekly
quizzes — same id slot, same two numbers, same weight — so the weights still
sum to 100 and every total in `expected` is unchanged. Replacing rather than
adding is what keeps the coursework path and the golden data out of it
entirely. It is off by default, so the module every other test sees is the
module it saw before.

The exports are generated **backwards from the mark each student should
end up with**, which is what makes the fixture assert something rather than
merely exist. With one free pass the mark is `min(passes + 1, 10)`, so a
target of *v* means passing *v* − 1 and failing the rest; a target of 10 is
nine passes and the cap; a target of 0 is a student who appears in no export
at all. That last one is Jack Joyce, who is already the cohort's "scored 0
throughout → NG, not F" case, so the NG guard is exercised by the fixture's
own logic rather than by a special case bolted on.

**polars is now a runtime dependency**, and this is the first module to use
it — the wedge for the migration rather than a port of what already works.
The fold is polars throughout; the return is pandas, because that is what
the rest of the pipeline reads. The conversion goes through Python lists
rather than `to_pandas()`, which would pull in pyarrow for a frame of a few
hundred rows.

### Group assessments

There are **two kinds**, and they are not variations on one another. The
whole design follows from that.

| | groups made in | membership arrives | Brightspace download | the mark belongs to |
|---|---|---|---|---|
| `group_source = "brightspace"` | Brightspace | a column in the class list | **one folder per group**, one feedback sheet | the **team** |
| `group_source = "module_leader"` | the leader's own sheets | nowhere — it has to be collected | one folder per **student**, one feedback sheet each | the **student** |

So the key decides two separate things: where membership is read from, and
whether a mark is a team's or a person's. `group = true` on its own answers
neither, which is why an assessment that sets it and nothing else now
**refuses to load**. There is no default, and picking one would fail late
and quietly in both directions — a Brightspace-managed run against a
per-student download simply finds no group folders and distributes nothing,
and a leader-managed run against a class list that already has the groups
goes looking for sheets nobody wrote.

Nothing read `Assessment.group` before this, so requiring the second key
broke no working file.

#### Collecting the leader's own groups

`collect_group_membership` is a fold, the same shape as `collect_quiz_marks`:
many sheets in, one two-column frame out.

```
assessments/cw2/groups/
    Team 1.xlsx        a sheet of student ids
    Team 2.xlsx                                  ->  Student ID | Group
    Team 3.xlsx
```

One workbook with a tab per team works too. **The group name comes from the
sheet, not from a column** — a file called `Team 1.xlsx` is Team 1, a tab
called `Team 1` is Team 1 — unless the sheet carries a group column, which
wins, because a leader who wrote one meant it and it is the only way to put
two teams in one tab. A single-sheet workbook is named by its *file*: a
workbook saved from a template is called `Sheet1` inside however carefully
the file was named.

These are hand-made files, so the reader survives what hand-made files have:
trailing blank rows, blank lines between teams, a leading `#` on ids pasted
from a Brightspace export, `~$Team 1.xlsx` lock files from a workbook someone
left open, an id column called almost anything.

#### Which column is the group

**A group column is called `Group` or `Team`.** Those two, in any casing,
with spaces and underscores ignored — and *nothing else is picked
automatically*. Not `Group Name`, which is what Brightspace's own group
function exports; not `Groups`, `Grouping` or `Team Name`; and not a code
that looks like one.

That is narrower than it started, and the narrowing is the point. A leader's
sheet carries several columns that read like the group without being it:

```
Name          Student Id   Team   Grp Code   Group
LAST FIRST    12345678     1      2A         2A_1
LAST4 FIRST4  12345681     1      2B         2B_1
```

`Grp Code` is produced elsewhere, for something else, and looks like the
group only because the group label is built out of it — `2A_1` contains
`2A`. It was never in the alias list and never found automatically. What did
the damage was the code **recommending** it: the ambiguity message offered
`["Grp Code", "Team"]` as its worked example of a composed key, and so did
the `module.toml` comment, two docstrings and `CLAUDE.md`. A suggestion is
not neutral when the reader is looking for something to type.

The first fix was a blocklist that refused it by name. That was the wrong
shape — it answered "which columns are forbidden" when the useful question
is "which columns are the group", and every column not on the list stayed
quietly eligible. **A closed list of two is the whole rule**, and it needs
no exceptions.

Naming a column explicitly is not restricted, and must not be: `group_column`
takes any column in the sheet. The difference is that naming one is a
decision somebody made, and picking one is a guess the code made.

`Team` and `Group` are both the group column by name, and **they are not the
same partition**: in the sheet above those two students are one team on
`Team` and two on `Group`. Picking by alias order would be right by luck.
So `resolve_group_column` reads the **data** — it compares the partitions
each induces, and:

- one of them, or both **agreeing** → use it, and do not ask; which one is
  used cannot change a single allocation
- both **disagreeing** → refuse, saying how many groups each makes and to
  name one

Two columns cut a frame the same way iff their common refinement is no finer
than either: `groupby(a).ngroups == groupby([a, b]).ngroups ==
groupby(b).ngroups`.

**Composed keys are gone.** `group_column` took a list and joined the parts
with `_`, so a sheet with no combined column could say cohort `2A` team `1`
is `2A_1`. With only two names accepted there is nothing sensible left to
compose — `["Group", "Team"]` is the only pair available and it is
meaningless — and the feature existed mainly to make the group code look
usable. `GROUP_KEY_SEPARATOR` went with it. `group_key` stays, for the one
thing it does that matters:

**A blank group stays blank** — not `"nan"`. `astype(str)` turns a missing
group into that string, which is not blank, so the missing-group refusal
never fires and every student without a group is allocated together as a
team called `nan`: one grader, one mark, no error anywhere. That defect was
live in `attach_group_membership` and found by a test written for something
else.

`Assessment.group_column` records the answer in `module.toml`, so a leader
whose sheets always look like this answers once. One helper,
`_group_column_for`, resolves override-or-assessment for both the
leader-managed and the Brightspace path — there were briefly two, and each
hid the other going missing under mutation.

Two refusals, both data problems for the leader:

- **A student in two groups** raises `ConflictingGroupsError`, naming them
  and both groups. Taking the last one seen marks their work with a team
  they were not in.
- **A student in no group** raises `MissingGroupError` — the same rule, and
  the same `SOLO` escape hatch, as a Brightspace group class list, because
  `attach_group_membership` reuses that code rather than restating it.

The other half of a mistyped id is a *warning*: the sheets name somebody who
is not enrolled. A typo shows up twice, once at each end, and seeing both
together is what identifies it.

`attach_group_membership` is the join that matters: afterwards there is **one
shape**, a class list with a `Group` column in the position
`import_brightspace_classlist(group=True)` puts it. Everything downstream
then stops caring which kind of group assessment it is.

`group_membership.csv` is written to `grading_output/` and **regenerated
every time**. The sheets are the record; correcting the collected file
instead would be corrected right back.

#### Allocation, wired in

`allocate_graders` in `allocating.py` is the step that was missing. The
pieces existed — `assign_graders_individual`, `assign_graders_groups`,
`save_distributed_graders`, `save_grader_sheets` — but nothing joined them
to an `Assessment`, so every caller had to know which allocator its
assessment wanted, where the two files go and what shape a grader's workbook
should be. Hand it an assessment and a class list and it does the right
thing for the kind:

| kind | allocated over | grader's workbook |
|---|---|---|
| individual | students | one row per student |
| group, Brightspace | groups | one row per **group** |
| group, module leader | groups | one row per **student** |

The middle row is the point. Brightspace gives a team one folder, one
feedback sheet and one mark, so a per-student workbook there would ask the
grader to type the same mark four times — three extra chances to mistype it,
in a package whose main control exists because a human copies a number by
hand. The bottom row is the mirror image: Brightspace knows nothing about
those groups, so every student has their own sheet and marks may
legitimately differ within a team. **The group decides who marks it, not
what the mark is.**

`distributed.xlsx` is one row per student in all three cases. It is the file
you open when a student asks who marked their work, and that question has an
answer whoever submitted it.

It lives at the top level beside `collating.py` for the reason given there:
it is an assembly layer, reaching into `ingesting`, `assignment` and
`file_operations` at once, and those packages deliberately do not reach
sideways into each other.

**It writes no status of its own.** `GraderAllocation` carries the
`Allocation` that `save_distributed_graders` returned rather than a bare
path, so `ModuleFile.record` reads the same evidence off either and
`graders_allocated` is set from what the run produced, not from its having
failed to raise. There is one more line in `recording.RULES` and nothing
else — see **Keeping status**.

#### In the app

The dashboard's `allocate_marking` was the hand-rolled version of all this,
and it had exactly the defect the split exists to prevent: it chose the
allocator off `assessment.group` and then wrote a per-**student** workbook
whichever it chose, so a Brightspace-managed team would have arrived at its
grader as four rows wanting the same mark typed four times. It now calls
`allocate_graders` and keeps its `record` call.

Two more things had to move with it. The class list is imported with
`group=True` only when some assessment is **Brightspace**-managed: asking
for a group column on a leader-managed module refuses a class list that is
perfectly correct, because those groups were never in Brightspace. And the
setup form now has a **submitted by** dropdown — one control with three
choices, not a tick plus a follow-up question, so the form cannot produce
the one state `module.toml` refuses.

Converting an assessment that already exists is still a hand edit:
`ModuleFile.save` only updates keys already in the file, so `group` and
`group_source` have to be typed into the `[[assessment]]` block. That is the
file's own rule, not a gap — it is what stops a save rearranging a
hand-written file — and `leader_managed_module` in `tests/test_dashboard_steps.py`
is what the edit looks like.

#### What was verified by reintroducing it

Every guard here was seen to fail before it was trusted: a per-student
Brightspace workbook, a per-group leader-managed one, groups allocated per
student so teams split across graders, conflicting groups resolved by
last-seen, the `Group` column appended rather than placed, the blank-row
filter removed, `group_source` left out of `module.toml`, `groups/` created
for every assessment, the form writing `group = true` with no source, the
class list asked for groups a leader-managed module has not got, an
ambiguous group column resolved by alias order, a composed key ignoring all
but its first column, `group_key` and `attach_group_membership`
stringifying a blank into `"nan"`, and the allocation ignoring the
assessment's own `group_column`.

Two of those **passed** the first time they were mutated, and both are
worth recording. The class-list one passed because nothing yet drove the
dashboard against a leader-managed module; the two end-to-end tests in
`test_dashboard_steps.py` were written because of it. The `group_column`
one passed because the fallback was written twice, once in
`allocate_graders` and once in `build_group_membership`, so each masked the
other's removal — the fix was one helper, not another test. A guard nobody
has watched fail is not yet a guard, and a guard written twice is watched
half as closely.

### Collating a module

Every other step in this package works on one assessment.
`collate_module_marks` is the one that works on the module: it walks the
assessments, fetches each one's marks from wherever that kind of assessment
keeps them, and returns a frame ready for
`prepare_data_for_departmental_template`.

It was extracted from a loop that lived inside a **test fixture**
(`tests/test_end_to_end.py`), which is where the only whole-module code in
the project had been sitting. That loop called `catch_grades` for every
assessment, so it could only ever read an assessment marked on a feedback
sheet — put a quiz in the module and there was nothing for it to read. The
fixture now calls the real function and its assertions are unchanged, so
what they check is that the extraction reproduced the prototype exactly.

**It lives at the top level, not in `dataframe_operations`.** That package
depends on nothing but `models`, and collation reaches into `ingesting` and
`file_operations`; putting it there would have inverted the layering.

#### What decides where a mark comes from

Not the assessment's `type`. An MCQ can be sat in Brightspace, written on a
feedback sheet, or done on paper in a lecture theatre, and all three are
`type = "mcq"` — so asking what an assessment *has* answers the question and
asking what it *is* does not. In order: marks handed in through `marks=`, a
`grade_cell` (the feedback-sheet workflow), then quiz exports in the
submissions folder. Anything else gets an empty column and a warning naming
it, because an assessment that quietly vanished would take a component out
of every total.

That order was found the hard way, and only by running the walkthrough.
`alphabetise_folders` writes `folder_rename_log.csv` **into the submissions
folder** — it is the handoff to `brightspace_name_folders` — so every
alphabetised coursework has a .csv sitting beside the submission folders.
Checking for exports first sent cw1 down the quiz path, where it failed
complaining that it had no pass mark: an error about the wrong assessment
entirely, in a step the reader was not thinking about. Two fixes, both kept:
a `grade_cell` now settles it before the folder is looked at, and the export
check ignores the files this package itself writes there.

#### The weighted column has to be named by the assessment

`collate_module_marks` used to weight through `calculate_weighted_score`,
which infers the new column's name by multiplying the fraction by 100. That
is the weight only when the piece is marked out of 100. Out of 50 and worth
25 it produces `(50)` — the raw column's own name, which it then refuses to
overwrite — and out of 10 and worth 35 it produces `(350)`.

It reports both by *returning* a string, and the return value was being
discarded. So the weighted column silently never appeared, and the failure
surfaced two steps later as `prepare_data_for_departmental_template`
complaining about a column it had been given no way to create. A component
quietly absent from every total is the exact failure this package exists to
prevent, and it was hiding in the code that assembles the totals.

It stayed invisible because every assessment in the fixtures was marked out
of 100, except the MCQ — which is worth what it is marked out of and so needs
no weighted column at all. PS4002 in the walkthrough is the first assessment
that scales *up* (10 marks worth 35), and it found this immediately.

The collation now takes the name from `Assessment.weighted_column` and does
the multiplication itself. `calculate_weighted_score` is unchanged and still
correct for the out-of-100 case it was written for.

#### The two records, and why there is no fallback

A marked coursework exists in two places and they mean different things:
`completed_grades.xlsx` is what the **department** receives, the feedback
sheets are what the **students** received. Step 7 reconciles them, and they
must agree — which makes it tempting to let a missing collated file fall
back to the feedback sheets. It does not. The fallback would be invisible,
and "the record I meant was not there so I used the other one" is the same
class of silent substitution as everything else this package refuses. A
missing collated file raises and names both ways out.

That invariant is now a test: collating a reconciled module from either
record gives the same frame. Writing it turned up the honest version of the
same point — the first draft of the fixture wrote a mark for the student who
never submitted, the two records disagreed, and the test was right to fail.

### The departmental workbook

`Dept grade sheet Template 2026.xlsx`, committed to the repo root. Five
sheets: `Guidelines for staff`, `Moderation Form`, `EHS grades UG modules`,
`Checklist for EE`, `GradeTemplate`. The last is the one marks go into; the
middle two matter for moderation, which is items 2 and 3 of **Next** and is
not started.

Read off the file itself, not inferred:

| | |
|---|---|
| header row | 29 |
| columns | A `Name`, B `Student ID`, C..G the assessments, H `Total % Grade`, I `Letter Grade`, J `Comments` |
| student rows | 30 to 530, so 501 of them |
| sample data | rows 30–50, and it has to be cleared before real marks go in |
| band table | rows 7–17: A lower, B upper, C letter, D award, E QPV. Row 7 is `No participation` → NG |
| distribution | G5:I17, `COUNTIF(I30:I530, "A1")` and so on, with the average QPV at I17 |
| summary | rows 23–25: Mean, SD, N |

`tests/resources/gradetemplate_samples.csv` is rows 30–49 of this sheet,
which is where the golden test's numbers came from.

#### Four columns are the sheet's, not ours

**D, F, H and I hold formulas, in all 501 rows, already.**

```
D30  =C30/100*40                    the weighted coursework 1
F30  =E30/2                         the weighted coursework 2
H30  =ROUND(SUM(D30,F30,G30),0)     the total
I30  =IF(ROUND(H30,2)>0, ...)       the letter grade, off the band table
```

So writing a module into this sheet means writing **A, B and the raw mark
columns** — five values a row — and touching nothing else. Filling in the
weighted columns or the total would overwrite the department's own
arithmetic with ours, which is backwards: the sheet is the source of truth
and our copy of the calculation exists to be *checked against* it.

That also settles what a test can assert. openpyxl does not evaluate
formulas, so on Linux the check is that the values landed, the formulas are
untouched and the sample rows are gone. Comparing H and I against
`prepare_data_for_departmental_template` needs a real Excel, which is what
the `excel` marker is for.

Two things the sheet confirms, both already implemented from the sample CSV:
`H` rounds half away from zero at 0 dp, which is `excel_round`; and `I`
returns `NG` when the total is not greater than zero, which is
`NO_PARTICIPATION`.

#### The template is one module's shape

The formulas hardcode it: `C/100*40`, `E/2`, and a total that sums exactly
`D, F, G`. This template **is** cw1 (100/40) + cw2 (100/50) + MCQ (10/10).
A module with four assessments, or different weights, cannot be written into
it as it stands — the fourth would be silently left out of the total, which
is the "plausible number" failure this package exists to prevent.

The way out is already in the codebase and needs no new convention: the
template's headers **are** `Assessment.raw_column`. Row 29 literally reads
`Coursework 1 (100)`, `MCQ (10)`. So the writer finds each assessment's
column by matching `raw_column` against row 29, writes the raw marks there,
and refuses — naming the column — when the module has an assessment the
template has no home for. A module that fits is written; one that does not
is told so, rather than being half-written.

That is `write_departmental_sheet`. The half it does not solve — a module
that does not fit — is `build_departmental_sheet`, which makes the home. See
**Building the departmental sheet**.

### Building the departmental sheet

The template is one module's shape, so any other shape has been reshaped by
hand — and that is where the marks go wrong. The two places a hand edit fails
are not random; they are the only two things that move when the assessment
block changes width:

* the **descriptives at A23** — Mean, SD and N, one formula per column. Add an
  assessment and the summary needs three more cells that nothing reminds you
  about. A mean over six of seven components is a perfectly plausible number.
* the **Letter Grade column and the distribution that reads it** — a nested
  `IF` ten levels deep, plus eleven `COUNTIF`s pointing at it. Miss one and
  the distribution reports the cohort as NG.

`build_departmental_sheet(module, template, destination)` lays the block out
for whatever assessments the module has and re-points everything downstream.
`write_departmental_sheet(df, module, workbook)` then writes Name, Student ID
and the raw marks into it — five values a row for the template's shape,
nothing else.

**It writes formulas, never values.** The weighting, the total, the letter
grade, the descriptives and the distribution all go in as Excel formulas
transcribed from the template's own. The sheet still does its own arithmetic
off its own band table, so it stays the thing our numbers are *checked
against* rather than a transcript of them. Nothing outside `GradeTemplate` is
touched, and inside it the band table at A5:E17 and the QPV column are read
but never written.

#### The guard: rebuild the template and require it back

`tests/test_departmental_sheet.py::test_rebuilds_the_committed_template` gives
the builder a module of the template's own shape — cw1 100/40, cw2 100/50, MCQ
10/10 — and asserts the committed template comes back cell for cell: headers,
every formula in the ruled rows, the descriptives, the distribution and the
number formats. The only permitted difference is the cleared sample rows.

That is what makes the shapes nobody has a golden copy of trustworthy. The
letter-grade formula in particular is *generated from the band table in the
workbook being written*, rows 8–17, so it reproduces the department's string
exactly and follows them if they retire a band.

#### Two things read off the file that contradicted the obvious choice

**The weighting must divide exactly where it can.** The template writes
`=C30/100*40` for cw1 and the hand-simplified `=E30/2` for cw2, and the tidier
thing to do is to write both the long way so the weight is visible in the
cell. That is wrong, and not cosmetically. `x/2` is exact in binary floating
point; `x/100*50` is two roundings and is not — they differ by up to 1.4e-14.
The total is `ROUND(SUM(...),0)`, so a sum landing on an exact half falls the
other way: at cw2 = 29 the two forms give 14.5 and 14.499999999999998, which
Excel rounds to **15 and 14**. Thirteen such disagreements exist on a
half-point mark grid. So: divide by a whole number where the weight goes into
the marks exactly, and use `/marks_out_of*weight` otherwise. On the template's
shape that gives the department's two formulas back, character for character.
`test_the_long_weighting_form_would_have_moved_marks` keeps the evidence.

**Body styling comes from a blank row, not row 30.** The template formats its
sample rows 30–49 with a number format of `0` and the 481 untouched rows below
them with `0.00`. The samples are the odd ones out and wrongly so: `E30` holds
`66.5` and a format of `0` displays it as **67**. Styling is taken from the
first ruled row the department left empty. Some sample rows also carry a
highlight fill, which on a real student would read as a flag from the module
leader.

#### Two templates are in circulation, and they grade 100 differently

Found by comparing a working copy against the committed one. They differ by
**one character, in one cell** (filled down 501 rows), in the letter-grade
formula:

```
committed:  ...ROUND(H30,2)<=$B$17),"A1","NG")
the other:  ...ROUND(H30,2)< $B$17),"A1","NG")
```

`$B$17` is 100. Every band but the last is closed by the band above it; A1
has nothing above it, so it has to close with `<=`. With `<`, a total of
exactly 100 matches no band and falls through the whole nested `IF` to the
final `"NG"` — **a student with full marks recorded as no participation.**

The committed copy is the correct one: it agrees with the band table beside
it, which gives A1 an upper bound of 100, and with `make_letter_grade`. The
golden samples top out at 75, which is why nothing had ever exercised the
boundary.

`build_departmental_sheet` **refuses** a template with the `<` form rather
than correcting it. It regenerates the formula, so it would otherwise emit
the right one silently and overrule the department's file without saying so
— and a package that substitutes its own arithmetic quietly is what every
other guard here exists to prevent. The refusal names the cell and the
one-character fix.

Worth knowing which copy the department actually issues. If it is the `<`
one, that is a live defect in their file rather than something to work
around.

#### The N row, which looks like a mistake and is not

Row 25 counts the *raw* column in every case: `D25` is `COUNT(C30:C530)`, not
`COUNT(D30:D530)`. That is deliberate — the weighting formula sits in all 501
rows, so counting it returns 501 whatever the cohort. `H25` counting `G`
follows from the same fill and has the same effect. The rule that reproduces
the template exactly is *the nearest raw column at or before this one*, and it
is also the honest one: N means "students with a mark", and only a raw column
knows that.

#### What it refuses

All four refusals guard one failure — a total quietly missing a component,
which looks exactly like a real mark:

- an assessment the sheet has no column for, named rather than dropped;
- a column the sheet totals that the module does not account for, because left
  empty it contributes zero to every student;
- a cohort larger than the 501 ruled rows, because row 531 is outside every
  formula on the sheet;
- an existing destination, unless `overwrite=True`.

Ten of these guards were verified by reintroducing the bug — dropping an
assessment from the total, pointing N at a formula column, freezing the
distribution on column I, skipping the clear, writing ids as numbers — and
watching the test fail.

### Keeping status

Two halves, split by one question: **can the code honestly know?**

A step can tell that it produced a file. Whether that file was then *sent*,
*read* or *accepted* is in somebody's head and never on disk. So each artefact
has a flag the code sets and, where a person has to do something with it, one
beside it that only a person can set.

| the code sets, from evidence | a person sets |
|---|---|
| `departmental_sheet_written` | `sent_to_department` |
| `moderation_pack_built` | `moderated` (per assessment) |
| `si_file_written` | `si_submitted` |
| `sheets_distributed` | |

That rule is why `build_moderation_pack` never set `moderated`: a pack
existing is not a pack having been read.

#### "It did not raise" is not evidence

The tempting rule is *set the flag when the code runs without crashing*. It is
wrong here, and this package supplies its own counter-examples:

* `distribute_feedback_sheets` returns a `Distribution` that can be entirely
  `unmatched` — forty folders, no ids recognised, no exception.
* `collate_module_marks` *warns* for an assessment it found no marks for.
* `ingest_completed_graderfiles(require_all=False)` warns rather than raises.

A green tick against a step that did nothing looks exactly like a real one —
the same failure as a total missing a component. So the flag comes from the
**return value**. `grader_helper/recording.py` holds one rule per result type:

| result | flag | evidence |
|---|---|---|
| `Allocation` | `graders_allocated` | `distributed.xlsx` holds students |
| `GraderAllocation` | `graders_allocated` | the `Allocation` it carries |
| `Distribution` | `sheets_distributed` | something copied or skipped, and nothing unmatched |
| `Collation` | `grades_collected` | `completed_grades` holds students |
| `DepartmentalWrite` | `departmental_sheet_written` | rows written |
| `Pack` | `moderation_pack_built` | the manifest exists |
| `SiUpload` | `si_file_written` | marks filled, and SI's roll fully accounted for |

**The artefact is the evidence.** Every rule reads the file the step produced:
`distributed.xlsx` existing is what says the graders were allocated,
`completed_grades` that the marks came back, `moderation_sample.csv` that a
pack was drawn. Existence alone is not enough, though -- an empty
`distributed.xlsx` is not an allocation -- so each rule also asks how many
students are in it.

`GraderAllocation` is the shape of an added rule: `allocate_graders` wrote
the grader workbooks as well, but the allocation file is still what says the
step happened, so it holds the `Allocation` rather than a bare path and its
rule reads straight through to it. One line in `RULES` and nothing else,
which is what that registry is for.

`ModuleFile.record(result, assessment_id=None)` looks the rule up and sets the
flag only if the evidence supports it. A result that falls short leaves the
status alone without complaint — a half-finished step is a normal state of
affairs. A result **nothing** has a rule for is refused, because setting a
flag on no evidence is worse than not setting one.

Adding a step means adding a line to `RULES` and nothing else. The library
functions stay pure and path-based; they never learn about `ModuleFile`.

Three functions gained evidence-carrying returns so their artefact could be
read:

* **`write_departmental_sheet` returns a `DepartmentalWrite`**, not a bare
  path. A path said the function had run; it did not say whether anything
  reached the sheet, so there was no evidence to read.
* **`save_distributed_graders` returns an `Allocation`** for the same reason.
* **`save_collated_grades` is new**, split out of
  `ingest_completed_graderfiles` so writing `completed_grades` has a function
  that reports what went into it. `ingest_completed_graderfiles(save=True)`
  calls it, so there is still one definition of what that file is and where it
  goes, and its own return is unchanged -- callers still get the frame.

**The rules live one layer up**, in `recording.py`, because they import
`file_operations`, `ingesting` and `moderation`, and those import `models`.
`ModuleFile.record` imports the registry inside the method, which keeps the
layering honest without a cycle.

#### `[module_status]`, and the bug writing it caused

Module-level status is its own table, **not** `[status.module]`: `[status]` is
keyed by assessment id, and an assessment legitimately called `module` would
collide with it.

Reading it back is order-dependent, and getting that wrong ate data. Both
`[status]` and `[module_status]` land on a model field called `status`, and
the first version set the module's *before* popping the assessments' —
silently wiping every assessment flag in the file. `[status]` is popped first
now, and `test_module_status_and_assessment_status_do_not_clobber_each_other`
is the guard.

#### What is left manual, and why

Only `moderated` and the two module-level ones. Every other flag now comes
from an artefact, and `test_every_assessment_flag_can_now_be_recorded` says so
— it fails if a new assessment flag appears with nothing to justify it.

`moderated`, `sent_to_department` and `si_submitted` are manual because
nothing on disk can settle them: a pack existing is not a pack having been
read, and a file written is not a file sent.

### The SI upload

SI **issues** a file — one row per enrolled student, `Mark`, `Grade` and a
bare `CD` blank — and the module leader sends the same file back. So this is
the departmental sheet's problem again: *fill in two fields of somebody
else's file and change nothing else*, not *produce a file in SI's format*.

`write_si_marks(df, si_file, destination=None)` does it;
`paths.si_file` in `module.toml` records where SI's file is.

Read off a real file at byte level (counts and the header only — no student
data left the machine):

| | |
|---|---|
| encoding | UTF-8, **no BOM**, trailing newline |
| line endings | **bare LF**, zero CRLF — on a file Windows produced |
| quoting | none anywhere; no field holds a comma |
| columns (13) | `Year, Period, #Module, Occ, #Map, #Ass#, #SPR_Code, Name, #CD, Mark, Grade, CD, #Cand Key` |
| `#SPR_Code` | `#<student id>/<attempt>` — attempt = times taken |
| `Name` | `KEVIN O'MALLEY` — upper case, apostrophes, no surname comma |
| `#CD` | two digits, leading zero significant (`#07`) |
| `Mark` | an integer literal; `Grade` a band letter |

**The bare LF is the one that bites.** Python's `open(path, "w")` turns `\n`
into `\r\n` on Windows, so writing the file back the obvious way changes
*every line in it* — forty lines rewritten by a function asked to change two
fields. Bytes are read and written, with whatever terminator the file already
had. Linux CI would never catch this by accident, because there a text write
produces LF anyway, so the test asserts on bytes.

**SI accepts `NG`** — confirmed by the module leader, not assumed. A
non-participant goes up as `Mark = 0`, `Grade = NG`, which is exactly what
the departmental sheet says they got, so no special case is needed anywhere
in the chain.

`#SPR_Code` and `#Cand Key` are **matched on and never rebuilt**. The attempt
number is SI's and nothing we hold could reproduce it, so a writer that
reconstructed the key would get every resitting student wrong and nobody
else.

#### Two faults in the scratch version this replaces

The working version was a marimo notebook doing `pr.scan_csv` →
`write_csv`, which re-emits the file as polars thinks a CSV should look. Both
faults are of the usual kind — a plausible result rather than an error:

- **It blanked marks.** `with_columns(pr.col("Mark_right").alias("Mark"))`
  replaced `Mark` unconditionally, so any SI row unmatched in the grades
  frame got `Mark = null`. Harmless the first time, because the column is
  empty anyway; on a re-run against a partial frame it overwrites real marks
  with nothing. A student on SI's roll with no mark is now **refused** and
  named, with `allow_unmarked=True` as the explicit way through.
- **`how="full"` invented rows.** A student in the grades file but not in
  SI's got appended with a null `#SPR_Code`. SI's roll decides the cohort, so
  they are reported in `not_enrolled` and never added.

Nine guards in `tests/test_si_upload.py`, each checked by reintroducing the
bug: writing as text, blanking an unmatched mark, skipping the refusal,
putting the id through an int, writing `70.0`, rebuilding the attempt number,
accepting a quoted file, accepting a short row, and appending the
un-enrolled.

#### The fixture has to play SI

Nothing generates one of these for real, so `write_si_export` in
`tests/fake_module.py` writes the blank file SI would issue — LF endings, no
BOM, the `#` prefixes, a `#CD` with a leading zero, and two students on
second and third attempts. PS4001, PS4002 and PS4003 each get one, and the
walkthrough fills all three.

### Moderation packs

Who gets a second opinion, and the folders the second marker is handed.
Three pieces in `grader_helper/moderation/`, in the order they run:

| | |
|---|---|
| `flag_borderline` | who is within a point of the next grade up |
| `sample_for_moderation` | the draw — *n* per band, plus requested, plus borderline if asked |
| `build_moderation_pack` | the folders, and the manifest saying what is in them and why |

The decisions were the module leader's and are recorded here so they are not
re-litigated: **n = 1**, and never expected above 2 or 3; **a band is a letter
grade**, A1 down to NG.

#### Borderline, and why it may replace the ratio

A total of 69 is a B2 and 70 is a B1 — one mark apart, and a different
classification on a transcript. If a hand-marked component is wrong anywhere,
it costs the student most there. The department is discussing moderating on
that basis *instead of* a random sample per band, so borderline students are
computed whatever else happens and `sample_for_moderation(borderline=...)`
takes `"flag"` (the default, today's practice), `"include"` (take them all)
or `"ignore"`.

**The distance is measured from the rounded total**, because that is the mark
of record: the sheet computes `ROUND(SUM(...),0)` and bands *that*, so a
student whose exact total is 69.6 already has 70 and is already a B1.
Measuring from the unrounded figure would flag people who are not near a
boundary and miss people who are.

The top band and NG never have a next grade, so neither is ever borderline.

#### The seed is the point

A random sample that comes out different every run is not a sample. Nobody
can answer "why was this student moderated?" six months later, and re-running
quietly changes the answer.

So every draw carries the seed that produced it, `sample_for_moderation`
generates one when not given it and **returns it**, and the seed goes into
`moderation_sample.csv` beside the pack along with who was selected, from
which band, on what mark, and why. Given the marks and the seed anyone can
reproduce the selection exactly — there is a test that does.

That manifest is also the handoff to the external pack, the same way
`folder_rename_log.csv` is the handoff to `brightspace_name_folders`. The
folders can be rebuilt from it; without it they cannot.

#### Three bugs the prototype had, all now guarded

The working version of this was a marimo notebook, and its faults were
instructive rather than careless — every one is the kind that produces a
plausible result:

- **`if id in f.stem`** matched the student id anywhere in the folder name,
  so `2330430` gets `23304301`'s work. The wrong student's submission in a
  moderation pack is worse than none. Folder names are now *parsed*, with
  `parse_brightspace_folder`.
- **No seed, plus `dirs_exist_ok=True`, plus no record.** Run it twice and a
  different student per band is copied in alongside the first, with nothing
  saying which draw was real. A pack is now refused rather than merged into,
  and `overwrite=True` replaces it outright.
- **NG was sampled.** A non-participant has no submission folder, so the copy
  found nothing and left an empty band directory — which reads as work the
  moderator has already been through. NG is excluded, and a selected student
  with nothing submitted is *named* in `pack.missing` and the manifest.

A fourth, found by asking why the walkthrough built no pack for PS4001: a
sampled band whose student submitted nothing **never appeared in the pack at
all**, because the band folder was only ever created as a side effect of
copying work into it. That is the empty-folder problem inverted — an empty
folder reads as work already moderated, and a *missing* folder reads as a band
nobody sampled. Every sampled band now gets a folder, and one with nothing in
it carries a note saying which of the two it is.

Fourteen guards in `tests/test_moderation.py`, each checked by reintroducing
the bug it catches. One of them was a bad test first: `every sampled band gets
a folder` kept the whole cohort, so another student in the same band had work
and `copytree` made the folder anyway — it passed against a build with the fix
removed. Narrowing the frame to the one student is what turned it into a test.

**PS4001 is the only fixture where a pack spans two assessments**, because it
is the only module with two marked courseworks. PS4003 has one, so its test
asserts `copied == {"cw1"}` and cannot catch a pack that quietly holds one
assessment's work when the module has two. The walkthrough moderates PS4001 as
well for exactly that reason.

### The Excel round trip

`distribute_feedback_sheets`, `save_grader_sheets`,
`save_distributed_graders` and `ingest_completed_graderfiles` are covered.
They form one loop — allocate, write a workbook per grader, mark, read back —
so the test that earns its keep is the round trip, not any one of them.

**No Excel needed.** These go through pandas and openpyxl, not xlwings, so
they run on Linux CI as well as on Windows. Only the `excel`-marked tests
need a real installation.

**`input()` is gone from the package.** Three of the four prompted on stdin
before replacing a file. That made them untestable without faking stdin and,
more to the point, unusable from the dashboard — `marimo run` has no
terminal, so an `input()` waits forever. Each now takes `overwrite: bool =
False` and raises `FileExistsError`, the same refusal `init_module` makes and
for the same reason.

What was wrong, all of it silent:

- **Student ids were destroyed on the round trip.** A column of digit
  strings goes to Excel and comes back `int64`: `'00123456'` → `123456`. The
  leading zeros are gone, and merging against the class list does not
  mismatch quietly — pandas raises `You are trying to merge on object and
  int64 columns`. Id columns are now read as text explicitly (`ID_COLUMNS`).
  This is the one that would have been faithfully carried into polars.
- **`save_distributed_graders` wrote a phantom index column** when
  overwriting: `index=False` on the first write, omitted on the second. The
  spurious column then travelled into every downstream read.
- **`ingest_completed_graderfiles` died confusingly on an empty run.**
  `pd.concat([])` raises `ValueError`, only `pd.errors.MergeError` was
  caught, and the fall-through returned an unbound name. A missing grader
  file is now refused outright (`require_all=True`) — missing files mean
  missing marks — or warned about if you opt out.
- **`save_grader_sheets` crashed on Enter**: `choice[0]` on an empty string
  raises `IndexError`, and the `or choice == ""` after it was unreachable. It
  also swallowed every exception into a `print`, so a failed write was
  indistinguishable from a successful one.
- **`distribute_feedback_sheets` only matched the parenthesised UL folder
  form**, so it silently found nothing on a fresh Brightspace download and
  had to be preceded by `alphabetise_folders`. Nothing said so. It now
  accepts both forms, reusing `parse_brightspace_folder`.
- **Group distribution hardcoded the word "Team"**, so a module calling them
  "Group 1" got no feedback sheets at all.

All four now return what they did rather than printing it — a `Distribution`
namedtuple, a dict of paths, a path. The dashboard cannot read stdout.

One test was written, watched to pass against the *broken* code, and
rewritten: the partial-write guard put the file clash on the first grader, so
the refusal fired before anything was written and a per-file check passed by
luck. Moving the clash to the last grader made it a real test. Worth
remembering that "reintroduce the bug" catches bad tests, not just bad code.

### The reconciliation, in code

**A disagreement says whose it was.** The comparison carries `grader` across
from the collated record, because a row naming a student and two numbers
leaves the module leader searching five workbooks for that student id to
find out whose slip it was — and the answer was in the collated file the
whole time. The merge had been selecting `[Student ID, Mark]` and throwing
the rest away.

`carry=` takes any columns; the grader is the default, and anything the
collated file has not got is skipped rather than raising, because a file
collated before the allocation wrote that column is still a valid record of
what the department was sent. A column the received frame already has is
skipped too — merging it comes back as `grade_x` and `grade_y`, and the
comparison would then be reading one of them without saying which.


The process itself is in **The domain → The lifecycle of one assessment**;
this is what it looks like from the code, which reads as though
`catch_grades` and `ingest_completed_graderfiles` were alternatives. They are
not — they are the two halves of one audit, run by different people, and
running only one gets you numbers without the control.

`notebooks/grading_walkthrough.py` walks it, labelled by who does each step.

Not every disagreement is a fault. A student who never submitted is still
allocated a grader from the class list, so they reach the collated file but
have no feedback sheet to read — `right_only` on the merge.

**Known gap in the fixture.** A real feedback sheet holds a *formula* in the
grade cell, and `extract_studentid_grade` reads the *cached* result — which
only Excel writes when it saves. A sheet generated programmatically and never
opened in Excel has a formula and no cached value, so openpyxl returns None
and it falls through to the xlwings recalculation path. The synthetic sheets
in `tests/fake_module.py` hold literals, so **nothing in the suite exercises
the formula path or the xlwings fallback**. Deliberately not fixed: doing so
either breaks the Linux tests or needs a real Excel. Recorded so it is not
rediscovered as a surprise.

### The assessment folder layout

An assessment's sub-directories are now fields, so `module.toml` records the
layout and `init_module` creates it:

```
assessments/cw1/
    Feedback sheet BLANK.xlsx     the author's
    distributed.xlsx              the allocation, at the assessment root
    submissions/                  the unzipped Brightspace download
    grading_output/               grader workbooks, completed_grades.xlsx
```

`grading_output` holds only what the tool writes, so it can be deleted and
regenerated without touching anything the author or Brightspace put there.

**Field holds a name, property adds `_path`.** Same shape at every level, which
is what makes the model readable:

| field | default | property |
|---|---|---|
| `folder` | the assessment id | `folder_path` |
| `submissions` | `"submissions"` | `submissions_path` |
| `grading_output` | `"grading_output"` | `grading_output_path` |
| `rubric` | — | `rubric_path` |

The directory field cannot be called `graders`: `Assessment.graders` is already
the list of `Person`.

Every field has a default, so a `module.toml` written before they existed still
loads and gets the conventional layout.

**Assessments are bound on load.** An `Assessment` holds relative names only and
has no idea where the module sits, so `Module` pushes `assessments_dir` down
into each one in a `model_validator(mode="after")`. That is what lets
`a.submissions_path` be a property rather than a method every call site hands
the root to. An unbound `Assessment` raises rather than returning a path
relative to the cwd.

The bound root is a **`PrivateAttr`, not a `Field(exclude=True)`** — private
attributes are left out of serialisation automatically. That matters for
`model_dump_json()`, which is how a module gets inspected in a notebook; a
bound root there would paste one machine's absolute path into whatever it
lands in. The *file* is protected by a different rule — `save` only updates
keys already present — which is why a test asserting only on the file passes
even when the root is a serialisable field. That test was written, seen to
pass against the broken version, and rewritten to assert on `model_dump`
instead.

### Renaming back for re-upload

`brightspace_name_folders` had no tests, and did not do what its name says:
folders came back **upper-cased**.

    27236-46025 - 23304302 Barry - 01 March 2026 600 PM     went in
    27236-46025 - 23304302 BARRY - 01 MARCH 2026 600 PM     came back

11 of 12 on the sample cohort. It upper-cased both log columns *in place* for
case-insensitive matching, then used the upper-cased `Original Name` as the
new folder name. **Upper case belongs in the lookup key, never in the value
written** — those are two different things, and conflating them is the whole
bug. Matching is still case-insensitive, so a folder whose case someone
touched by hand still matches and is still restored properly.

It now round-trips byte for byte: 0 of 12 differ. Also fixed alongside, since
they came from the same lines: it no longer mutates the frame it is handed,
the bare `except Exception` is narrowed to `OSError` (a rename fails for
filesystem reasons; anything else is a bug that should surface), and it
returns a `Restoration` rather than printing — what was renamed, what was
already correct, what was unrecognised, what failed.

The guarantee the tests hold is the round trip: what Brightspace gave us,
`alphabetise_folders` renamed, and this hands back character for character.
Written red first, and all seven failed against the old code.

#### The damage outlives the defect

The bug is fixed; a log written while it was live is not. `alphabetise_folders`
**appends** to `folder_rename_log.csv` and never clears it, so `Original Name`
is a permanent record of what the folders were called the first time they were
alphabetised. Folders renamed by the broken version and alphabetised again put
upper-cased names into the log *as though Brightspace had written them that
way*, and every restore since puts them faithfully back. Correct code, poisoned
data.

That surfaced as a real report — the originals were still coming back
upper-cased — and the first fix for it was `.title()` on the logged name. It
makes the symptom disappear and quietly costs more than it saves:

| stored | restored |
|---|---|
| `MACDONALD` | `Macdonald` |
| `MCGRATH` | `Mcgrath` |
| `O'BRIEN` | `O'Brien` |
| `612 PM` | `612 Pm` |

In a department where those are ordinary surnames, that is not a cosmetic
difference. Three tests caught it, which is the round-trip guard doing exactly
the job it was written for.

So `brightspace_name_folders` now **refuses** a log it can tell Brightspace did
not write, before renaming anything: `StaleRenameLogError`. The tell is that
Brightspace writes the month out in full, so a real name has lower case in it
somewhere — an all-caps surname alone is not enough to trip it.
`alphabetise_folders` warns about the same rows when it appends to such a log,
because by the time the restore refuses, the append has already happened. The
only real recovery is to delete the log and re-download; nothing can
reconstruct a name that was overwritten.

### The two steps the page was missing

Run against a real module, the marking page had no way to do three of the
things a leader actually does first. Two were genuinely absent and the third
was a symptom of the first.

**Reading the class list.** It was read silently by a cell, and every
marking step is blocked behind it. A path in `module.toml` that is wrong --
or a file that has not been downloaded yet -- therefore left the page with
nothing to do and no way forward except hand-editing the toml, which is the
thing the app exists to replace. There is now a file browser beside it, and
**picked wins over remembered**: the remembered value being wrong is the
whole reason the control exists, so it cannot be the one that always wins.
`Remember this class list in module.toml` writes it back, relative to the
module folder -- an absolute path is refused, because these folders live
under OneDrive where it differs per machine.

That write has one honest limit. `ModuleFile.save` updates keys already in
the file and does not add new ones, because appending to a table moves the
comment that follows it. So a module with no `classlist` line under
`[paths]` gets a refusal naming the line to add by hand, rather than a save
that reports success and changed nothing.

**Collecting the groups.** Nothing ran `build_group_membership`. The panel
now shows the sheets it can see and collects them, and the join against the
class list runs with it -- which is where a mistyped id or a student left
off every sheet is named, and both are much cheaper to fix before the
graders have workbooks. For a Brightspace-managed assessment there is
nothing to collect and it says so, reporting instead whether the group
column arrived in the class list. **The step appears only for a group
assessment**: a dead button on an individual one would say there is
something to do.

**Allocating.** This button was already there. It was blocked behind the
class list, which is the first item above; the fix was that one, not a
second button. `blocking` gained one reason of its own -- a leader-managed
group assessment with no sheets folder now says so up front rather than
failing inside the step.

#### Where the group sheets are, and recording the answer

`group_sheets` defaulted to a folder called `groups/` and the model treated
it as one -- `init_module` created it, and the page listed what was in it.
A leader who keeps every team in one workbook is at least as common as one
who keeps a file per team, and `collect_group_membership` always read
either. So a real module with `Assignment 1/groups.xlsx` beside it got
*"0 sheet(s) in `groups/`"* about a file sitting right there.

`group_sheets` now names **a file or a folder**, decided by
`group_sheets_is_file` -- **by the suffix, not by what is on disk**. It has
to answer before the file exists, because `directories` uses it to decide
what `init_module` creates, and creating a *directory* called `groups.xlsx`
over the top of the leader's workbook name is a mess to undo.

That was the smaller half. The bigger one: the module had no `group_sheets`
key **at all**, and `save` will not add one.

##### Adding a key the file has not got

`save` updates keys already present and never adds one, because appending
puts the key *after* the table's trailing trivia and tomlkit binds that to
the table it follows:

```toml
[[assessment]]
id = "Assignment 1"

# ---------------------------------------------------------------------------
# Where things live, relative to this file.
# ---------------------------------------------------------------------------
group_sheets = "groups.xlsx"     <- appended here
[paths]
```

The comment now reads as part of the assessment and the new key is orphaned
below it. Reproduced in four lines of tomlkit before anything was built on
it.

That is a good default and a bad limit: **a form that cannot record its
answer asks the same question every time**. `add_key` inserts *above* the
trailing trivia instead -- walk back over the body entries that have no key
of their own, which is exactly the whitespace and comments, and insert
there. `ModuleFile.set_assessment(id, **keys)` and `set_paths(**keys)` are
the explicit "I mean to add this" calls; `save` stays conservative, because
most saves are not adding anything and should not be able to.

Two details that are not decoration. The insert goes **through the model**
first, so `module.toml` cannot be given something the model would not load
back -- and a value it rejects leaves the file untouched. And when nothing
trails the last key, `at == len(body)` and tomlkit's `_insert_at` refuses an
index past the end, so that case appends, which is both correct and the only
thing available. The second was found by a test, not by reading.

##### On the page

The Groups panel has a file picker, and **picked wins over remembered**, for
the same reason it does for the class list. `Remember this in module.toml`
writes `group_sheets` relative to the assessment's own folder. The class
list's remember now goes through `set_paths`, so it adds the key too --
last time round it could only refuse and name the line to type.

#### "folders there: 0" meant four different things

The assessment panel counted the directories immediately inside
`submissions/` and printed the number. It printed **0** for a folder that is
not there, a folder with nothing in it, a download still sitting in its zip,
and a download unzipped one level too deep -- four situations wanting four
different things done, reported identically. The last is the common one:
extracting the zip makes a folder named for the download and puts the
student folders inside *that*, and every step here iterates the directories
immediately inside `submissions/`, so it finds nothing and says nothing.

`submissions_state(path)` now returns the count **and what is wrong**, and
names the wrapper folder when it finds one. Distribution blocks on "there
are no student folders in `<path>`" rather than "there is no submissions
folder at `<path>`", which was a false statement about a folder plainly
sitting there and sent the reader looking in the wrong place.

The one-folder test is `len(folders) == 1 and any(p.is_dir() for p in
folders[0].iterdir())`, not `len(folders) == 1`: a cohort of one, or the
last folder left after resolving the others, is a student folder, and a
student folder holds files rather than folders.

#### `is_dir` on a thing that may be a file

`group_sheets` was made to name **a folder of sheets or one file**, and the
step that blocks allocation kept asking `is_dir()`. So a module with
`group_sheets = "groups.xlsx"` -- collected, 85 students in 43 groups,
written to `group_membership.csv` -- was told *"there are no sheets at
…\groups.xlsx"* about a workbook sitting exactly where it had been asked
for. `exists()`, and the message says "nothing at" rather than "no sheets
at", which is true of both shapes.

Two things worth keeping from it. The check now resolves through
`groups_where`, so a file **picked on the page but not yet remembered**
unblocks the step as well -- picked wins everywhere or it wins nowhere. And
the reason it survived a change that was specifically about files is that
the test for it used the folder layout: the feature grew a second shape and
its guard was only ever exercised in the first.

#### The one place a test cannot reach

The group panel's table was `sizes.rename("students").reset_index(names="group")`.
`names=` is a **DataFrame** argument; `Series.reset_index` has never had it.
It raised the moment somebody pressed the button, on the first real module
it was run against, having passed every test in the suite.

It passed because it sat **inside a button guard**. `the_steps` exists
precisely so that does not happen -- its docstring says the work is there
"so that it can be driven by something other than a click" -- and I put
display logic in the guard anyway. Nothing in the suite executes a guard
body: `App.run()` runs the cell, the guard is False, and the line inside is
never touched.

So the rule is not "test the buttons", which cannot be done. It is: **if a
line can fail, it does not belong in a guard.** `group_sizes(membership)`
sits in `the_steps` with everything else and has a test that builds the
table. Reintroducing the broken line fails it.

The same review turned up that the ids named in the sheets but not on the
class list reached only the terminal, as a Python warning. That is the other
half of a mistyped id, and it is not where somebody clicking a button is
looking, so `collect_groups` returns them and the panel shows them.

#### The crash it turned up

`import_brightspace_classlist` returns `None` rather than raising for a file
it cannot make sense of, and the page did `len(frame)` on the result. A real
class list that would not parse -- the wrong export, a spreadsheet of
something else -- took the **whole page** down with a `TypeError`, which is
the one thing a step may not do. Handled, and covered.

Both new actions live in `the_steps` with the others, for the reason given
there: a test cannot click, but it can call exactly what a click calls. The
file-browser selection cannot be driven that way at all, so the choice it
feeds is a returned function (`class_list_choice`) and the test drives that
instead. Six guards verified by reintroducing the bug: the picked class list
ignored, the unparseable one unhandled, an absolute path written to
`module.toml`, a no-op save reported as success, the group join skipped, and
missing group sheets not blocking allocation.

### Who to follow up

Two lists get read *off* the finished departmental sheet and acted on, and
both were being worked out by eye over eighty rows.

**Repeats** — everyone at **F or NG**. Both, not just F: NG is no
participation where F is work that did not pass, and the difference matters
in the conversation, but the conversation happens either way.

**Borderlines** — everyone within a mark of the next band. One mark because
the sheet's totals are whole numbers, so "within one" means one more mark
would have moved them. `flag_borderline` has computed this since the
moderation sample was built and **nothing outside moderation ever looked at
it**, which is the whole of the change: the machinery existed and was
reachable from one place only.

`write_outcomes` writes both beside the module, named for it —
`PS4034 repeats.csv`, not `repeats.csv`, because these get attached to
emails and the reader needs to know which module's. Whole rows, not just the
totals: the per-assessment marks are what say *why* somebody did not pass,
and a repeat conversation starting from a total alone starts by going back
to the sheet.

Neither list is a decision. They are the students a decision is due about,
written down so it is made from a list rather than from a scroll.

Two guards worth naming. Both files are checked before either is written --
one list current and the other from the last run is worse than neither. And
`outcomes_written` is satisfied by **the files existing**, not by anyone
being on them: a cohort where nobody failed and nobody sat on a boundary is
a fine result and the step still ran, so counting it as not-done would leave
a tick missing on a module that is finished.

Still by hand, and worth knowing: the repeat list carries no **email
address**. `import_brightspace_classlist` selects four columns and drops
`Email`, which the Brightspace export does carry.

### Simulating the marking

Everything after allocation needs marks to exist, and producing them by
marking real work is not a thing you can do twice. `grader_helper/simulating.py`
is the stand-in for **steps 5 and 6** -- the grader writing a mark on the
feedback sheet, and the grader copying it into their own workbook:

```
uv run simulate-marking ~/scratch/PS4001                 # the plan
uv run simulate-marking ~/scratch/PS4001 --write         # do it
uv run simulate-marking ~/scratch/PS4001 -a cw1 -d 2 --write
```

**It also takes folders.** A set of files extracted from a past module is a
download and some grader workbooks sitting where somebody put them; there is
no `module.toml` to load and no assessment layout to resolve paths against:

```
uv run simulate-marking -s "PS4001 CW1/Downloads" -c D30 \
                        -w "PS4001 CW1/Grader sheets" --write
```

`simulate_marking_in(submissions, grade_cell, ...)` is the folder form and
does the work; `simulate_marking(assessment, ...)` is a thin wrapper that
reads the two folders, the cell and the scale off the assessment. Written
the other way round first, and the folder form had to be extracted out of
it -- an assessment is one way to know where the files are, not the only
one.

`--cell` is required with `--submissions`, because the cell a mark goes in
is the one thing about a feedback sheet that cannot be worked out by
looking at it, and it has to be the cell `catch_grades` reads back.
Without `--workbooks` only the feedback sheets are marked, which is one
record and leaves reconciliation nothing to compare -- so it says so.
Which graders are involved is read off the folder: everything in it that is
not `completed_grades`, `distributed` or `group_membership` is somebody's
workbook.

Nothing else needed this. `import_brightspace_classlist`,
`collect_group_membership` and `load_graders` already take a path to a file
and always did.

**It writes both records, not one.** They are two records and step 7 exists
because they can disagree, so `--discrepancies N` has the grader *mistype* N
of them into their workbook while the sheet keeps the mark the student
received. Without that, every reconciliation trivially passes and
`reconcile_marks` can never be seen working. With it:

```
  cw1: wrote 12 feedback sheet(s) for 11 student(s), 1 planted discrepancy
      planted: 23304305 sheet 39.5 vs workbook 29.5
```

and `reconcile_marks` names exactly that student.

**The marks are not uniform, and not entirely random.** A uniform cohort
puts a tenth of the class in every band, which makes a stratified moderation
sample look easy and a grade distribution look like nothing. So the draw is
roughly where a psychology cohort sits -- mean 0.58 of the scale, sd 0.15 --
and `--boundaries N` *plants* N marks on the values the arithmetic can get
wrong and a random draw almost never hits: every band edge, zero (which is
NG, not F), and the halves Python and Excel round in opposite directions.
`round(64.5)` is 64 and Excel's is 65, and 64 is a B3 where 65 is a B2. A
cohort with no exact halves in it never tests the rule this project has a
house note about.

#### `--explain`, because guessing was not working

Four rounds went on why a real module's sheets were not being marked, and
the answer in the end was that **the writer had never run**: `--explain` was
on the same command line as `--write`, returned before writing anything, and
printed a report that looked exactly like a successful run. The two are
refused together now -- a warning at the top of a long report is missable,
and there is nothing legitimate that wants both.

Worth keeping in view: of the guesses made along the way, the ones about the
*code* were checked and mostly wrong, and the one thing never asked for was
the output of the failing command. Diagnosis over a wire is not the same
activity as debugging, and the difference is which questions get asked.



Four separate guesses about why a real module's sheets were not being
marked all turned out to be about **what was in the grade cell** -- which
nobody can see from here and everybody can see from there. So:

```
uv run simulate-marking <module> -a cw1 --explain
```

lists every sheet it finds, what its grade cell holds, what the blank rubric
holds, and whether it would write or skip and why. It writes nothing -- and
refuses to be combined with `--write` for that reason -- and it
reports an empty folder rather than refusing to run -- refusing is the
opposite of a diagnostic's job.

`explain_sheets` is a function returning a frame, not printing: the printing
is the part that cannot be tested, so it does as little as possible.

The same pass widened the sheet glob to `.xlsx`, `.xlsm`, `.xlsb` and
`.xls` -- the set `catch_grades` already read. A rubric saved as `.xlsm` was
findable by the reader and invisible to the writer, which is a difference
nothing should have.

#### "Holds a number" is not "has been marked"

Every feedback sheet in the suite had an **empty** grade cell, because that
is what `fake_module` writes. A real rubric *calculates* its total from
criterion cells, so the moment Excel saves it the grade cell caches a result
— usually `0`, the sum of criteria nobody has filled in yet.

`_already_marked` asked "is there a number here", which is true of every
distributed sheet from the moment it is distributed. So a run over a real
module skipped **all** of them, silently, while still filling the grader
workbooks — the exact shape of the failure this package spends its guards
on, because the result is plausible: marks in the department's record and
none on the sheets the students receive.

The test is now "is it a *different* number from the one the blank sheet
has", with the blank rubric read once per run. `assessment.rubric_path`
supplies it; `--blank` does for the folder form. Without one it falls back
to the old rule, which is right for a sheet this package wrote.

Two things fell out of getting that right. **What the grader copies is what
is on the sheet**, not what was drawn: a skipped sheet keeps the mark it
already had, and reporting the drawn one instead would reconcile as a
disagreement the simulator invented rather than one it found. And a
discrepancy can only be planted on a sheet that was actually written, for
the same reason.

**A sheet that will not take a mark is reported, not raised.** A run over a
real cohort writes eighty-odd files; dying on the fortieth leaves half of
them marked with no record of which half, which is worse than any one sheet
failing. The one that actually happens is a **merged** grade cell -- openpyxl
writes only to the top-left of a merged range, and a rubric that spreads the
total across two columns puts the grade cell elsewhere in it. The message
names the cell that *can* be written rather than passing on `'MergedCell'
object attribute 'value' is read-only`, which is not a sentence about a
feedback sheet.

A mark that never reached a sheet is then **left out of the grader's
workbook too**. A grader does not copy a mark they never wrote, and leaving
it in would reconcile as a disagreement -- an empty sheet against a workbook
mark -- which is a fault the simulator invented rather than one it found.

Three things it will not do to a module:

- a feedback sheet whose grade cell already holds a **number** is skipped,
  so a part-marked assessment survives a careless run;
- a `Mark` a grader has already written is left alone;
- the command line **shows the plan and writes nothing** without `--write`.

Writing a number into the grade cell *replaces the formula there*. That is
unavoidable -- a real rubric totals criterion cells this knows nothing about
-- and it is the reason to point it at a copy.

#### Two things it found

**A resubmission is two sheets.** The first version keyed sheets by student
id into a `dict`, so a student with two submission folders had one of their
two sheets marked and the other left blank. `catch_grades` reads every sheet
it finds, so the result was a warning about an empty cell on a student who
had been marked. `feedback_sheets` returns a **list per identifier** now.
Resubmissions are a normal state -- nothing renames those folders until
somebody decides which counts -- so this is the shape, not an edge case.

**One seed is not one cohort.** Two `Random(seed)` objects make the same
first choice, so drawing the boundary marks and choosing who mistypes one
off separate streams put every discrepancy on a planted mark, every run. One
stream, threaded through. And one seed for the whole *module* gave every
student the same mark in cw1 as in cw2 -- reproducible and useless, because
the total then equals the component and a weighting bug looks exactly like a
correct answer. The command line derives a per-assessment seed with
`zlib.crc32` of the id, rather than `hash`, which is salted per process.

Every guard was verified by reintroducing the bug: only the last sheet per
student marked, the discrepancy dropped, the slip written to the sheet as
well as the workbook, separate random streams, already-marked sheets
overwritten by default, a dry run writing anyway, and a grader's own mark
clobbered.

### The fake module, and the end-to-end test

`tests/fake_module.py` writes a complete module to disk: `module.toml`, a
Brightspace class-list export, a submissions tree in Brightspace folder
format, and **real `.xlsx` feedback sheets with real numbers in `D30`**.
`tests/test_end_to_end.py` drives it from unzipped download to departmental
grade sheet.

The workbooks being real is the point. Everywhere else in the suite
`extract_studentid_grade` is monkeypatched out, so this is the only place the
Excel read itself is exercised. Swapping the workbooks for empty placeholders
— which is what the older fixtures wrote — collapses the end-to-end test, so
it is genuinely testing the read.

The fixture holds the marks it wrote, so the test asserts the pipeline gives
back what went in rather than merely running. The cohort is chosen, not
random, and the awkward cases are deliberate:

| student | why |
|---|---|
| 23304305 | totals exactly 64.5 — Excel 65 (B2), Python 64 (B3) |
| 23304309 | scored 0 throughout → NG, not F |
| 00123456 | a leading zero, destroyed by an unguarded Excel round trip |
| 23304311 | in the class list, never submitted |
| 23304307 | submitted twice |

Plus a `__MACOSX` folder and a stray `index.html`, which every real download
has.

It runs as a pytest fixture (`fake_module`), and standalone for a notebook:

```
python tests/fake_module.py ~/scratch/PS4001
```

`quizzes=True` swaps the MCQ for eleven weekly quizzes and their exports —
see **Quiz collection → The fixture** for how the exports are generated and
why the swap costs the coursework path nothing. Off by default, so
`fake_module` is unchanged.

Two things the walkthrough surfaced, neither a bug:

- **A non-submitter and a student who scored zero are indistinguishable on
  the sheet.** Both come out `NG`. That is faithful to the departmental
  sheet, which computes `IF(ROUND(total,2) > 0, <bands>, "NG")` and cannot
  tell them apart either — but it means the sheet alone does not tell you
  which happened.
- **`catch_grades` reads whichever feedback sheet it finds**, so a
  resubmission needs resolving before marking, not after. `scan_multiple_subs`
  finds them; nothing yet decides which one counts.

### Known gaps

- `make_sub_date` cannot parse `"0000 AM"` (`%I` is 12-hour). Brightspace
  appears to use `"1200 AM"`, so it may never bite. `xfail`.
- `assignment/visualise.py` defines its function inside `main()`, so it is
  unreachable and unexported. Delete or fix; do not port.
- `alphabetise_folders` returns `None` and hands off to
  `brightspace_name_folders` through `folder_rename_log.csv` rather than
  through a value. Worth knowing before looking for a return value that is
  not there.
- **No external examiner pack.** The internal pack is built and keeps its
  manifest, which is what an external pack has to be assembled over — but
  nothing assembles one yet. `Assessment.status.moderated` is still not set
  by anything either; `build_moderation_pack` writes the manifest but does
  not mark the assessment moderated, because a pack having been *built* is
  not the same as it having been *read*.
- **A Brightspace-managed group assessment cannot reach the grade sheet
  yet.** Its marks come back keyed by group and nothing expands them onto
  the students. See **Next**, item 7 — it is the next chunk, not a defect in
  what is there.
- **The walkthrough notebook has no group assessment in it.** cw1, cw2 and
  the quizzes are all individual. The dashboard can now run a leader-managed
  one and the suite drives it, but nothing a person steps through by hand
  covers the group path. Worth adding once item 7 lands and a
  Brightspace-managed group assessment runs the whole way too.
- **The repo-root shim covers the public API but not submodules.** The repo
  directory is itself called `grader_helper`, so with its parent on
  `sys.path` an `import grader_helper` finds `./__init__.py`, which
  star-re-exports the package. `from grader_helper import catch_grades`
  therefore works and the breakage stays invisible until something imports a
  *submodule* -- `tests/fake_module.py` does
  `from grader_helper.dataframe_operations import ...`, which the shim has no
  path for. It bit `test_walkthrough.py`, which works around it by dropping
  the stale binding; `test_import.py` does not catch it because it checks in
  a subprocess. Giving the shim a `__path__` would close it properly.
- **A blank mark is a zero to the sheet.** Excel's `SUM` reads an empty cell
  as nothing, so a student with one component unmarked gets a total as though
  they had scored nil on it, and a letter grade computed from that. This is
  the department's arithmetic, not ours, and it is not ours to change — but it
  means a sheet written before all the marking is in reads as a complete set
  of low grades. `write_departmental_sheet` leaves a missing mark blank rather
  than writing 0, so at least the empty cell is visible.
- **The Excel check now passes, and left one piece of noise behind.**
  `test_excel_computes_what_we_compute` had only ever been skipped. Run on
  Windows against a real Excel it passes: **413 passed, nothing skipped**.
  Excel's `Total % Grade` and `Letter Grade` agree with
  `prepare_data_for_departmental_template` on a generated sheet, so the
  formulas the builder emits compute what we compute — not merely what
  openpyxl can see, which is all every other test in that file can check.
  Linux still reports 412 passed and 1 skipped.

  Two pieces of console noise it does not mean anything by. The
  `Reading feedback: 100%|...| 11/11` lines are `tqdm` progress bars from
  `catch_grades`, which write to stderr. And openpyxl warns `Unknown
  extension is not supported and will be removed` on every read of the
  template: the extension is `mx:PLV`, Excel for Mac's **page-layout view
  preference**, recorded by whoever last had the file open on a Mac. It is a
  view setting, not data or a formula, so dropping it costs nothing.

  Reading that XML did turn up something worth covering, though. The SD row
  is stored as a dynamic-array formula (`<f t="array" ref="C24">` around
  `_xlfn.STDEV.S` over `_xlfn._xlws.FILTER`), the builder regenerates it, and
  openpyxl can only confirm the *text* is right. Whether Excel still
  evaluates it in a rebuilt file rather than showing `#NAME?` is only
  answerable with Excel, so `test_excel_computes_what_we_compute` now checks
  the Mean, SD and N as well as the total and the letter grade.

  The run prints `Windows fatal exception: code 0x800706ba`
  (`RPC_S_SERVER_UNAVAILABLE`) with two thread dumps, and then passes. It is
  COM teardown: `app.quit()` ends Excel, a lingering proxy is touched
  afterwards, and pytest's `faulthandler` dumps the SEH exception before it
  is handled normally. Cosmetic, but it reads like a crash. Not quietened,
  because no machine here has Excel to tell a real fix from one that merely
  moves the noise. It stops being cosmetic if stray `EXCEL.EXE` processes
  start accumulating; `app.kill()` after `quit()` and `add_book=False` are
  the things to try then.
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
  seen to fail is not yet a test. It catches bad *tests*, not just bad code:
  the partial-write guard on `save_grader_sheets` passed against a knowingly
  broken version, because the file clash was on the first grader and the
  refusal fired before anything was written. The test was asserting nothing.
