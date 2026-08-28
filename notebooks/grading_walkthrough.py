import marimo

app = marimo.App(width="medium")

with app.setup():
    import os
    import pathlib as pl
    import sys

    import marimo as mo
    import pandas as pd
    from openpyxl import load_workbook

    sys.path.insert(0, "tests")          # so `fake_module` is importable
    from fake_module import make_fake_module

    from grader_helper import (
        alphabetise_folders,
        assign_graders_individual,
        catch_grades,
        distribute_feedback_sheets,
        extract_studentid_grade,
        collate_module_marks,
        collect_quiz_marks,
        import_brightspace_classlist,
        ingest_completed_graderfiles,
        prepare_data_for_departmental_template,
        read_quiz,
        save_distributed_graders,
        save_grader_sheets,
        scan_multiple_subs,
    )
    from grader_helper.file_operations.brightspace_name_folders import (
        brightspace_name_folders,
    )
    from grader_helper.models import ModuleFile

    # Somewhere short and disposable. NOT under OneDrive -- the generated
    # folder names are long, and make_fake_module overwrites feedback sheets
    # every time it runs.
    #
    # The environment variable is only so the test suite can run this whole
    # notebook into a temporary directory instead of your home folder. Ignore
    # it; the default is the path you want.
    ROOT = pl.Path(
        os.environ.get(
            "GRADER_HELPER_SCRATCH", pl.Path.home() / "grader_helper_scratch"
        )
    ) / "PS4001"

    # The assessments this walkthrough drives.
    ASSESSMENT_1_ID = "cw1"
    ASSESSMENT_2_ID = "cw2"
    ASSESSMENT_3_ID = "quizzes"


@app.cell
def intro():
    mo.md(
        """
        # Grading walkthrough

        One assessment, from an unzipped Brightspace download to a reconciled
        set of marks and folders renamed ready to go back up.

        The marking itself is a two-person process, and the last step is the
        control that makes it trustworthy:

        1. **Grader** fills in the feedback sheet — `grade_cell` calculates
           the score
        2. **Grader** copies that value into their own grade sheet
           (`KOM.xlsx`)
        3. **Module leader** collates the grade sheets into
           `completed_grades.xlsx`, which is a filled-in `distributed.xlsx`
        4. **Module leader** reads the feedback sheets and reconciles the two

        Step 2 is a manual copy, so steps 3 and 4 exist to catch it going
        wrong. `catch_grades` and `ingest_completed_graderfiles` are the two
        halves of that audit, not alternatives.

        Two courseworks go through all of that. The **quizzes** at the end do
        not, and the reason is worth holding on to: every step above exists
        because a human copies a number by hand. Nobody marks a quiz, so
        there is no allocation, no feedback sheet, no transcription and
        nothing to reconcile — just Brightspace's own exports, read.

        Run the cells in order. Each one prints what it did.
        """
    )
    return


@app.cell
def init_the_module():
    # make_fake_module calls init_module for us, then fills the tree with a
    # class list, submission folders and blank feedback sheets.
    #
    # distributed=False so the distribution step below has something to do.
    #
    # quizzes=True puts eleven weekly quizzes where the MCQ would be, and
    # writes Brightspace's own exports into their submissions folder. The
    # weights are unchanged -- the quiz takes the MCQ's ten marks, not extra
    # ones -- so nothing about cw1 or cw2 moves.
    #
    # DELETE ROOT before re-running if you built it before the quizzes
    # existed: module.toml stops mentioning the MCQ, but `assessments/mcq/`
    # stays on disk and is confusing to find there.
    FAKE = make_fake_module(ROOT, distributed=False, marked=False, quizzes=True)

    HANDLE = ModuleFile.load(ROOT)
    MODULE = HANDLE.module

    mo.md(f"""
    **{MODULE.code} {MODULE.name}** ({MODULE.year})

    - leader: `{MODULE.leader}`
    - root: `{MODULE.root}`
    - grade sheet columns: `{MODULE.grade_sheet_columns}`
    """)
    return FAKE, HANDLE, MODULE


