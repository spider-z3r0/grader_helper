# The dashboard — scope notes

Written to start a fresh session on the app. The library is finished enough to
sit under one; this records what was decided, what is still open, and what a
cold start needs to know before proposing anything.

**Read this, then `docs/development-notes.md` → "Keeping status".** Everything
else in the notes is reference for when you touch that part of the library.

---

## Where the library got to

The whole pipeline runs end to end. `notebooks/grading_walkthrough.py` drives
it across three modules of different shapes and the suite runs the notebook,
so it is a working reference for the call sequence rather than a document that
was true once.

| step | function | returns |
|---|---|---|
| read the class list | `import_brightspace_classlist` | frame |
| allocate graders | `assign_graders_individual` / `_groups` | frame |
| write grader workbooks | `save_grader_sheets` | dict of paths |
| save the allocation | `save_distributed_graders` | **`Allocation`** |
| distribute feedback sheets | `distribute_feedback_sheets` | **`Distribution`** |
| alphabetise / rename back | `alphabetise_folders`, `brightspace_name_folders` | `None` / paths |
| read marks off the sheets | `catch_grades` | frame |
| collate the grader files | `ingest_completed_graderfiles` | frame |
| write the collated file | `save_collated_grades` | **`Collation`** |
| collect quiz marks | `collect_quiz_marks` | frame |
| collate the module | `collate_module_marks` | frame |
| total and band | `prepare_data_for_departmental_template` | frame |
| lay out the dept sheet | `build_departmental_sheet` | path |
| write marks into it | `write_departmental_sheet` | **`DepartmentalWrite`** |
| flag borderline students | `flag_borderline` | frame |
| draw the moderation sample | `sample_for_moderation` | **`Sample`** |
| build the moderation pack | `build_moderation_pack` | **`Pack`** |
| fill SI's upload | `write_si_marks` | **`SiUpload`** |

The bolded returns carry evidence and are what `ModuleFile.record()` reads.

### Three fixture modules, deliberately different shapes

- **PS4001** — cw1 (100/40), cw2 (100/50), weekly quizzes (10/10). The
  template's own shape, two marked courseworks, so the only one whose
  moderation pack spans more than one assessment.
- **PS4002** — cw1 (100/30) and two MCQs worth 35, one marked out of 100 and
  one out of 10. Exists to exercise the sheet builder on a block the
  departmental template has no room for.
- **PS4003** — coursework, quizzes, MCQ, exam. The only module where marks
  arrive by three different routes in one collation.

`tests/fake_module.py` builds all three, including a faithful blank SI export.

---

## Built already — do not redesign these

`notebooks/module_dashboard.py`, on `inspect_module_folder`. It opens a module
folder or sets one up, and shows what is in it. See **Pointing at a folder** in
`docs/development-notes.md` for the reasoning; the short version:

- Pointing at a folder has **four** answers — loaded, uninitialised,
  unreadable, missing — and `can_initialise` is true for *uninitialised* only.
  A `module.toml` that will not load is never offered setup, because that
  would mean `overwrite=True` over the module's memory to fix a typo.
- `inspect_module_folder` never raises. A dashboard cell runs on every click.
- The setup form asks for the module, then *n* rows of assessment —
  including the graders, the blank feedback sheet and the mark cell, so a
  module set up in the app is runnable without hand-editing. Validation stays
  in the model: the form shows the running weight total, `init_module`
  refuses everything else and its message is displayed.
- The page names any assessment missing what marking needs, and exempts the
  ones collected from Brightspace.

What is **not** built: running any step from the page. That is the next chunk,
and it is where the scratch copy below has to be designed.

## Decided

### The app writes to a scratch copy and promotes

Steps run against a copy; a deliberate action publishes the result to the real
module folder. This is the answer to "what can a mis-click during an exam
board reach", and it is the single biggest thing to design.

**The principle is settled. The mechanics are not**, and the app session has
to work them out:

- Is the copy the whole module folder, or only the outputs? Submissions can be
  hundreds of megabytes; copying them per run is not free.
- Where does the scratch copy live? Not under OneDrive, on the same reasoning
  that keeps absolute paths out of `module.toml`.
- What does *promote* actually move — every changed file, or a named set?
- What happens to `module.toml` and its `[status]` sections? A status written
  in the scratch copy is a claim about the real module.
