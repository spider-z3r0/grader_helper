import marimo

app = marimo.App(width="medium")

with app.setup():
    import os
    import pathlib as pl

    import marimo as mo

    import pandas as pd

    from grader_helper import (
        KEEP_CHOICES,
        alphabetise_folders,
        build_departmental_sheet,
        build_moderation_pack,
        collate_module_marks,
        prepare_data_for_departmental_template,
        sample_for_moderation,
        write_departmental_sheet,
        write_si_marks,
        allocate_graders,
        attach_group_membership,
        build_group_membership,
        brightspace_name_folders,
        catch_grades,
        collect_quiz_marks,
        distribute_feedback_sheets,
        import_brightspace_classlist,
        ingest_completed_graderfiles,
        reconcile_marks,
        resolve_multiple_subs,
        save_collated_grades,
        scan_multiple_subs,
    )
    from grader_helper.moderation import BORDERLINE_MODES
    from grader_helper.file_operations.scan_multiple_submissions import (
        parse_brightspace_folder,
    )
    from grader_helper.models import (
        COLLECTED_TYPES,
        GroupSource,
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
            "### Marking setup",
            "",
            "| id | graders | blank feedback sheet | mark is in |",
            "|---|---|---|---|",
        ]

        # An assessment collected from Brightspace has none of this and needs
        # none of it: nobody marks a quiz. Everything else needs all three
        # before a single step will run -- graders to allocate, a blank sheet
        # to distribute, a cell to read the mark back out of -- so what is
        # missing is named here rather than discovered at the first click.
        def _collected(assessment) -> bool:
            return assessment.pass_mark is not None

        def _missing(assessment) -> list[str]:
            if _collected(assessment):
                return []
            return [
                label
                for label, value in (
                    ("graders", assessment.graders),
                    ("feedback sheet", assessment.rubric),
                    ("mark cell", assessment.grade_cell),
                )
                if not value
            ]

        for a in module.assessments:
            if _collected(a):
                lines.append(
                    f"| `{a.id}` | collected from Brightspace — "
                    f"pass mark {a.pass_mark}, {a.free_passes} free | | |"
                )
            else:
                lines.append(
                    f"| `{a.id}` | "
                    f"{', '.join(g.initials for g in a.graders) or '—'} | "
                    f"{a.rubric or '—'} | {a.grade_cell or '—'} |"
                )

        unready = {a.id: _missing(a) for a in module.assessments if _missing(a)}
        lines += [
            "",
            "Every assessment has what marking it needs."
            if not unready
            else "**Not ready to mark:** "
            + "; ".join(
                f"`{aid}` has no {' or '.join(gaps)}" for aid, gaps in unready.items()
            )
            + ". Add them in `module.toml`.",
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
        label="Departmental grade sheet to write (optional)",
        placeholder="PS4034 grades.xlsx",
    )
    template = mo.ui.text(
        label="Departmental blank template (optional)",
        placeholder="Dept grade sheet Template 2026.xlsx",
    )
    si_file = mo.ui.text(
        label="SI's upload file (optional)", placeholder="PS4034_SI.CSV"
    )
    return (
        classlist, code, departmental, leader, moderator, si_file, template,
        title, year,
    )