@app.cell
def cw1_pick_the_assessment(MODULE):
    A = MODULE.assessment(ASSESSMENT_1_ID)
    GRADERS = [person.initials for person in A.graders]

    mo.md(f"""
    ### {A.name} (`{A.id}`)

    Marked out of {A.marks_out_of}, worth {A.weight}. Graders: `{GRADERS}`.
    Mark lives in cell `{A.grade_cell}` of each feedback sheet.

    | | |
    |---|---|
    | folder | `{A.folder_path}` |
    | submissions | `{A.submissions_path}` |
    | grading output | `{A.grading_output_path}` |
    | rubric | `{A.rubric_path}` |
    """)
    return A, GRADERS


@app.cell
def ingest_class_list(MODULE):
    cl = import_brightspace_classlist(MODULE.classlist_path)
    cl
    return (cl,)


@app.cell
def cw1_check_for_resubmissions(A):
    # alphabetise_folders refuses to rename anything while a student has more
    # than one submission folder, so find them first. Resolve by deleting the
    # ones that do not count -- which one counts is a judgement call, not
    # something the tool should make for you.
    repeated = scan_multiple_subs(A.submissions_path)

    mo.md(
        f"**{len(repeated)} student(s) submitted more than once:** "
        f"`{sorted(repeated)}`"
        if repeated
        else "**No resubmissions.** Safe to alphabetise."
    )
    return (repeated,)


@app.cell
def cw1_resolve_resubmissions(A, repeated):
    # Keeps the EARLIEST submission for each repeat. Change to [:-1] to keep
    # the latest instead. Delete this cell entirely once you would rather
    # resolve them by hand.
    for student_id in repeated:
        folders = sorted(
            p for p in A.submissions_path.iterdir()
            if p.is_dir() and student_id in p.name
        )
        for extra in folders[1:]:
            for f in extra.rglob("*"):
                if f.is_file():
                    f.unlink()
            for d in sorted(extra.rglob("*"), reverse=True):
                d.rmdir()
            extra.rmdir()

    resolved = scan_multiple_subs(A.submissions_path)
    mo.md(f"Remaining resubmissions: `{sorted(resolved)}`")
    return


@app.cell
def cw1_distribute_graders(cl, GRADERS):
    # Even split, randomised. overwrite=True lets the cell re-run.
    allocation = assign_graders_individual(cl, GRADERS, overwrite=True)

    allocation["grader"].value_counts()
    return (allocation,)


@app.cell
def cw1_save_the_grader_sheets(A, GRADERS, allocation):
    # The master allocation sits at the assessment root; the per-grader
    # workbooks go in grading_output, which is safe to delete and regenerate.
    master = save_distributed_graders(allocation, A.folder_path, overwrite=True)
    workbooks = save_grader_sheets(
        allocation,
        A.grading_output_path,
        GRADERS,
        criteria=["Mark"],
        overwrite=True,
    )

    mo.md(f"""
    - master: `{master.name}` at the assessment root
    - workbooks: `{[p.name for p in workbooks.values()]}` in `grading_output/`
    """)
    return


@app.cell
def cw1_distribute_the_feedback_sheets(A):
    # A copy of the blank rubric into every student's folder, named for their
    # id. Existing sheets are skipped, never overwritten -- they may already
    # carry marks.
    distribution = distribute_feedback_sheets(A.submissions_path, A.rubric_path)

    mo.md(f"**{distribution}** — unrecognised: `{distribution.unmatched}`")
    return


@app.cell
def cw1_alphabetise_the_folders(A, cl):
    # Brightspace format -> UL format:
    #   "27236-46025 - 23304308 Angood - 05 March 2026 612 PM"
    #                       becomes
    #   "ANGOOD, AOIFE(23304308)"
    #
    # Returns None. The log is written into the submissions folder, and
    # brightspace_name_folders needs it to rename them back later.
    alphabetise_folders(cl, A.submissions_path)

    rename_log = pd.read_csv(A.submissions_path / "folder_rename_log.csv")
    rename_log
    return (rename_log,)


