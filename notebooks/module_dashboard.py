import marimo

app = marimo.App(width="medium")

with app.setup():
    import os
    import pathlib as pl

    import marimo as mo

    from grader_helper.models import (
        COLLECTED_TYPES,
        MODULE_FILENAME,
        STARTER_ASSESSMENTS,
        WEIGHT_TOLERANCE,
        AssessmentType,
        FolderState,
        init_module,
        inspect_module_folder,
    )

    # Where the folder browser opens. Modules live somewhere like
    # OneDrive/teaching/2026/Sem1/PS4034, and clicking down to that from your
    # home folder every time gets old, so point GRADER_HELPER_START at the
    # level you actually browse from -- `teaching/`, say.
    #
    # GRADER_HELPER_MODULE goes one further and preselects a module folder.
    # It is also how the test suite drives this notebook, since a test cannot
    # click a file browser.
    #
    # Neither is stored anywhere by this tool. A module's own module.toml is
    # the only file grader_helper writes, and it holds no absolute paths --
    # these modules sync between machines, where an absolute path is wrong.
    START = pl.Path(os.environ.get("GRADER_HELPER_START", pl.Path.home()))
    PRESELECTED = os.environ.get("GRADER_HELPER_MODULE")

    #: Assessments beyond the three the starter file describes. Weighted 10
    #: rather than 0 deliberately: a fourth row must push the total off 100,
    #: so the check below says "not yet" instead of "ready" for a row that
    #: has not been filled in.
    EXTRA_ROW = dict(type="coursework", marks_out_of=100, weight=10)

    #: What a row's "collected from Brightspace" tick writes. Only a quiz or
    #: an MCQ may carry them -- COLLECTED_TYPES is the model's own rule, and
    #: it refuses them on anything else with an explanation.
    COLLECTION_KEYS = ("pass_mark", "free_passes")


@app.cell
def intro():
    mo.md(
        """
        # Module dashboard

        Point this at a module folder. It either loads the module that is
        there, or offers to set one up.

        The folder is a year's run of one module -- the thing that sits at
        `teaching/2026/Sem1/PS4034`. Inside it goes `module.toml`, which is
        the module's memory: its assessment, its weights, its graders and
        everything recorded about progress. Nothing outside that file
        remembers anything, and nothing in it is an absolute path, so the
        folder can move between machines and OneDrive accounts intact.

        That is also why this notebook has no "recent modules" list: you say
        which module you are on by choosing its folder.
        """
    )
    return


@app.cell
def choose_a_folder():
    browser = mo.ui.file_browser(
        initial_path=START if START.is_dir() else pl.Path.home(),
        selection_mode="directory",
        multiple=False,
        label="**Module folder**",
    )
    reread = mo.ui.run_button(label="Re-read this folder")

    mo.vstack([browser, reread])
    return browser, reread


@app.cell
def look_in_the_folder(browser, reread):
    # Referencing the button makes this cell re-run when it is clicked, which
    # is what picks up a module.toml written since the folder was chosen --
    # or edited by hand in another window to fix the error reported below.
    _ = reread.value

    selected = (
        pl.Path(browser.value[0].path)
        if browser.value
        else (pl.Path(PRESELECTED) if PRESELECTED else None)
    )
    found = inspect_module_folder(selected) if selected is not None else None

    if found is None:
        report = mo.md("Choose a folder above to begin.")
    elif found.state is FolderState.LOADED:
        report = mo.md(f"Loaded **{found.module.code}** from `{found.file_path}`.")
    elif found.state is FolderState.UNINITIALISED:
        report = mo.md(
            f"""
            No `{MODULE_FILENAME}` in `{found.folder}`.

            Nothing is set up here yet. Fill in the form below and this
            folder becomes a module.
            """
        )
    elif found.state is FolderState.UNREADABLE:
        report = mo.md(
            f"""
            ### `{MODULE_FILENAME}` will not load

            ```
            {found.error}
            ```

            Edit `{found.file_path}` and click **Re-read this folder**.

            That file is not offered for setting up again, and the refusal is
            deliberate: it holds this module's graders, its quiz rules and
            every status flag recorded so far. A mistyped weight is fixed by
            correcting the weight, never by starting the module over.
            """
        )
    else:
        report = mo.md(f"Nothing at `{found.folder}`. Check the path.")

    # Decided once, here, and used by every cell below. Whether to offer
    # setting a folder up is the one judgement this notebook makes, and a
    # copy of it per cell is a copy that can disagree -- the dangerous
    # disagreement being a cell that offers to overwrite a module.toml the
    # cell above it has just reported as broken.
    loaded = found is not None and found.loaded
    offer = found is not None and found.can_initialise

    report
    return found, loaded, offer