- How does a second run relate to the first copy — reuse it, or start again?

### One module at a time, chosen by its folder

Answered in the session that built the front door, against the three options
this file previously listed. There is **no registry and no recents list**: you
say which module you are on by choosing its folder in the browser, every time.

The reasoning, in the order it decided things. A registry of modules has to
hold absolute paths, and nothing in this package holds an absolute path,
because these folders sit under OneDrive and an absolute path is wrong the
moment it syncs to another machine. A recents list is a new file to keep
correct, and its entries go stale silently — a module that moved is a path
that points at nothing, and the failure looks like the module being gone. And
scanning a modules directory assumes a layout nobody follows: the real one is
`teaching/<year>/<semester>/<code>`, where the same code appears under several
years.

Two environment variables take the tedium out of browsing without storing
anything: `GRADER_HELPER_START` opens the browser at, say, `teaching/`, and
`GRADER_HELPER_MODULE` opens straight onto one module. Neither is written by
this package.

**Deliberately deferred: rolling a module forward a year.** `PS4034` under
2025 and under 2026 is the same module run twice, and starting next year from
last year's file — assessment shape, weights, quiz rules and people copied,
status flags reset, marks dropped — is wanted, but not before the steps run.

### Both users, in that order

Build it as Kev's own tool first, replacing the notebook. Harden it for a
non-technical module leader second, once the shape is proven. The second phase
is a real chunk of work — plain-language errors, no reachable destructive
action — and should not be smuggled into the first.

### Status is already wired for it

`ModuleFile.record(result, assessment_id=None)` sets a flag from what a step
returned. `set_status` / `set_module_status` are the manual half. The split is
by one question: **can the code honestly know?**

| the code sets | a person presses a button |
|---|---|
| `sheets_distributed` | `moderated` (per assessment) |
| `departmental_sheet_written` | `sent_to_department` |
| `moderation_pack_built` | `si_submitted` |
| `si_file_written` | |

So the app's buttons are already enumerated: three of them.

Every assessment flag but `moderated` now comes from an artefact, so the app
does not have to set any of them itself — it calls the step and passes the
result to `record()`.

---

## Open — needs deciding in the app session

### Everything else worth settling early

- **`marimo run` or `marimo edit`?** `run` serves it as an app with no editing
  and no autosave, which is what a colleague should get — and what stops the
  notebook file being rewritten every session, which happened repeatedly while
  building this.
- **Running a step twice.** Partly answered by existing refusals:
  `build_departmental_sheet`, `save_grader_sheets` and `build_moderation_pack`
  all refuse rather than overwrite, and `build_moderation_pack` refuses
  *merging* specifically. The app has to decide whether a button offers
  `overwrite=True` and how loudly.
- **What the app shows when a step has not run.** Status is the obvious spine,
  but a flag being `False` does not say *why* — no submissions downloaded, or
  the step simply not attempted yet.
- **Where marimo's reactivity helps and hurts.** Cells re-run on change; a cell
  that copies folders or writes a workbook should not fire because an unrelated
  widget moved.

---

## Constraints a cold start will otherwise trip over

- **Work on `develop`.** Do not create a branch.
- **`uv run`, never bare `python`.** The venv is not on the path.
- **Windows is first-class**, macOS second, Linux only for the pure-logic
  tests. Anything the app does with files has to be right on Windows —
  see the bare-LF finding in **The SI upload** for how that bites.
- **`import pathlib as pl`, `import polars as pr`.** House convention, and it
  inverts the usual polars idiom.
- **`uv run pytest -q` is 496 passed, 1 skipped, 1 xfailed** on Linux; 497
  passed with a real Excel. Green before and after.
- **The notebook is run by the suite** (`tests/test_walkthrough.py`). Anything
  that breaks it fails there rather than in front of a colleague. If the app
  supersedes the notebook, that coverage has to go somewhere.
- **Verify a guard by reintroducing the bug.** It has caught two bad *tests*
  in this repo, not just bad code.

---

## Still outstanding in the library, unrelated to the app

- The **external examiner pack** — possible now, since every internal pack
  keeps its manifest, but not built.
- Nothing sets `Assessment.status.moderated`; that is one of the app's buttons.
- `write_si_marks` has never run against a real SI file. Worth doing on a copy
  and diffing before the app depends on it.
- Full list in **Known gaps** in `docs/development-notes.md`.