@app.cell
def cw1_graders_complete_the_feedback_sheets(A):
    """GRADER — marks each allocated student's feedback sheet."""
    # A real feedback sheet CALCULATES the grade cell from the rubric rows
    # above it; the grader fills those in and the total falls out. These
    # synthetic sheets hold a literal instead, so this writes the value
    # straight in.
    #
    # Delete this cell when running for real. The graders do this.
    marked = 0
    for sheet in sorted(A.submissions_path.glob("*/Feedback sheet *.xlsx")):
        workbook = load_workbook(sheet)
        workbook.active[A.grade_cell] = 40 + (marked * 7) % 55
        workbook.save(sheet)
        marked += 1

    mo.md(f"Marked **{marked}** feedback sheets (cell `{A.grade_cell}`).")
    return


@app.cell
def cw1_graders_copy_marks_to_their_grade_sheets(A, GRADERS):
    """GRADER — copies each calculated mark into their own grade sheet.

    This is the transcription step, and the reason the reconciliation below
    exists. In real use a grader reads the number off the feedback sheet and
    types it into their workbook, which is exactly where a mark can go
    astray.
    """
    transcribed = {}

    sheets = {
        found.stem.split(" ")[-1]: found
        for found in A.submissions_path.glob("*/Feedback sheet *.xlsx")
    }

    for grader in GRADERS:
        grader_file = A.grading_output_path / f"{grader}.xlsx"
        allocated = pd.read_excel(grader_file, dtype={"Student ID": str})

        marks = []
        for allocated_id in allocated["Student ID"]:
            their_sheet = sheets.get(allocated_id)
            # The same reader the module leader uses below, so the two see
            # the same value -- including the fallbacks for a sheet whose
            # formula has not been recalculated.
            result = (
                extract_studentid_grade(their_sheet, A.grade_cell)
                if their_sheet
                else None
            )
            marks.append(result[1] if result else None)

        allocated["Mark"] = marks
        allocated.to_excel(grader_file, index=False)
        transcribed[grader] = int(allocated["Mark"].notna().sum())

    mo.md(f"Marks copied into each grade sheet: `{transcribed}`")
    return


@app.cell
def cw1_leader_reads_the_feedback_sheets(A):
    """MODULE LEADER — what the students actually received."""
    # Walks the submissions tree, opens every feedback sheet, reads the grade
    # cell. Student id comes from the filename, not the folder.
    grades = catch_grades(A.submissions_path, A.grade_cell)

    grades
    return (grades,)


@app.cell
def cw1_leader_collates_the_grade_sheets(A, GRADERS):
    """MODULE LEADER — every grader's sheet into one collated file.

    The result is a filled-in `distributed.xlsx`: the same allocation, with
    the marks in it. Written to `grading_output/completed_grades.xlsx`.
    """
    # require_all=True (the default) refuses if any grader has not returned
    # their file -- missing files mean missing marks. Pass require_all=False
    # to proceed with whoever has, and it warns about the rest.
    #
    # Student id columns are read as text. Left to pandas they come back as
    # int64, which drops leading zeros and makes the result unmergeable with
    # the class list.
    completed = ingest_completed_graderfiles(
        A.grading_output_path,
        GRADERS,
        file_type="excel",
        save=True,
        overwrite=True,
    )

    completed
    return (completed,)