@app.cell
def the_module(found, loaded):
    def _tick(flag: bool) -> str:
        return "yes" if flag else "-"

    def _summarise(module):
        # Built as a list of lines at column zero, then joined, rather than as
        # one indented f-string. mo.md dedents by the common leading
        # whitespace, so a multi-line value interpolated into an indented
        # block sets that common indent to nothing and leaves every other
        # line over-indented -- which silently turns the headings into
        # paragraphs and the tables into text.
        lines = [
            f"## {module.code} — {module.name}",
            "",
            f"{module.year}. Led by `{module.leader}`, moderated by "
            f"`{module.internal_moderator or 'not set'}`.",
            "",
            "### Assessment",
            "",
            "| id | type | name | out of | weight | grade sheet columns |",
            "|---|---|---|---|---|---|",
        ]
        lines += [
            f"| `{a.id}` | {a.type.value} | {a.name} | {a.marks_out_of} | "
            f"{a.weight} | {', '.join(a.columns)} |"
            for a in module.assessments
        ]
        lines += [
            "",
            f"Weights sum to **{sum(a.weight for a in module.assessments)}**.",
            "",
            "### Progress",
            "",
            "| id | allocated | distributed | collected | moderated |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| `{a.id}` | {_tick(a.status.graders_allocated)} | "
            f"{_tick(a.status.sheets_distributed)} | "
            f"{_tick(a.status.grades_collected)} | {_tick(a.status.moderated)} |"
            for a in module.assessments
        ]

        # The module's own flags, not an assessment's: the things produced
        # once for the whole module. Each artefact the code can see for
        # itself is shown beside the flag saying a person did something with
        # it -- written is not sent, and only a person knows the second.
        lines += [
            "",
            "### Produced once for the module",
            "",
            "| | written | sent |",
            "|---|---|---|",
        ]
        lines += [
            f"| {label} | {_tick(automatic)} | "
            f"{_tick(manual) if manual is not None else 'n/a'} |"
            for label, automatic, manual in (
                (
                    "departmental sheet",
                    module.status.departmental_sheet_written,
                    module.status.sent_to_department,
                ),
                ("moderation pack", module.status.moderation_pack_built, None),
                ("SI upload", module.status.si_file_written, module.status.si_submitted),
            )
        ]

        missing = [d for d in module.directories if not d.exists()]
        lines += [
            "",
            "### Files",
            "",
            "| | |",
            "|---|---|",
            f"| root | `{module.root}` |",
            f"| assessments | `{module.assessments_dir}` |",
            f"| class list | `{module.classlist_path or 'not set'}` |",
            f"| departmental sheet | `{module.departmental_sheet_path or 'not set'}` |",
            "",
            "All the folders it describes exist."
            if not missing
            else "**Missing folders:** " + ", ".join(f"`{d}`" for d in missing),
        ]

        return mo.md("\n".join(lines))

    view = _summarise(found.module) if loaded else mo.md("")
    view
    return


@app.cell
def how_many_assessments(offer):
    how_many = mo.ui.number(
        start=1, stop=12, step=1, value=len(STARTER_ASSESSMENTS),
        label="How many pieces of assessment?",
    )

    mo.vstack(
        [mo.md("## Set this folder up as a module"), how_many]
    ) if offer else mo.md("")
    return (how_many,)


@app.cell
def module_details():
    code = mo.ui.text(label="Module code", placeholder="PS4034")
    title = mo.ui.text(label="Module title", placeholder="Research Methods")
    year = mo.ui.text(label="Academic year", placeholder="2025/26")
    leader = mo.ui.text(label="Module leader (initials)", placeholder="KOM")
    moderator = mo.ui.text(label="Internal moderator (optional)", placeholder="SOB")
    classlist = mo.ui.text(
        label="Class list file (optional)", placeholder="classlist.csv"
    )
    departmental = mo.ui.text(
        label="Departmental grade sheet (optional)", placeholder="grades.xlsx"
    )
    return classlist, code, departmental, leader, moderator, title, year


@app.cell
def assessment_rows(how_many):
    def _default(index: int) -> dict:
        if index < len(STARTER_ASSESSMENTS):
            return dict(STARTER_ASSESSMENTS[index])
        return dict(EXTRA_ROW, id=f"a{index + 1}", name=f"Assessment {index + 1}")

    def _row(index: int):
        default = _default(index)
        return mo.ui.dictionary(
            {
                "id": mo.ui.text(value=default["id"], label="id"),
                "type": mo.ui.dropdown(
                    options=[t.value for t in AssessmentType],
                    value=default["type"],
                    label="type",
                ),
                "name": mo.ui.text(value=default["name"], label="name"),
                "marks_out_of": mo.ui.number(
                    start=0, stop=1000, step=1,
                    value=default["marks_out_of"], label="marked out of",
                ),
                "weight": mo.ui.number(
                    start=0, stop=100, step=0.5,
                    value=default["weight"], label="worth",
                ),
                "collected": mo.ui.checkbox(
                    value="pass_mark" in default,
                    label="collected from Brightspace exports",
                ),
                "pass_mark": mo.ui.number(
                    start=0, stop=100, step=1,
                    value=default.get("pass_mark", 80), label="pass mark",
                ),
                "free_passes": mo.ui.number(
                    start=0, stop=50, step=1,
                    value=default.get("free_passes", 0), label="free passes",
                ),
            }
        )

    rows = mo.ui.array([_row(i) for i in range(int(how_many.value))])
    return (rows,)


