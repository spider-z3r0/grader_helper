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

    # Which assessment this walkthrough drives.
    ASSESSMENT_ID = "cw1"


@app.cell
def intro():
    mo.md(
        """
        # Grading walkthrough

        One assessment, from an unzipped Brightspace download to marks read
        back out of the feedback sheets, and the folders renamed ready to go
        back up.

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
def pick_the_assessment(MODULE):
    A = MODULE.assessment(ASSESSMENT_ID)
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
def check_for_resubmissions(A):
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
def resolve_resubmissions(A, repeated):
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
def distribute_graders(cl, GRADERS):
    # Even split, randomised. overwrite=True lets the cell re-run.
    allocation = assign_graders_individual(cl, GRADERS, overwrite=True)

    allocation["grader"].value_counts()
    return (allocation,)


@app.cell
def save_the_grader_sheets(A, GRADERS, allocation):
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
def distribute_the_feedback_sheets(A):
    # A copy of the blank rubric into every student's folder, named for their
    # id. Existing sheets are skipped, never overwritten -- they may already
    # carry marks.
    distribution = distribute_feedback_sheets(A.submissions_path, A.rubric_path)

    mo.md(f"**{distribution}** — unrecognised: `{distribution.unmatched}`")
    return


@app.cell
def alphabetise_the_folders(A, cl):
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
def simulate_marking(A):
    # Stands in for the graders doing their work. Writes a mark into the
    # grade cell of every distributed feedback sheet. Delete this cell when
    # running against real submissions.
    marked = 0
    for sheet in sorted(A.submissions_path.glob("*/Feedback sheet *.xlsx")):
        workbook = load_workbook(sheet)
        workbook.active[A.grade_cell] = 40 + (marked * 7) % 55
        workbook.save(sheet)
        marked += 1

    mo.md(f"Wrote a mark into `{A.grade_cell}` of **{marked}** feedback sheets.")
    return


@app.cell
def catch_the_grades(A):
    # Walks the submissions tree, opens every feedback sheet, reads the grade
    # cell. Student id comes from the filename, not the folder.
    grades = catch_grades(A.submissions_path, A.grade_cell)

    grades
    return (grades,)


@app.cell
def transcribe_into_the_grader_workbooks(A, GRADERS, grades):
    # There are two routes to a single sheet of grades, and this is the second.
    #
    #   feedback sheets  -> catch_grades                  (above)
    #   grader workbooks -> ingest_completed_graderfiles  (below)
    #
    # A grader does one or the other: marks each student's feedback sheet, or
    # fills in the Mark column of their own workbook. Here the marks caught
    # above are transcribed into the workbooks, which is what a grader doing
    # both would do -- and it makes the cross-check below meaningful.
    #
    # Delete this cell when running for real; the graders fill these in.
    caught = dict(zip(grades["Student ID"], grades["grade"]))

    for grader in GRADERS:
        grader_file = A.grading_output_path / f"{grader}.xlsx"
        allocated = pd.read_excel(grader_file, dtype={"Student ID": str})
        allocated["Mark"] = allocated["Student ID"].map(caught)
        allocated.to_excel(grader_file, index=False)

    mo.md(
        f"Transcribed **{len(caught)}** marks into "
        f"`{[f'{g}.xlsx' for g in GRADERS]}`."
    )
    return


@app.cell
def ingest_the_grader_files(A, GRADERS):
    # Every grader's workbook, concatenated into one frame, and written to
    # grading_output/completed_grades.xlsx.
    #
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
def cross_check_the_two_routes(completed, grades):
    # Do the feedback sheets and the grader workbooks agree?
    #
    # This is worth running for real. It catches transcription slips, and it
    # proves the ids survived the Excel round trip -- a merge between an
    # object column and an int64 one does not fail quietly, it raises.
    #
    # Not every disagreement is a fault. A student who never submitted is
    # allocated a grader from the class list, so they appear in the workbook
    # (`right_only`) but have no feedback sheet to read a mark from. Look at
    # `_merge` before assuming something went wrong:
    #
    #   right_only  in the workbooks, not in the submissions -- no submission
    #   left_only   marked, but nobody was allocated them -- worth a look
    #   both, differing marks  a transcription slip
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
        + ("\n\nAll marks match across both routes."
           if disagreements.empty else "")
    )
    return (disagreements,)


@app.cell
def rename_for_reupload(A, rename_log):
    # UL format back to Brightspace format, so the folders can be re-uploaded.
    # This is the least tested part of the package -- check its output.
    #
    # It takes the rename LOG, not the class list, and mutates the frame it is
    # given (upper-casing two columns), so hand it a copy.
    #
    # KNOWN DEFECT: the restored names are NOT the originals. It upper-cases
    # `Original Name` for case-insensitive matching and then renames to that
    # upper-cased value, so
    #
    #     27236-46025 - 23304302 Barry - 01 March 2026 600 PM     went in
    #     27236-46025 - 23304302 BARRY - 01 MARCH 2026 600 PM     comes back
    #
    # 11 of 12 differ on the sample cohort. Compare against `rename_log` before
    # re-uploading anything you care about.
    brightspace_name_folders(rename_log.copy(), A.submissions_path)

    restored = sorted(p.name for p in A.submissions_path.iterdir() if p.is_dir())
    changed = sum(
        1 for original, now in zip(sorted(rename_log["Original Name"]), restored)
        if original != now
    )

    mo.md(
        "Folders now look like:\n\n```\n"
        + "\n".join(restored[:5])
        + f"\n```\n\n**{changed} differ from the names Brightspace gave.**"
    )
    return


@app.cell
def record_progress(HANDLE):
    # Write what has been done back into module.toml. Comments and layout
    # survive; only the [status] section changes.
    HANDLE.set_status(
        ASSESSMENT_ID,
        graders_allocated=True,
        sheets_distributed=True,
        grades_collected=True,
    )

    status = ModuleFile.load(ROOT).module.assessment(ASSESSMENT_ID).status
    status.model_dump()
    return


if __name__ == "__main__":
    app.run()