@app.cell
def cw1_reconcile_the_two_records(completed, grades):
    """MODULE LEADER — does the student's number match the recorded one?

    The student receives the feedback sheet; the department receives the
    collated file. Between them sits a manual copy, so this is the check that
    the two agree. Run it for real -- it is the point of collating and
    catching separately.
    """
    # It also proves the ids survived the Excel round trip: a merge between an
    # object column and an int64 one does not mismatch quietly, it raises.
    #
    # Not every disagreement is a fault. A student who never submitted is
    # allocated a grader from the class list, so they appear in the collated
    # file (`right_only`) but have no feedback sheet to read a mark from. Look
    # at `_merge` before assuming something went wrong:
    #
    #   right_only  collated but not submitted -- no feedback sheet exists
    #   left_only   marked, but nobody was allocated them -- worth a look
    #   both, differing marks  a transcription slip at the copy step
    comparison = grades.merge(
        completed[["Student ID", "Mark"]], on="Student ID", how="outer",
        indicator=True,
    )
    disagreements = comparison[
        (comparison["_merge"] != "both") | (comparison["grade"] != comparison["Mark"])
    ]

    mo.md(
        f"**{len(comparison)}** students compared, "
        f"**{len(disagreements)}** disagreements."
        + ("\n\nEvery mark the students received matches the collated file."
           if disagreements.empty else "")
    )
    return (disagreements,)


@app.cell
def cw1_rename_for_reupload(A, rename_log):
    # UL format back to Brightspace format, so the folders can be re-uploaded.
    #
    # It takes the rename LOG, not the class list. The names come back exactly
    # as Brightspace wrote them, case included -- matching is
    # case-insensitive, the name written is not.
    restoration = brightspace_name_folders(rename_log, A.submissions_path)

    restored = sorted(p.name for p in A.submissions_path.iterdir() if p.is_dir())
    expected = sorted(rename_log["Original Name"])
    exact = [name for name in expected if name in restored]

    mo.md(
        f"**{restoration}**\n\n"
        f"{len(exact)} of {len(expected)} folders restored to the exact name "
        "Brightspace gave.\n\n```\n" + "\n".join(restored[:4]) + "\n```"
    )
    return


@app.cell
def cw1_record_progress(HANDLE):
    HANDLE.set_status(
        ASSESSMENT_1_ID,
        graders_allocated=True,
        sheets_distributed=True,
        grades_collected=True,
    )

    # Read back the assessment we just wrote, not the other one.
    status = ModuleFile.load(ROOT).module.assessment(ASSESSMENT_1_ID).status
    status.model_dump()
    return


@app.cell
def cw2_pick_the_assessment(MODULE):
    A2 = MODULE.assessment(ASSESSMENT_2_ID)
    GRADERS2 = [person.initials for person in A2.graders]

    mo.md(f"""
    ### {A2.name} (`{A2.id}`)

    Marked out of {A2.marks_out_of}, worth {A2.weight}. Graders: `{GRADERS2}`.
    Mark lives in cell `{A2.grade_cell}` of each feedback sheet.

    | | |
    |---|---|
    | folder | `{A2.folder_path}` |
    | submissions | `{A2.submissions_path}` |
    | grading output | `{A2.grading_output_path}` |
    | rubric | `{A2.rubric_path}` |
    """)
    return A2, GRADERS2


@app.cell
def cw2_check_for_resubmissions(A2):
    repeated2 = scan_multiple_subs(A2.submissions_path)

    mo.md(
        f"**{len(repeated2)} student(s) submitted more than once:** "
        f"`{sorted(repeated2)}`"
        if repeated2
        else "**No resubmissions.** Safe to alphabetise."
    )
    return (repeated2,)


@app.cell
def cw2_resolve_resubmissions(A2, repeated2):
    for student_id2 in repeated2:
        folders2 = sorted(
            p for p in A2.submissions_path.iterdir()
            if p.is_dir() and student_id2 in p.name
        )
        for extra2 in folders2[1:]:
            for f2 in extra2.rglob("*"):
                if f2.is_file():
                    f2.unlink()
            for d2 in sorted(extra2.rglob("*"), reverse=True):
                d2.rmdir()
            extra2.rmdir()

    resolved2 = scan_multiple_subs(A2.submissions_path)
    mo.md(f"Remaining resubmissions: `{sorted(resolved2)}`")
    return