@app.cell
def assessment_rows(how_many):
    # One control, not a tick plus a follow-up question, so the form cannot
    # express the one state module.toml refuses: a group assessment that does
    # not say where its groups come from. The two kinds share almost nothing
    # -- where membership is read from, and whether a mark belongs to a team
    # or to a person -- so there is no sensible default to fall back on.
    GROUP_CHOICES = {
        "marked per student": None,
        "group, made in Brightspace": GroupSource.BRIGHTSPACE,
        "group, I keep the groups myself": GroupSource.MODULE_LEADER,
    }
    _GROUP_LABELS = {source: label for label, source in GROUP_CHOICES.items()}

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
                "grade_cell": mo.ui.text(
                    value=default.get("grade_cell", ""),
                    placeholder="B12",
                    label="mark is in cell",
                ),
                "graders": mo.ui.text(
                    value=", ".join(default.get("graders", ())),
                    placeholder="KOM, SOB",
                    label="graders (initials)",
                ),
                "rubric": mo.ui.text(
                    value=default.get("rubric", ""),
                    placeholder="Feedback sheet.xlsx",
                    label="blank feedback sheet",
                ),
                "group": mo.ui.dropdown(
                    options=list(GROUP_CHOICES),
                    value=_GROUP_LABELS[
                        GroupSource(default["group_source"])
                        if default.get("group_source")
                        else None
                    ],
                    label="submitted by",
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
    return GROUP_CHOICES, rows


@app.cell
def the_form(
    offer, rows, code, title, year, leader, moderator, classlist, departmental,
    template, si_file,
):
    def _row_view(index, row):
        return mo.vstack(
            [
                mo.md(f"**Assessment {index + 1}**"),
                mo.hstack([row["id"], row["type"], row["name"]], justify="start"),
                mo.hstack(
                    [row["marks_out_of"], row["weight"], row["grade_cell"]],
                    justify="start",
                ),
                mo.hstack(
                    [row["group"], row["graders"], row["rubric"]],
                    justify="start",
                ),
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
            mo.hstack([template, si_file], justify="start"),
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

                **Submitted by** says whether the work is one student's or a
                team's, and where the teams come from. *Made in Brightspace*
                means Brightspace's own groups: they arrive in the class
                list, and the download has one folder, one feedback sheet and
                one mark per team. *I keep the groups myself* means the teams
                are yours, in sheets under the assessment's `groups/` folder;
                Brightspace knows nothing about them, so the download is the
                ordinary per-student shape and marks may differ within a
                team. Either way a whole team goes to one marker.

                **Graders**, the **blank feedback sheet** and the **cell the
                mark lands in** are what the marking steps read: who gets a
                workbook, what is copied into each student's folder, and
                where a grader's mark is found afterwards. Initials go in
                comma separated — `KOM, SOB` — and the sheet is a filename
                inside the assessment's own folder, not a path.

                Leave all three blank for anything nobody marks by hand, and
                for an assessment whose graders are not decided yet: an
                absent key is a question not yet answered, and you can add it
                to `module.toml` later.
                """
            ),
            *[_row_view(i, rows[i]) for i in range(len(rows))],
        ]
    )

    form if offer else mo.md("")
    return


@app.cell
def the_specs(rows, GROUP_CHOICES):
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

        # Both keys or neither. `group = true` on its own does not load, and
        # `group = false` is the default, so writing it would only add a line
        # saying what the absence already says.
        source = GROUP_CHOICES[row["group"]]
        if source is not None:
            spec["group"] = True
            spec["group_source"] = source.value

        # What the marking steps read off the model: who marks it, the blank
        # sheet they are given, and the cell their mark lands in. Left out
        # of the file entirely when blank rather than written empty -- a
        # `graders = []` reads as "nobody marks this", which is a claim,
        # where an absent key is just a question not yet answered.
        graders = [
            initials.strip() for initials in row["graders"].split(",")
            if initials.strip()
        ]
        if graders:
            spec["graders"] = graders
        for key in ("rubric", "grade_cell"):
            if row[key].strip():
                spec[key] = row[key].strip()
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
    departmental, template, si_file,
):
    def _optional(field) -> str | None:
        return field.value.strip() or None

    def _write():
        paths = {
            "classlist": _optional(classlist),
            "departmental_sheet": _optional(departmental),
            "departmental_template": _optional(template),
            "si_file": _optional(si_file),
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


@app.cell
def marking_intro(loaded):
    _intro = mo.md(
        """
        ---

        # Running the assessment

        Each button below is one step, and each writes into the module folder
        you chose. They are grouped the way the work actually happens: two
        before anyone marks, two after — with days or weeks in between, which
        is why this is a page you come back to rather than a script you run.

        Nothing here overwrites a feedback sheet. A sheet already in a
        student's folder may carry a mark, so distribution skips it rather
        than replacing it, and there is no tick that changes that. The tick
        below covers only the files this tool writes for itself — the
        allocation and the grader workbooks — which are safe to regenerate
        because nothing but this tool puts anything in them.

        After a step, click **Re-read this folder** at the top to see the
        status it recorded.
        """
    )
    _intro if loaded else mo.md("")
    return


@app.cell
def helpers():
    def attempt(action):
        """Run one step. Return its result, or the exception it raised.

        Every button needs this and none of them may crash the page: a step
        that fails on a real module folder — a workbook open in Excel, a
        grader who has not returned their file — has to leave a message
        behind, not a traceback that takes the rest of the page with it.
        """
        try:
            return action(), None
        except Exception as exc:
            return None, exc

    def failed(title: str, error: Exception):
        return mo.md(
            f"""
            ### {title} — not done

            ```
            {type(error).__name__}: {error}
            ```
            """
        )

    return attempt, failed


@app.cell
def class_list_source(found, loaded):
    # module.toml names the class list, and every marking step is blocked
    # behind reading it. A path that is wrong, or a file that has not arrived
    # yet, therefore left the page with nothing to do and no way forward
    # except hand-editing the toml -- which is the thing this is meant to
    # replace. So: pick one here instead.
    classlist_picker = mo.ui.file_browser(
        initial_path=found.module.root if loaded else pl.Path.home(),
        selection_mode="file",
        multiple=False,
        filetypes=[".csv", ".xlsx"],
        label="**Class list** — pick a file to use instead of the one above",
    )
    remember_classlist = mo.ui.run_button(
        label="Remember this class list in module.toml"
    )

    mo.vstack([classlist_picker, remember_classlist]) if loaded else mo.md("")
    return classlist_picker, remember_classlist


@app.cell
def the_class_list(found, loaded, classlist_picker):
    def class_list_choice(picked, configured):
        """Which class list to read, and where it came from.

        **Picked wins.** module.toml is the module's memory, but a path in it
        that is wrong is the whole reason this control exists, so the
        remembered value cannot be the one that always wins.
        """
        if picked is not None:
            return picked, "picked here"
        return configured, "from module.toml"

    def read_class_list(path, module):
        """The class list at `path`, or None and the reason why."""
        if path is None:
            return None, (
                "**No class list.** `[paths]` in module.toml has no "
                "`classlist`, so pick the file above."
            )
        if not path.exists():
            return None, (
                f"**No class list at** `{path}`. Pick the file above — the "
                "marking steps all wait on this one."
            )

        # Groups have to be asked for at ingest: a group allocation needs the
        # column, and it is dropped when it is not wanted. Only a
        # Brightspace-managed group assessment has one to ask for -- a
        # leader-managed one keeps its groups in sheets of its own, and
        # asking here would refuse a class list that is perfectly correct.
        grouped = any(
            a.group_source is GroupSource.BRIGHTSPACE for a in module.assessments
        )
        try:
            frame = import_brightspace_classlist(path, group=grouped)
        except Exception as exc:
            return None, f"`{path.name}` would not read: `{exc}`"

        # import_brightspace_classlist returns None rather than raising for a
        # file it cannot make sense of. Reading len(None) here took the whole
        # page down with a TypeError, which is the one thing a step may not do.
        if frame is None:
            return None, (
                f"`{path.name}` would not read. It should be a Brightspace "
                "class list export, with `Username`, `Last Name` and "
                "`First Name` columns."
            )

        return frame, (
            f"**{len(frame)} students** on the class list (`{path.name}`)"
            + (" — with groups" if grouped else "")
        )

    def _now():
        picked = classlist_picker.value
        path, where = class_list_choice(
            pl.Path(picked[0].path) if picked else None,
            found.module.classlist_path,
        )
        frame, note = read_class_list(path, found.module)
        return frame, path, f"{note} *({where})*" if path is not None else note

    class_list, class_list_path, class_list_note = (
        _now() if loaded else (None, None, "")
    )

    mo.md(class_list_note) if loaded else mo.md("")
    return class_list, class_list_choice, class_list_path, read_class_list


@app.cell
def do_remember_classlist(
    remember_classlist, remember_class_list, class_list_path, loaded, attempt,
    failed,
):
    if not (remember_classlist.value and loaded and class_list_path is not None):
        remembered = mo.md("")
    else:
        _done, _error = attempt(lambda: remember_class_list(class_list_path))
        if _error is not None:
            remembered = failed("Remembering the class list", _error)
        else:
            remembered = mo.md(
                f"""
                ### Remembered

                `classlist = "{_done.as_posix()}"` is now in module.toml.
                Click **Re-read this folder** at the top to see it.
                """
            )

    remembered
    return


@app.cell
def pick_an_assessment(found, loaded):
    ids = [a.id for a in found.module.assessments] if loaded else []
    which = mo.ui.dropdown(
        options=ids, value=ids[0] if ids else None, label="**Working on**"
    )

    which if loaded else mo.md("")
    return (which,)


@app.cell
def the_chosen_assessment(found, loaded, which):
    def submissions_state(subs):
        """What is actually in the submissions folder, in words.

        "folders there: 0" was true of a folder that is not there, a folder
        with nothing in it, a download still sitting in its zip, and a
        download unzipped one level too deep -- four situations wanting four
        different things done, reported identically. Every step that reads
        submissions iterates the directories immediately inside it, so the
        difference is the difference between working and silently doing
        nothing.
        """
        if not subs.is_dir():
            return 0, "**not there** — unzip the Brightspace download into it"

        folders = sorted(p for p in subs.iterdir() if p.is_dir())
        files = sorted(p for p in subs.iterdir() if p.is_file())

        if not folders:
            zipped = [f.name for f in files if f.suffix.lower() == ".zip"]
            if zipped:
                return 0, (
                    f"**still zipped** — `{zipped[0]}` is there but has not "
                    "been extracted"
                )
            if files:
                return 0, (
                    f"**{len(files)} loose file(s), no folders** — a "
                    "Brightspace download extracts to one folder per student"
                )
            return 0, "**empty** — the download has not been extracted into it"

        # The classic: extracting the zip makes a folder named for the
        # download, and the student folders are inside that. Everything
        # downstream looks one level up from where they are and finds
        # nothing, without complaining.
        if len(folders) == 1 and any(p.is_dir() for p in folders[0].iterdir()):
            return 1, (
                f"**one level too deep** — the student folders are inside "
                f"`{folders[0].name}/`. Move them up into `{subs.name}/`"
            )

        return len(folders), ""

    def _describe(assessment, repeats):
        subs = assessment.submissions_path
        how_many, trouble = submissions_state(subs)
        # Folder names only, so this is cheap even on a real cohort.
        status = assessment.status

        return mo.md(
            "\n".join(
                [
                    f"### {assessment.name} (`{assessment.id}`)",
                    "",
                    f"Marked out of {assessment.marks_out_of}, worth "
                    f"{assessment.weight}.",
                    "",
                    "| | |",
                    "|---|---|",
                    f"| submissions | `{subs}` |",
                    f"| folders there | {how_many}"
                    f"{' — ' + trouble if trouble else ''} |",
                    f"| submitted more than once | {len(repeats)} |",
                    f"| graders | "
                    f"{', '.join(g.initials for g in assessment.graders) or '—'} |",
                    f"| blank feedback sheet | "
                    f"{'`' + assessment.rubric + '`' if assessment.rubric else '—'}"
                    f"{'' if assessment.rubric_path is None or assessment.rubric_path.exists() else ' — **not on disk**'} |",
                    f"| mark is in | `{assessment.grade_cell or '—'}` |",
                    "",
                    f"Allocated: **{'yes' if status.graders_allocated else 'no'}** · "
                    f"distributed: **{'yes' if status.sheets_distributed else 'no'}** · "
                    f"collected: **{'yes' if status.grades_collected else 'no'}**",
                ]
            )
        )

    chosen = (
        found.module.assessment(which.value) if loaded and which.value else None
    )
    # Folder names only, so this is cheap even on a real cohort. Worked out
    # once here rather than per step: three cells below need to know.
    repeats = (
        scan_multiple_subs(chosen.submissions_path)
        if chosen is not None and chosen.submissions_path.is_dir()
        else {}
    )
    # An assessment collected from Brightspace's exports takes a different
    # path entirely: no allocation, no sheets, no transcription, so nothing
    # to reconcile. The tick in the setup form is what says which it is.
    collected = chosen is not None and chosen.pass_mark is not None

    _describe(chosen, repeats) if chosen is not None else mo.md("")
    return chosen, collected, repeats, submissions_state


@app.cell
def step_options(loaded):
    replace = mo.ui.checkbox(
        value=False,
        label="replace the allocation and grader workbooks if they exist "
        "(never feedback sheets)",
    )

    replace if loaded else mo.md("")
    return (replace,)


@app.cell
def why_not(chosen, collected, class_list, repeats, submissions_state):
    def blocking(*needs: str) -> list[str]:
        """What is missing before a step can run, in words."""
        if chosen is None:
            return ["no assessment chosen"]
        if collected:
            return ["nobody marks this one — it is collected from Brightspace"]
        reasons = {
            "class list": "the class list has not been read",
            "graders": "this assessment has no graders in module.toml",
            "rubric": "this assessment has no blank feedback sheet in module.toml",
            "grade cell": "this assessment has no mark cell in module.toml",
            "submissions": (
                f"there is no submissions folder at "
                f"`{chosen.submissions_path}`"
                if not chosen.submissions_path.is_dir()
                else f"there are no student folders in "
                f"`{chosen.submissions_path}` — see the note above"
            ),
            "one folder each": (
                f"{len(repeats)} student(s) submitted more than once — "
                "resolve that first, below"
            ),
            "group sheets": (
                "this is a group assessment whose groups you keep yourself, "
                f"and there are no sheets at `{chosen.group_sheets_path}`"
            ),
        }
        have = {
            "class list": class_list is not None,
            "graders": bool(chosen.graders),
            "rubric": bool(chosen.rubric),
            "grade cell": bool(chosen.grade_cell),
            # A folder that is there but holds no student folders is not a
            # download that can be distributed into, and saying "there is no
            # folder" about a folder that plainly exists sent the reader
            # looking in the wrong place.
            "submissions": submissions_state(chosen.submissions_path)[0] > 0,
            "one folder each": not repeats,
            # Only leader-managed groups have sheets to be missing. A
            # Brightspace-managed one gets its groups from the class list,
            # which is already a need of its own.
            "group sheets": (
                chosen.group_sheets_path is None
                or chosen.group_sheets_path.is_dir()
            ),
        }
        return [reasons[need] for need in needs if not have[need]]

    def step_panel(title: str, explanation: str, button, blocked: list[str]):
        """A step, or the reason it cannot run yet."""
        if blocked:
            return mo.md(
                f"### {title}\n\n*Not yet — " + "; ".join(blocked) + ".*"
            )
        return mo.vstack([mo.md(f"### {title}\n\n{explanation}"), button])

    return blocking, step_panel


@app.cell
def the_steps(found):
    """What each button does, as a function that can be called without one.

    The work is here rather than inside the button guards so that it can be
    driven by something other than a click -- the suite runs a whole module
    through these against a real folder on disk, which a test that can only
    press buttons cannot do.

    Each takes the assessment it works on. The module handle comes from the
    page, because it is the file every one of these records into.
    """

    def remember_class_list(path):
        """Record a class list in module.toml, relative to the module folder.

        Nothing absolute goes in the file: these folders live under OneDrive,
        where the absolute path differs per machine and per account.
        """
        root = found.module.root
        try:
            relative = pl.Path(path).relative_to(root)
        except ValueError:
            raise ValueError(
                f"{path} is outside the module folder ({root}). module.toml "
                "stores paths relative to itself, so the class list has to "
                "live in the module folder. Copy it in and pick it again."
            )
        # set_paths adds the key when the file has not got it, above the
        # table's trailing comments rather than after them -- see add_key.
        found.file.set_paths(classlist=relative.as_posix())
        return relative

    def remember_group_sheets(assessment, path):
        """Record where an assessment's group sheets are, in module.toml."""
        try:
            relative = pl.Path(path).relative_to(assessment.folder_path)
        except ValueError:
            raise ValueError(
                f"{path} is outside `{assessment.folder_path}`. "
                "`group_sheets` is relative to the assessment's own folder, "
                "and module.toml stores nothing absolute, so the sheets have "
                "to live in there. Copy them in and pick again."
            )
        found.file.set_assessment(assessment.id, group_sheets=relative.as_posix())
        return relative

    def collect_groups(assessment, class_list=None, source=None):
        """Collect a leader-managed assessment's own group sheets.

        Allocation does this too. Running it on its own first is where a
        mistyped id or a student left off every sheet shows up, and both are
        much cheaper to fix before the graders have workbooks.

        Returns the membership, the class list with a Group column on it, and
        the ids the sheets name who are **not enrolled**. That last one is
        the other half of a mistyped id, and it reached only the terminal as
        a warning -- which is not where the person clicking the button is
        looking.
        """
        membership = build_group_membership(assessment, source=source)
        strangers = []
        attached = None
        if class_list is not None:
            enrolled = set(class_list["Student ID"].astype(str))
            strangers = sorted(
                set(membership.frame["Student ID"].astype(str)) - enrolled
            )
            # The join is where a student in no group is named, so do it here
            # rather than leaving it to be found at allocation.
            attached = attach_group_membership(class_list, membership.frame)
        return membership, attached, strangers

    def group_sizes(membership):
        """How many students are in each group, as a table to show.

        Here rather than in the button guard because the guard is the one
        place a test cannot reach -- and the first version of this line,
        `reset_index(names=...)`, is a DataFrame argument that Series has
        never had. It raised the moment somebody pressed the button, having
        passed every test in the suite.
        """
        sizes = membership.frame["Group"].value_counts().sort_index()
        return sizes.rename_axis("group").reset_index(name="students")

    def allocate_marking(assessment, class_list, replace: bool = False):
        # One call for all three kinds. It picks the allocator, collects a
        # leader-managed assessment's own group sheets first, and writes a
        # grader's workbook in the shape that kind of marking comes back in
        # -- one row per group where Brightspace gives the team one feedback
        # sheet, one row per student everywhere else.
        result = allocate_graders(assessment, class_list, overwrite=replace)
        # The artefact is the evidence, not the absence of an exception.
        found.file.record(result, assessment.id)
        return result.allocation, result.workbooks, result.frame

    def distribute_sheets(assessment, class_list):
        # Never overwrite: a sheet already in a student's folder may carry a
        # mark, and there is no tick that changes that.
        distribution = distribute_feedback_sheets(
            assessment.submissions_path, assessment.rubric_path
        )

        # Only rename what is still in Brightspace's format. Pressing this a
        # second time is an ordinary thing to do -- a late submission
        # downloaded and dropped in, or simply not being sure it ran -- and
        # alphabetise_folders refuses a folder with nothing left to rename,
        # which would read as the step having failed when it has already
        # succeeded.
        log_path = assessment.submissions_path / "folder_rename_log.csv"
        still_brightspace = any(
            parse_brightspace_folder(folder.name)
            for folder in assessment.submissions_path.iterdir()
            if folder.is_dir()
        )
        if still_brightspace:
            # Returns None. The handoff to the rename-back step is the log.
            alphabetise_folders(class_list, assessment.submissions_path)

        log = pd.read_csv(log_path) if log_path.exists() else pd.DataFrame()
        found.file.record(distribution, assessment.id)
        return distribution, log

    def collect_marks(assessment, replace: bool = False):
        graders = [g.initials for g in assessment.graders]
        received = catch_grades(assessment.submissions_path, assessment.grade_cell)
        reported = ingest_completed_graderfiles(
            assessment.grading_output_path, graders, file_type="excel"
        )
        collation = save_collated_grades(
            reported,
            assessment.grading_output_path,
            file_type="excel",
            overwrite=replace,
        )
        found.file.record(collation, assessment.id)
        return collation, reconcile_marks(received, reported)

    def rename_back(assessment):
        log_path = assessment.submissions_path / "folder_rename_log.csv"
        if not log_path.exists():
            raise FileNotFoundError(
                f"No folder_rename_log.csv in {assessment.submissions_path}. "
                "The folders are renamed back from that log, which the "
                "distribute step writes, so there is nothing to restore them "
                "from."
            )
        return brightspace_name_folders(
            pd.read_csv(log_path), assessment.submissions_path
        )

    def recorded(assessment, flag: str) -> bool:
        """Whether a step's flag actually got set.

        `record` reads the evidence off what a step returned and leaves the
        status alone when it does not hold up -- a distribution that left a
        folder unrecognised has not finished, and the tick would hide the
        one it missed. So the page reports the flag rather than the click.
        """
        return getattr(
            found.file.module.assessment(assessment.id).status, flag
        )

    def resolve_resubmissions(assessment, keep: str, apply: bool = False):
        # apply=False works out the same answer without touching anything, so
        # the choice can be seen before a student's work is deleted.
        return resolve_multiple_subs(
            assessment.submissions_path, keep=keep, apply=apply
        )

    def collect_quizzes(assessment, class_list):
        marks = collect_quiz_marks(assessment, class_list)
        # No evidence type for a frame, so this flag is set directly rather
        # than through record(). What a frame would have to show to justify it
        # is a question for the library, not for a button.
        found.file.set_status(assessment.id, grades_collected=True)
        return marks

    return (
        allocate_marking,
        collect_groups,
        group_sizes,
        remember_group_sheets,
        remember_class_list,
        collect_marks,
        recorded,
        collect_quizzes,
        distribute_sheets,
        rename_back,
        resolve_resubmissions,
    )


@app.cell
def groups_source(chosen, loaded):
    # module.toml names where the group sheets are, and the default is a
    # folder called `groups/`. Plenty of leaders keep the lot in one file
    # instead, and a module written before this key existed has not got it
    # at all -- so it can be pointed at here, and remembered.
    groups_picker = mo.ui.file_browser(
        initial_path=(
            chosen.folder_path
            if chosen is not None and chosen.folder_path.is_dir()
            else pl.Path.home()
        ),
        selection_mode="file",
        multiple=False,
        filetypes=[".csv", ".xlsx", ".xlsm"],
        label="**Group sheets** — pick the file holding them",
    )
    remember_groups = mo.ui.run_button(
        label="Remember this in module.toml"
    )

    (
        mo.vstack([groups_picker, remember_groups])
        if loaded and chosen is not None and chosen.group
        and chosen.group_source is GroupSource.MODULE_LEADER
        else mo.md("")
    )
    return groups_picker, remember_groups


@app.cell
def groups_panel(chosen, class_list, loaded, groups_picker):
    # A group assessment's membership has to exist before anything can be
    # allocated, and where it comes from depends on which kind it is. This is
    # the only step whose *presence* depends on the assessment: an individual
    # one has no groups to collect, and showing a dead button for it would
    # say there is something to do.
    catch_groups = mo.ui.run_button(label="Collect the groups", kind="warn")

    def _picked():
        picked = groups_picker.value
        return pl.Path(picked[0].path) if picked else None

    def groups_where(assessment):
        """The sheets to read: picked here, or what module.toml says.

        **Picked wins**, for the same reason it does for the class list: the
        remembered value being wrong or absent is the reason the control is
        there.
        """
        picked = _picked()
        if picked is not None:
            return picked, "picked here"
        return assessment.group_sheets_path, "from module.toml"

    def _sheets_note(where):
        if where.is_file():
            return f"one file, `{where.name}`"
        if not where.is_dir():
            return None
        names = sorted(
            q.name for q in where.iterdir()
            if q.suffix.lower() in (".csv", ".xlsx", ".xlsm")
            and not q.name.startswith("~$")
        )
        return f"**{len(names)} sheet(s)** in `{where.name}/` — `{names}`" if names else None

    def _panel():
        if chosen is None or not chosen.group:
            return mo.md("")

        if chosen.group_source is GroupSource.BRIGHTSPACE:
            arrived = class_list is not None and "Group" in class_list.columns
            return mo.md(
                "### Groups\n\n"
                "Brightspace made these groups, so they come down **in the "
                "class list** and there is nothing to collect. "
                + (
                    f"The group column is there: "
                    f"**{class_list['Group'].nunique()} groups**."
                    if arrived
                    else "*The class list has no group column yet* — read one "
                    "above, exported with Brightspace's group function."
                )
            )

        where, source = groups_where(chosen)
        note = _sheets_note(where) if where is not None else None
        if note is None:
            return mo.md(
                "### Groups\n\n"
                f"*Nothing to collect at* `{where}` *({source}).* "
                "Pick the file above — a folder of one sheet per team works "
                "too, and is set with `group_sheets` in module.toml."
            )

        return mo.vstack([
            mo.md(
                "### Groups\n\n"
                "You keep these groups yourself, so they have to be collected "
                "into one student-to-group table before anything can be "
                f"allocated. Reading {note} *({source})*.\n\n"
                "Allocating does this too. Running it here first is where a "
                "mistyped id or a student left off every sheet shows up, and "
                "both are much cheaper to fix before the graders have "
                "workbooks."
            ),
            catch_groups,
        ])

    _panel() if loaded else mo.md("")
    return catch_groups, groups_where


@app.cell
def do_catch_groups(
    catch_groups, collect_groups, group_sizes, groups_where, chosen,
    class_list, attempt, failed,
):
    if not (catch_groups.value and chosen is not None and chosen.group):
        caught_groups = mo.md("")
    else:
        _source, _ = groups_where(chosen)
        _done, _error = attempt(
            lambda: collect_groups(chosen, class_list, source=_source)
        )
        if _error is not None:
            caught_groups = failed("Collecting the groups", _error)
        else:
            _membership, _attached, _strangers = _done
            caught_groups = mo.vstack([
                mo.md(
                    f"""
                    ### Groups collected

                    {_membership} — written to
                    `{_membership.path.name}` in `grading_output/`.

                    {"Every student on the class list is in a group."
                     if _attached is not None
                     else "*Read a class list above to check every student "
                          "is in one.*"}

                    {f"**{len(_strangers)} id(s) in the sheets are not on the "
                     f"class list** and have been ignored: `{_strangers}`. "
                     "Usually a withdrawal, or a mistyped id — a mistyped one "
                     "shows up here and again as a student with no group."
                     if _strangers else ""}
                    """
                ),
                mo.ui.table(group_sizes(_membership), selection=None),
            ])

    caught_groups
    return


@app.cell
def do_remember_groups(
    remember_groups, remember_group_sheets, groups_where, chosen, attempt,
    failed,
):
    if not (remember_groups.value and chosen is not None and chosen.group):
        remembered_groups = mo.md("")
    else:
        _source, _ = groups_where(chosen)
        _done, _error = attempt(
            lambda: remember_group_sheets(chosen, _source)
        )
        if _error is not None:
            remembered_groups = failed("Remembering the group sheets", _error)
        else:
            remembered_groups = mo.md(
                f"""
                ### Remembered

                `group_sheets = "{_done.as_posix()}"` is now on
                `{chosen.id}` in module.toml. Click **Re-read this folder**
                at the top to see it.
                """
            )

    remembered_groups
    return


@app.cell
def allocate_button(blocking, step_panel, chosen):
    allocate = mo.ui.run_button(label="Allocate the marking", kind="warn")

    step_panel(
        "1. Allocate the marking",
        "Splits the class list between the graders, writes `distributed.xlsx` "
        "at the assessment root, and gives each grader their own workbook in "
        "`grading_output/`. The split is random and even.",
        allocate,
        blocking("class list", "graders", "group sheets"),
    ) if chosen is not None else mo.md("")
    return (allocate,)


@app.cell
def do_allocate(
    allocate, allocate_marking, attempt, failed, chosen, class_list, recorded,
    replace,
):
    if not (allocate.value and chosen is not None):
        allocated = mo.md("")
    else:
        _done, _error = attempt(
            lambda: allocate_marking(chosen, class_list, replace.value)
        )
        if _error is not None:
            allocated = failed("Allocation", _error)
        else:
            _master, _workbooks, _allocation = _done
            allocated = mo.md(
                f"""
                ### Allocated

                {_master}

                Per grader: `{_allocation["grader"].value_counts().to_dict()}`

                Workbooks in `grading_output/`:
                `{[p.name for p in _workbooks.values()]}`

                Recorded `graders_allocated`:
                **{"yes" if recorded(chosen, "graders_allocated") else "no"}**
                """
            )

    allocated
    return


@app.cell
def resubmission_widgets():
    # Defined apart from the panel that renders them: marimo refuses to let a
    # cell read the value of an element it created itself, and the panel has
    # to read the choice to work out what deleting it would remove.
    keep_which = mo.ui.radio(
        options=list(KEEP_CHOICES),
        value=None,
        label="**Which submission counts?**",
    )
    resolve = mo.ui.run_button(label="Delete the other submissions", kind="danger")
    return keep_which, resolve


@app.cell
def resubmission_panel(
    chosen, collected, repeats, resolve_resubmissions, keep_which, resolve
):
    def _panel():
        listed = "\n".join(
            f"| `{student}` | "
            + " · ".join(when.strftime("%d %b %Y %H:%M") for when in sorted(times))
            + " |"
            for student, times in sorted(repeats.items())
        )
        heading = mo.md(
            f"""
            ### 1a. Resolve multiple submissions

            {len(repeats)} student(s) submitted more than once. Two folders
            for one student cannot both be renamed for marking, so nothing
            below will run until one of them goes.

            | student | submitted |
            |---|---|
            {listed}

            Which one counts is your decision, not the tool's: a
            resubmission may supersede the first attempt, or may have arrived
            after the deadline and not count at all. There is no default.
            """
        )
        if keep_which.value is None:
            return mo.vstack([heading, keep_which])

        plan = resolve_resubmissions(chosen, keep_which.value)
        return mo.vstack(
            [
                heading,
                keep_which,
                mo.md(
                    "**This will delete:**\n\n"
                    + "\n".join(f"- `{folder.name}`" for folder in plan.removed)
                    + "\n\nBrightspace still has them; this folder will not."
                ),
                resolve,
            ]
        )

    _panel() if (chosen is not None and repeats and not collected) else mo.md("")
    return


@app.cell
def do_resolve(resolve, keep_which, resolve_resubmissions, attempt, failed, chosen):
    if not (resolve.value and chosen is not None and keep_which.value):
        resolved = mo.md("")
    else:
        _done, _error = attempt(
            lambda: resolve_resubmissions(chosen, keep_which.value, apply=True)
        )
        resolved = (
            failed("Resolving the resubmissions", _error)
            if _error is not None
            else mo.md(
                f"### Resolved\n\n{_done}\n\nClick **Re-read this folder** "
                "at the top, then carry on."
            )
        )

    resolved
    return


@app.cell
def distribute_button(blocking, step_panel, chosen):
    distribute = mo.ui.run_button(label="Distribute the feedback sheets", kind="warn")

    step_panel(
        "2. Distribute the feedback sheets",
        "Copies the blank sheet into every student's folder, named for their "
        "id, then renames the folders from Brightspace's format into "
        "`SURNAME, NAME(id)` for marking. A sheet already there is skipped, "
        "never replaced — it may already carry a mark.",
        distribute,
        blocking("class list", "rubric", "submissions", "one folder each"),
    ) if chosen is not None else mo.md("")
    return (distribute,)


@app.cell
def do_distribute(
    distribute, distribute_sheets, attempt, failed, chosen, class_list, recorded
):
    if not (distribute.value and chosen is not None):
        distributed = mo.md("")
    else:
        _done, _error = attempt(lambda: distribute_sheets(chosen, class_list))
        if _error is not None:
            distributed = failed("Distribution", _error)
        else:
            _distribution, _log = _done
            _flag = recorded(chosen, "sheets_distributed")
            distributed = mo.md(
                f"""
                ### Distributed

                {_distribution}

                {len(_log)} folders renamed for marking; the log that renames
                them back is in the submissions folder.

                Recorded `sheets_distributed`: **{"yes" if _flag else "no"}**

                {"" if _flag else
                 "Not recorded, because these folders were not recognised: "
                 f"`{_distribution.unmatched}`. A run that matched every "
                 "student but one has not finished, and a tick here would "
                 "hide the one it missed. Anything that is not a student "
                 "submission — `__MACOSX` from unzipping on a Mac, a folder "
                 "you added — can be deleted or moved out; anything that is "
                 "one needs looking at."}
                """
            )

    distributed
    return


@app.cell
def collect_button(blocking, step_panel, chosen):
    collect = mo.ui.run_button(label="Collect and reconcile the marks", kind="warn")

    step_panel(
        "3. Collect the marks — after the graders have finished",
        "Reads the mark off every feedback sheet, collates the graders' own "
        "sheets into `completed_grades.xlsx`, and compares the two. Between "
        "them sits a human copying a number by hand, and this is the check "
        "that they agree.",
        collect,
        blocking("graders", "grade cell", "submissions"),
    ) if chosen is not None else mo.md("")
    return (collect,)


@app.cell
def do_collect(collect, collect_marks, attempt, failed, chosen, recorded, replace):
    if not (collect.value and chosen is not None):
        collected_marks = mo.md("")
    else:
        _done, _error = attempt(lambda: collect_marks(chosen, replace.value))
        if _error is not None:
            collected_marks = failed("Collecting the marks", _error)
        else:
            _collation, _audit = _done
            collected_marks = mo.vstack(
                [
                    mo.md(
                        f"### Collected\n\n{_collation}\n\n**{_audit}**\n\n"
                        f"Recorded `grades_collected`: "
                        f"**{'yes' if recorded(chosen, 'grades_collected') else 'no'}**"
                    ),
                    mo.md("")
                    if _audit.agree
                    else mo.vstack(
                        [
                            mo.md(
                                "Look at these before sending anything to the "
                                "department. A student collated without a "
                                "feedback sheet usually just never submitted; "
                                "two differing marks is a slip at the copy."
                            ),
                            _audit.disagreements,
                        ]
                    ),
                ]
            )

    collected_marks
    return


@app.cell
def rename_button(blocking, step_panel, chosen):
    rename = mo.ui.run_button(label="Rename the folders back", kind="warn")

    step_panel(
        "4. Rename the folders for re-upload",
        "Puts every folder back to the exact name Brightspace gave it, using "
        "the log written at step 2, so the marked folders can go back up.",
        rename,
        blocking("submissions"),
    ) if chosen is not None else mo.md("")
    return (rename,)


@app.cell
def do_rename(rename, rename_back, attempt, failed, chosen):
    if not (rename.value and chosen is not None):
        renamed = mo.md("")
    else:
        _done, _error = attempt(lambda: rename_back(chosen))
        renamed = (
            failed("Renaming the folders", _error)
            if _error is not None
            else mo.md(f"### Renamed\n\n{_done}")
        )

    renamed
    return


@app.cell
def quiz_button(chosen, collected, class_list):
    quizzes = mo.ui.run_button(label="Collect the quiz marks", kind="warn")

    _panel = (
        mo.vstack(
            [
                mo.md(
                    "### Collect the quiz marks\n\nFolds every Brightspace "
                    "export in the submissions folder into one mark, counting "
                    "the passes against this assessment's own pass mark and "
                    "free passes. The only step there is — nobody marks a quiz."
                ),
                quizzes,
            ]
        )
        if collected and class_list is not None
        else mo.md("")
    )

    _panel if chosen is not None else mo.md("")
    return (quizzes,)


@app.cell
def do_quizzes(
    quizzes, collect_quizzes, attempt, failed, chosen, collected, class_list
):
    if not (quizzes.value and collected and class_list is not None):
        quiz_marks = mo.md("")
    else:
        _done, _error = attempt(lambda: collect_quizzes(chosen, class_list))
        if _error is not None:
            quiz_marks = failed("Collecting the quiz marks", _error)
        else:
            _counts = _done[chosen.raw_column].value_counts().sort_index().to_dict()
            quiz_marks = mo.vstack(
                [
                    mo.md(
                        f"""
                        ### Quiz marks collected

                        **{len(_done)} students**, every one on the class list,
                        including those in no export at all — a missing row
                        would take a component out of a module total, and a
                        total missing a component is still a plausible number.

                        Distribution of `{chosen.raw_column}`: `{_counts}`
                        """
                    ),
                    _done,
                ]
            )

    quiz_marks
    return


@app.cell
def module_steps_intro(loaded):
    _md = mo.md(
        """
        ---

        # The module as a whole

        Once every assessment is collected: the marks in one frame, the
        department's workbook, the moderation pack, and SI's upload file.

        Collating reads every feedback sheet on the module, so it is a button
        rather than something the page does on its own. Everything below it
        works from what that produced.
        """
    )
    _md if loaded else mo.md("")
    return


@app.cell
def the_module_actions(found):
    def collate_the_module(module, class_list, source: str):
        # Reads only. `source` is not a fallback chain: "feedback" is what the
        # students received and "collated" is what the graders reported, they
        # are supposed to agree, and silently substituting one for the other
        # would hide exactly the disagreement worth knowing about.
        marks = collate_module_marks(module, class_list, source=source)
        return marks, prepare_data_for_departmental_template(marks, module)

    def write_the_departmental_sheet(module, sheet, destination, replace=False):
        # Two calls, and the split matters: the builder writes the
        # department's formulas and never a computed value, so the sheet
        # still does its own arithmetic; the writer puts in the name, the id
        # and each mark as awarded, and nothing else.
        path = build_departmental_sheet(
            module,
            module.departmental_template_path,
            destination,
            overwrite=replace,
        )
        written = write_departmental_sheet(sheet, module, path)
        found.file.record(written)
        return path, written

    def draw_the_sample(sheet, n: int, borderline: str, seed=None):
        # With no seed one is generated and handed back, and it is what makes
        # the draw defensible months later.
        return sample_for_moderation(sheet, n=n, borderline=borderline, seed=seed)

    def build_the_pack(module, sample, destination, replace=False):
        pack = build_moderation_pack(module, sample, destination, overwrite=replace)
        found.file.record(pack)
        return pack

    def fill_si_upload(module, sheet, destination):
        upload = write_si_marks(sheet, module.si_file_path, destination)
        found.file.record(upload)
        return upload

    return (
        build_the_pack,
        collate_the_module,
        draw_the_sample,
        fill_si_upload,
        write_the_departmental_sheet,
    )


@app.cell
def collate_widgets():
    source = mo.ui.radio(
        options=["feedback", "collated"],
        value="feedback",
        label="**Take each mark from**",
    )
    collate = mo.ui.run_button(label="Collate the module")
    return collate, source


@app.cell
def collate_panel(loaded, collate, source, class_list):
    _panel = mo.vstack(
        [
            mo.md(
                """
                ### 5. Collate the module

                Every assessment's marks in one frame, then totalled and
                banded in the department's column order. **feedback** is what
                the students were given; **collated** is what the graders
                reported. They are supposed to agree — step 3 is the check —
                and this will not fall back from one to the other.
                """
            ),
            source,
            collate,
        ]
    )
    _panel if (loaded and class_list is not None) else mo.md("")
    return


@app.cell
def do_collate(collate, collate_the_module, attempt, failed, found, loaded, class_list, source):
    if not (collate.value and loaded and class_list is not None):
        module_marks, module_sheet, collated_note = None, None, mo.md("")
    else:
        _done, _error = attempt(
            lambda: collate_the_module(found.module, class_list, source.value)
        )
        if _error is not None:
            module_marks, module_sheet = None, None
            collated_note = failed("Collating the module", _error)
        else:
            module_marks, module_sheet = _done
            _banded = module_sheet["Letter Grade"].value_counts().sort_index()
            collated_note = mo.vstack(
                [
                    mo.md(
                        f"""
                        ### Collated

                        **{len(module_sheet)} students** ·
                        `{list(module_sheet.columns)}`

                        Grades: `{_banded.to_dict()}`

                        A blank mark counts as zero, the way the sheet's own
                        `SUM` reads an empty cell — so a module collated
                        before all the marking is in reads as a complete set
                        of low grades.
                        """
                    ),
                    module_sheet,
                ]
            )

    collated_note
    return module_marks, module_sheet


@app.cell
def departmental_button(loaded, found, module_sheet):
    dept_sheet = mo.ui.run_button(label="Build and fill the departmental sheet")

    def _panel():
        template = found.module.departmental_template_path
        if template is None or not template.exists():
            return mo.md(
                f"""
                ### 6. The departmental sheet

                *Not yet — this module has no departmental template.* Put the
                department's blank workbook in the module folder and name it
                in `module.toml`:

                ```toml
                [paths]
                departmental_template = "Dept grade sheet Template 2026.xlsx"
                ```

                It is the department's file and it changes year to year, so
                the module keeps its own copy rather than this tool using
                whichever one it happens to have.
                """
            )
        return mo.vstack(
            [
                mo.md(
                    f"""
                    ### 6. The departmental sheet

                    Lays the department's workbook out for this module's
                    assessments and fills in the name, the id and each mark as
                    awarded. The weighted columns and the total are left to
                    the sheet's own formulas — where our arithmetic and the
                    sheet disagree, the sheet wins.

                    Template: `{template.name}`
                    """
                ),
                dept_sheet,
            ]
        )

    (_panel() if module_sheet is not None else mo.md("")) if loaded else mo.md("")
    return (dept_sheet,)


@app.cell
def do_departmental(
    dept_sheet, write_the_departmental_sheet, attempt, failed, found, module_sheet,
    replace,
):
    if not (dept_sheet.value and module_sheet is not None):
        departmental_done = mo.md("")
    else:
        _module = found.module
        _destination = (
            _module.departmental_sheet_path
            or _module.root / f"{_module.code} grades.xlsx"
        )
        _done, _error = attempt(
            lambda: write_the_departmental_sheet(
                _module, module_sheet, _destination, replace.value
            )
        )
        if _error is not None:
            departmental_done = failed("The departmental sheet", _error)
        else:
            _path, _written = _done
            _flag = found.file.module.status.departmental_sheet_written
            departmental_done = mo.md(
                f"""
                ### Written

                **{_written}** — `{_path}`

                Recorded `departmental_sheet_written`:
                **{"yes" if _flag else "no"}**
                """
            )

    departmental_done
    return


@app.cell
def moderation_widgets():
    per_band = mo.ui.number(
        start=1, stop=5, step=1, value=1, label="students per band"
    )
    borderline_mode = mo.ui.dropdown(
        options=list(BORDERLINE_MODES), value="include", label="borderline cases"
    )
    moderate = mo.ui.run_button(label="Draw the sample and build the pack")
    return borderline_mode, moderate, per_band


@app.cell
def moderation_panel(loaded, module_sheet, per_band, borderline_mode, moderate):
    _panel = mo.vstack(
        [
            mo.md(
                """
                ### 7. The moderation pack

                A random draw of *n* per grade band, plus the students within
                a point of the next grade up, and the folders they submitted
                copied into `Moderation/`. The draw records its own seed, in
                the manifest, which is what makes it defensible months later.
                """
            ),
            mo.hstack([per_band, borderline_mode], justify="start"),
            moderate,
        ]
    )
    (_panel if module_sheet is not None else mo.md("")) if loaded else mo.md("")
    return


@app.cell
def do_moderation(
    moderate, draw_the_sample, build_the_pack, attempt, failed, found, module_sheet,
    per_band, borderline_mode, replace,
):
    if not (moderate.value and module_sheet is not None):
        moderation_done = mo.md("")
    else:
        def _moderate():
            sample = draw_the_sample(
                module_sheet, int(per_band.value), borderline_mode.value
            )
            pack = build_the_pack(
                found.module,
                sample,
                found.module.root / "Moderation",
                replace.value,
            )
            return sample, pack

        _done, _error = attempt(_moderate)
        if _error is not None:
            moderation_done = failed("The moderation pack", _error)
        else:
            _sample, _pack = _done
            _flag = found.file.module.status.moderation_pack_built
            moderation_done = mo.vstack(
                [
                    mo.md(
                        f"""
                        ### Pack built

                        **{_sample}**

                        **{_pack}** — `{_pack.root}`

                        Bands that could not fill the quota:
                        `{_sample.short_bands or "none"}`

                        Selected but submitted nothing: `{_pack.missing or "none"}`
                        — named rather than left as an empty folder, which
                        would read as work already been through.

                        Recorded `moderation_pack_built`:
                        **{"yes" if _flag else "no"}**
                        """
                    ),
                    _sample.selected,
                ]
            )

    moderation_done
    return


@app.cell
def si_button(loaded, found, module_sheet):
    si = mo.ui.run_button(label="Fill in SI's upload file")

    def _panel():
        issued = found.module.si_file_path
        if issued is None or not issued.exists():
            return mo.md(
                """
                ### 8. The SI upload

                *Not yet — this module has no SI file.* SI issues it; nothing
                here generates one. Put it in the module folder and name it:

                ```toml
                [paths]
                si_file = "PS4034_SI.CSV"
                ```
                """
            )
        return mo.vstack(
            [
                mo.md(
                    f"""
                    ### 8. The SI upload

                    Fills two columns of the file SI issued and leaves the
                    rest of it exactly as it arrived — its encoding, its line
                    endings and its quoting included. Written alongside it as
                    a copy; the issued file is not touched.

                    Issued: `{issued.name}`
                    """
                ),
                si,
            ]
        )

    (_panel() if module_sheet is not None else mo.md("")) if loaded else mo.md("")
    return (si,)


@app.cell
def do_si(si, fill_si_upload, attempt, failed, found, module_sheet):
    if not (si.value and module_sheet is not None):
        si_done = mo.md("")
    else:
        _module = found.module
        _done, _error = attempt(
            lambda: fill_si_upload(
                _module, module_sheet, _module.root / f"{_module.code}_upload.CSV"
            )
        )
        if _error is not None:
            si_done = failed("The SI upload", _error)
        else:
            _flag = found.file.module.status.si_file_written
            si_done = mo.md(
                f"""
                ### Filled

                **{_done}**

                Recorded `si_file_written`: **{"yes" if _flag else "no"}**

                {"" if _flag else
                 "Not recorded. A student with a mark whom SI has no row for "
                 "means the two records disagree, which is not a finished "
                 "step."}
                """
            )

    si_done
    return


@app.cell
def manual_widgets():
    # The half only a person can know. We wrote a file; we cannot see that it
    # was sent, read or accepted.
    mark_moderated = mo.ui.run_button(label="This assessment has been moderated")
    mark_sent = mo.ui.run_button(label="The sheet has gone to the department")
    mark_submitted = mo.ui.run_button(label="The upload has been lodged with SI")
    return mark_moderated, mark_sent, mark_submitted


@app.cell
def manual_panel(loaded, chosen, mark_moderated, mark_sent, mark_submitted):
    _panel = mo.vstack(
        [
            mo.md(
                f"""
                ### 9. The things only you know

                Everything above is set from what a step produced. These are
                not: a pack having been *built* is not a pack having been
                *read*, and a sheet having been written is not a sheet having
                been sent.

                The first applies to **{chosen.id if chosen is not None else "the chosen assessment"}**;
                the other two to the module.
                """
            ),
            mark_moderated,
            mark_sent,
            mark_submitted,
        ]
    )
    _panel if loaded else mo.md("")
    return


@app.cell
def do_manual(
    mark_moderated, mark_sent, mark_submitted, attempt, failed, found, chosen, loaded
):
    def _set():
        # Each button answered on its own. Chained, a click on the first with
        # no assessment chosen would fall through and set one of the others,
        # which is a flag nobody asked for on a record nobody was looking at.
        done = []
        if mark_moderated.value and chosen is not None:
            found.file.set_status(chosen.id, moderated=True)
            done.append(f"`{chosen.id}` marked as moderated.")
        if mark_sent.value:
            found.file.set_module_status(sent_to_department=True)
            done.append("Marked as sent to the department.")
        if mark_submitted.value:
            found.file.set_module_status(si_submitted=True)
            done.append("Marked as lodged with SI.")
        return " ".join(done) if done else "Nothing to record — choose an assessment first."

    if not (loaded and (mark_moderated.value or mark_sent.value or mark_submitted.value)):
        manual_done = mo.md("")
    else:
        _done, _error = attempt(_set)
        manual_done = (
            failed("Recording that", _error)
            if _error is not None
            else mo.md(f"{_done} Click **Re-read this folder** to see it.")
        )

    manual_done
    return


if __name__ == "__main__":
    app.run()
