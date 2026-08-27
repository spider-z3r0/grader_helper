import marimo

app = marimo.App(width="medium")

with app.setup():
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
        import_brightspace_classlist,
        ingest_completed_graderfiles,
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
    ROOT = pl.Path.home() / "grader_helper_scratch" / "PS4001"

    # The assessments this walkthrough drives.
    ASSESSMENT_1_ID = "cw1"
    ASSESSMENT_2_ID = "cw2"


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
    FAKE = make_fake_module(ROOT, distributed=False, marked=False)

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



if __name__ == "__main__":
    app.run()