@app.cell
def cw2_distribute_graders(cl, GRADERS2):
    # A fresh allocation. Who marks cw2 is independent of who marked cw1.
    allocation2 = assign_graders_individual(cl, GRADERS2, overwrite=True)

    allocation2["grader"].value_counts()
    return (allocation2,)


@app.cell
def cw2_save_the_grader_sheets(A2, GRADERS2, allocation2):
    master2 = save_distributed_graders(allocation2, A2.folder_path, overwrite=True)
    workbooks2 = save_grader_sheets(
        allocation2,
        A2.grading_output_path,
        GRADERS2,
        criteria=["Mark"],
        overwrite=True,
    )

    mo.md(f"""
    - master: `{master2.name}` at the assessment root
    - workbooks: `{[p.name for p in workbooks2.values()]}` in `grading_output/`
    """)
    return


@app.cell
def cw2_distribute_the_feedback_sheets(A2):
    # A2.rubric_path, not A.rubric_path -- each assessment has its own blank
    # sheet, and cw2's rubric lives in cw2's folder.
    distribution2 = distribute_feedback_sheets(A2.submissions_path, A2.rubric_path)

    mo.md(f"**{distribution2}** — unrecognised: `{distribution2.unmatched}`")
    return


@app.cell
def cw2_alphabetise_the_folders(A2, cl):
    alphabetise_folders(cl, A2.submissions_path)

    rename_log2 = pd.read_csv(A2.submissions_path / "folder_rename_log.csv")
    rename_log2
    return (rename_log2,)


@app.cell
def cw2_graders_complete_the_feedback_sheets(A2):
    """GRADER — marks each allocated student's feedback sheet."""
    # Delete this cell when running for real. The graders do this.
    marked2 = 0
    for sheet2 in sorted(A2.submissions_path.glob("*/Feedback sheet *.xlsx")):
        workbook2 = load_workbook(sheet2)
        workbook2.active[A2.grade_cell] = 45 + (marked2 * 5) % 50
        workbook2.save(sheet2)
        marked2 += 1

    mo.md(f"Marked **{marked2}** feedback sheets (cell `{A2.grade_cell}`).")
    return


@app.cell
def cw2_graders_copy_marks_to_their_grade_sheets(A2, GRADERS2):
    """GRADER — copies each calculated mark into their own grade sheet."""
    transcribed2 = {}

    sheets2 = {
        found2.stem.split(" ")[-1]: found2
        for found2 in A2.submissions_path.glob("*/Feedback sheet *.xlsx")
    }

    for grader2 in GRADERS2:
        grader_file2 = A2.grading_output_path / f"{grader2}.xlsx"
        allocated2 = pd.read_excel(grader_file2, dtype={"Student ID": str})

        marks2 = []
        for allocated_id2 in allocated2["Student ID"]:
            their_sheet2 = sheets2.get(allocated_id2)
            result2 = (
                extract_studentid_grade(their_sheet2, A2.grade_cell)
                if their_sheet2
                else None
            )
            marks2.append(result2[1] if result2 else None)

        allocated2["Mark"] = marks2
        allocated2.to_excel(grader_file2, index=False)
        transcribed2[grader2] = int(allocated2["Mark"].notna().sum())

    mo.md(f"Marks copied into each grade sheet: `{transcribed2}`")
    return


@app.cell
def cw2_leader_reads_the_feedback_sheets(A2):
    """MODULE LEADER — what the students actually received."""
    grades2 = catch_grades(A2.submissions_path, A2.grade_cell)

    grades2
    return (grades2,)


@app.cell
def cw2_leader_collates_the_grade_sheets(A2, GRADERS2):
    """MODULE LEADER — every grader's sheet into one collated file."""
    completed2 = ingest_completed_graderfiles(
        A2.grading_output_path,
        GRADERS2,
        file_type="excel",
        save=True,
        overwrite=True,
    )

    completed2
    return (completed2,)