@app.cell
def the_form(offer, rows, code, title, year, leader, moderator, classlist, departmental):
    def _row_view(index, row):
        return mo.vstack(
            [
                mo.md(f"**Assessment {index + 1}**"),
                mo.hstack([row["id"], row["type"], row["name"]], justify="start"),
                mo.hstack([row["marks_out_of"], row["weight"]], justify="start"),
                mo.hstack(
                    [row["collected"], row["pass_mark"], row["free_passes"]],
                    justify="start",
                ),
            ]
        )

    form = mo.vstack(
        [
            mo.md("### The module"),
            mo.hstack([code, title, year], justify="start"),
            mo.hstack([leader, moderator], justify="start"),
            mo.hstack([classlist, departmental], justify="start"),
            mo.md(
                f"""
                ### The assessment

                Each piece carries two numbers, and every grade sheet column
                falls out of them: what it is **marked out of**, and what it
                is **worth** towards the module total. Where they differ you
                get a raw column and a weighted one; where they are equal
                there is one column.

                Tick **collected from Brightspace exports** for a run of
                weekly quizzes, or an MCQ read straight out of Brightspace.
                Only a {" or a ".join(t.value for t in COLLECTED_TYPES)} may
                be ticked; anything else is refused when the file is written.
                Only then are the pass mark and free passes written: a pass
                mark of 80 means a quiz scoring exactly 80 has failed, and a
                free pass is a week that may be missed without losing the
                mark. Leave it unticked and the piece is marked by a human on
                a feedback sheet, which is every coursework and every exam.

                Ten weekly quizzes, each pass worth 1%, are **one** row —
                marked out of 10 and worth 10.

                Rubrics, grade cells and graders are not asked for here; add
                them to `module.toml` afterwards, where the file's own
                comments explain them.
                """
            ),
            *[_row_view(i, rows[i]) for i in range(len(rows))],
        ]
    )

    form if offer else mo.md("")
    return


@app.cell
def the_specs(rows):
    def assessment_spec(row: dict) -> dict:
        """One form row as the dict init_module wants.

        The collection rules are written only when the row is ticked, rather
        than inferred from its type. An MCQ may be collected from
        Brightspace's exports or marked by hand, and the difference is not
        visible in the type -- so guessing would give every MCQ a pass mark
        of 80, and an MCQ collected with a pass mark is scored as one quiz
        passed, worth a single mark, instead of read straight off.
        """
        spec = {
            "id": row["id"].strip(),
            "type": row["type"],
            "name": row["name"].strip(),
            "marks_out_of": row["marks_out_of"],
            "weight": row["weight"],
        }
        if row["collected"]:
            spec["pass_mark"] = row["pass_mark"]
            spec["free_passes"] = int(row["free_passes"])
        return spec

    specs = [assessment_spec(row) for row in rows.value]
    weights = sum(spec["weight"] for spec in specs)
    return assessment_spec, specs, weights


@app.cell
def check_the_weights(offer, weights):
    ready = abs(weights - 100) <= WEIGHT_TOLERANCE

    verdict = mo.md(
        f"""
        Weights so far: **{weights}**. {
            "That is 100, so the module can be written."
            if ready else
            "They must sum to 100 before this module can be written — "
            "weights that do not make every student's total wrong, and the "
            "error stays invisible until the marks are audited."
        }
        """
    )

    verdict if offer else mo.md("")
    return


@app.cell
def the_button(offer):
    create = mo.ui.run_button(label=f"Write {MODULE_FILENAME} and create the folders")

    create if offer else mo.md("")
    return (create,)


@app.cell
def write_the_module(
    create, found, offer, specs, code, title, year, leader, moderator, classlist,
    departmental,
):
    def _optional(field) -> str | None:
        return field.value.strip() or None

    def _write():
        paths = {
            "classlist": _optional(classlist),
            "departmental_sheet": _optional(departmental),
        }
        handle = init_module(
            found.folder,
            code=code.value.strip(),
            name=title.value.strip(),
            year=year.value.strip(),
            leader=leader.value.strip(),
            assessments=specs,
            internal_moderator=_optional(moderator),
            paths={k: v for k, v in paths.items() if v is not None},
        )
        created = "\n".join(f"- `{d}`" for d in handle.module.directories)
        return mo.md(
            f"""
            ### Written

            `{handle.path}` now holds **{handle.module.code}**, and these
            folders exist:

            {created}

            Click **Re-read this folder** at the top to load it.
            """
        )

    if not (create.value and offer):
        outcome = mo.md("")
    else:
        try:
            outcome = _write()
        except Exception as exc:
            # Shown rather than raised. Everything that can go wrong here is
            # something the person filling in the form can fix -- a blank
            # title, two assessments sharing an id, weights that do not sum
            # to 100 -- and the model's messages are written to be read.
            #
            # Nothing has been written when this happens: init_module
            # validates before it touches the disk.
            outcome = mo.md(
                f"""
                ### Not written

                ```
                {exc}
                ```

                Nothing was created. Fix the form above and click again.
                """
            )

    outcome
    return


if __name__ == "__main__":
    app.run()