@app.cell
def cw2_reconcile_the_two_records(completed2, grades2):
    """MODULE LEADER — does the student's number match the recorded one?"""
    comparison2 = grades2.merge(
        completed2[["Student ID", "Mark"]], on="Student ID", how="outer",
        indicator=True,
    )
    disagreements2 = comparison2[
        (comparison2["_merge"] != "both")
        | (comparison2["grade"] != comparison2["Mark"])
    ]

    mo.md(
        f"**{len(comparison2)}** students compared, "
        f"**{len(disagreements2)}** disagreements."
        + ("\n\nEvery mark the students received matches the collated file."
           if disagreements2.empty else "")
    )
    return (disagreements2,)


@app.cell
def cw2_rename_for_reupload(A2, rename_log2):
    # As cw1: the log, not the class list, and the names come back exactly.
    restoration2 = brightspace_name_folders(rename_log2, A2.submissions_path)

    restored2 = sorted(p.name for p in A2.submissions_path.iterdir() if p.is_dir())
    expected2 = sorted(rename_log2["Original Name"])
    exact2 = [name for name in expected2 if name in restored2]

    mo.md(
        f"**{restoration2}**\n\n"
        f"{len(exact2)} of {len(expected2)} folders restored to the exact name "
        "Brightspace gave.\n\n```\n" + "\n".join(restored2[:4]) + "\n```"
    )
    return


@app.cell
def cw2_record_progress(HANDLE):
    HANDLE.set_status(
        ASSESSMENT_2_ID,
        graders_allocated=True,
        sheets_distributed=True,
        grades_collected=True,
    )

    # Read back the assessment we just wrote, not the other one.
    status2 = ModuleFile.load(ROOT).module.assessment(ASSESSMENT_2_ID).status
    status2.model_dump()
    return


@app.cell
def quiz_intro():
    mo.md(
        """
        ## The quizzes

        Everything above happens because a grader writes a number on a
        feedback sheet and then copies it somewhere else by hand. A quiz has
        neither: Brightspace scores it, and exports one CSV per quiz.

        So the whole of steps 3–7 collapses into a single read. There is
        nothing to allocate, nothing to distribute, no second record, and so
        nothing to reconcile — the audit that makes the coursework
        trustworthy has nothing to audit here.

        What is left is the module's own rules about what a pass is, and
        those live in `module.toml` rather than in this notebook.
        """
    )
    return


@app.cell
def quiz_pick_the_assessment(MODULE):
    A3 = MODULE.assessment(ASSESSMENT_3_ID)
    quiz_exports = sorted(A3.submissions_path.glob("*.csv"))

    mo.md(f"""
    ### {A3.name} (`{A3.id}`)

    Marked out of {A3.marks_out_of}, worth {A3.weight}. No graders, no
    rubric, no grade cell — nobody marks these.

    **{len(quiz_exports)} exports** for {A3.marks_out_of} marks, so one may
    be dropped.

    | | |
    |---|---|
    | pass mark | `{A3.pass_mark}` — strictly above, so exactly {A3.pass_mark} fails |
    | free passes | `{A3.free_passes}` |
    | exports | `{A3.submissions_path}` |
    | column | `{A3.raw_column}` |

    Both numbers are read off the assessment. They are in `module.toml`, so
    the module records its own rules rather than this notebook restating
    them.
    """)
    return A3, quiz_exports


@app.cell
def quiz_look_at_one_export(quiz_exports):
    # What Brightspace actually hands over, and what read_quiz does to it:
    # the '#' comes off the username (the class list has it stripped too, and
    # a join between the two forms silently matches nothing), every column is
    # read as text so a leading zero survives, and the score column is named
    # after the file.
    one_quiz = read_quiz(quiz_exports[0]).collect()

    one_quiz
    return (one_quiz,)


@app.cell
def quiz_collect_the_marks(A3, cl):
    """MODULE LEADER — the only step there is."""
    # No pass mark and no free passes are passed in. Both come off the
    # assessment, which read them from module.toml. With neither there, this
    # raises rather than picking a threshold nobody chose.
    quiz_marks = collect_quiz_marks(A3, cl)

    quiz_marks
    return (quiz_marks,)


@app.cell
def quiz_check_the_edges(A3, quiz_marks):
    # Two students are worth looking at by name, because they are where the
    # rules are visible rather than merely applied.
    by_id = quiz_marks.set_index("Student ID")[A3.raw_column]

    mo.md(f"""
    | student | mark | why |
    |---|---|---|
    | 23304309 Joyce | **{by_id["23304309"]}** | sat no quiz at all, so appears in no export. The free pass is *not* given: the departmental sheet awards NG rather than F while the total is zero, and one free mark here would quietly make him a fail |
    | 23304308 Ivers | **{by_id["23304308"]}** | passed 9 of 11, and the free pass takes her to the {A3.marks_out_of} available. It cannot take her past it |

    Full distribution: `{by_id.value_counts().sort_index().to_dict()}`

    Every student in the class list has a row, including the ones in no
    export. A missing row would take a component out of a module total, and
    a total missing a component is still a plausible number.
    """)
    return


@app.cell
def quiz_record_progress(HANDLE):
    HANDLE.set_status(ASSESSMENT_3_ID, grades_collected=True)

    status3 = ModuleFile.load(ROOT).module.assessment(ASSESSMENT_3_ID).status
    status3.model_dump()
    return


@app.cell
def the_whole_module():
    mo.md(
        """
        ## The module

        Everything above is one assessment at a time. This is the module: the
        three sets of marks in one frame, totalled, and turned into letter
        grades.

        `collate_module_marks` is the only thing here that walks a whole
        module, and it fetches each assessment's marks from wherever that
        kind of assessment keeps them -- the courseworks off their feedback
        sheets, the quizzes out of Brightspace's exports. It decides that by
        asking what the assessment *has*, not what its `type` says, because
        an MCQ can be sat in Brightspace, on a feedback sheet, or on paper in
        a lecture theatre, and all three are `type = "mcq"`.
        """
    )
    return


@app.cell
def collate_the_whole_module(MODULE, cl):
    """MODULE LEADER -- every assessment's marks, in one frame."""
    # source="feedback" reads what the students received. The other record is
    # source="collated", the completed_grades.xlsx the graders' sheets were
    # collated into. They must agree -- that is what the reconciliation above
    # checks -- and this deliberately will not fall back from one to the
    # other, because a substitution nobody asked for is invisible.
    module_marks = collate_module_marks(MODULE, cl, source="feedback")

    module_marks
    return (module_marks,)


@app.cell
def the_departmental_sheet(MODULE, module_marks):
    """MODULE LEADER -- totalled, banded, in the department's column order."""
    module_sheet = prepare_data_for_departmental_template(module_marks, MODULE)

    module_sheet
    return (module_sheet,)


@app.cell
def look_at_the_edges(module_sheet):
    graded = module_sheet.set_index("Student ID")

    mo.md(f"""
    | student | total | grade | why |
    |---|---|---|---|
    | 23304305 Egan | {graded.loc["23304305", "Total % Grade"]} | {graded.loc["23304305", "Letter Grade"]} | totals exactly 64.5. Excel rounds half away from zero and says 65 (B2); Python's own round says 64 (B3). The sheet is the source of truth, so `excel_round` is what runs |
    | 23304309 Joyce | {graded.loc["23304309", "Total % Grade"]} | {graded.loc["23304309", "Letter Grade"]} | scored zero on everything and sat no quiz. NG, not F -- no participation is a different thing from a mark of zero |
    | 23304311 Lynch | {graded.loc["23304311", "Total % Grade"]} | {graded.loc["23304311", "Letter Grade"]} | never submitted, and still on the sheet. A student missing from the sheet has no grade at all, which nobody notices |

    Writing this into the department's own workbook is the next piece, and it
    needs the workbook: `paths.departmental_sheet` in `module.toml` is where
    it goes.
    """)
    return


if __name__ == "__main__":
    app.run()
