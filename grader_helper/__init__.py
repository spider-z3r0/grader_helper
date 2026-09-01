#!/usr/bin/env python
# -*- coding: utf-8 -*-


""" This is the init file the folder that contains all the sub-modules. But it's not the top-level init file."""


# models
from .models import (
    Assessment,
    AssessmentStatus,
    AssessmentType,
    GroupSource,
    Module,
    ModuleFile,
    ModulePaths,
    Person,
    init_module,
    load_module,
)

# ingesting
from .ingesting.load_graders import load_graders
from .ingesting.import_brightspace_classlist import import_brightspace_classlist
from .ingesting.ingest_completed_graderfiles import (
    Collation,
    ingest_completed_graderfiles,
    save_collated_grades,
)
from .ingesting.collect_group_membership import (
    AmbiguousGroupError,
    ConflictingGroupsError,
    attach_group_membership,
    collect_group_membership,
)
from .ingesting.import_brightspace_classlist import (
    MissingGroupError,
    group_key,
    resolve_group_column,
)
from .ingesting.collect_quiz_marks import (
    DuplicateAttemptError,
    collect_quiz_marks,
    quiz_name,
    read_quiz,
)

# grader assignment
from .assignment.assign_graders_individual import assign_graders_individual
from .assignment.assign_graders_groups import assign_graders_groups
from .assignment.find_unsubmitted import find_unsubmitted

# dataframe operations
from .dataframe_operations.rounding import excel_round, excel_round_series
from .dataframe_operations.make_letter_grade import make_letter_grade
from .dataframe_operations.calculate_weighted_score import calculate_weighted_score
from .dataframe_operations.calculate_total_module_score import (
    calculate_total_module_score,
)
from .dataframe_operations.sort_order_columns import sort_order_columns
from .dataframe_operations.check_for_weighted_columns import check_for_weighted_columns
from .dataframe_operations.prepare_data_for_departmental_template import (
    prepare_data_for_departmental_template,
)

# simulating -- a testing aid, not part of running a module. It writes marks
# into real feedback sheets and grader workbooks so the steps after marking
# can be run without anyone marking anything.
from .simulating import (
    SimulatedMarking,
    draw_marks,
    feedback_sheets,
    feedback_sheets_in,
    grader_workbooks,
    simulate_marking,
    simulate_marking_in,
)

# collating and allocating -- the assembly layer, above the packages they
# reach into
from .collating import collate_module_marks
from .allocating import (
    GraderAllocation,
    GroupMembership,
    allocate_graders,
    build_group_membership,
)

# the student information system upload
from .si_upload import (
    SiUpload,
    read_si_file,
    student_id_from_key,
    write_si_marks,
)

# moderation
from .moderation import (
    Pack,
    Sample,
    build_moderation_pack,
    flag_borderline,
    next_grade_up,
    read_moderation_manifest,
    sample_for_moderation,
)

# file operations
from .file_operations.distribute_feedback_sheets import distribute_feedback_sheets
from .file_operations.distribute_feedback_sheets import distribute_feedback_sheets_groups
from .file_operations.alphabetise_folders import alphabetise_folders
from .file_operations.save_distributed_graders import (
    Allocation,
    save_distributed_graders,
)
from .file_operations.save_grader_sheets import save_grader_sheets
from .file_operations.extract_studentid_grade import extract_studentid_grade
from .file_operations.catch_grades import catch_grades
from .file_operations.brightspace_name_folders import brightspace_name_folders
from .file_operations.resolve_multiple_subs import (
    KEEP_CHOICES,
    resolve_multiple_subs,
)
from .reconciling import Reconciliation, reconcile_marks
from .file_operations.scan_multiple_submissions import make_sub_date, scan_multiple_subs
from .file_operations.departmental_layout import DepartmentalLayout
from .file_operations.build_departmental_sheet import build_departmental_sheet
from .file_operations.write_departmental_sheet import (
    DepartmentalWrite,
    write_departmental_sheet,
)

__all__ = [
    "Assessment",
    "AssessmentStatus",
    "AssessmentType",
    "GroupSource",
    "Module",
    "ModuleFile",
    "ModulePaths",
    "Person",
    "init_module",
    "load_module",
    "load_graders",
    "distribute_feedback_sheets",
    "distribute_feedback_sheets_groups",
    "assign_graders_individual",
    "assign_graders_groups",
    "import_brightspace_classlist",
    "alphabetise_folders",
    "Allocation",
    "Collation",
    "save_collated_grades",
    "save_distributed_graders",
    "save_grader_sheets",
    "ingest_completed_graderfiles",
    "collect_quiz_marks",
    "read_quiz",
    "quiz_name",
    "DuplicateAttemptError",
    "collect_group_membership",
    "attach_group_membership",
    "AmbiguousGroupError",
    "ConflictingGroupsError",
    "MissingGroupError",
    "group_key",
    "resolve_group_column",
    "extract_studentid_grade",
    "catch_grades",
    "excel_round",
    "excel_round_series",
    "make_letter_grade",
    "calculate_weighted_score",
    "calculate_total_module_score",
    "sort_order_columns",
    "check_for_weighted_columns",
    "prepare_data_for_departmental_template",
    "collate_module_marks",
    "simulate_marking",
    "simulate_marking_in",
    "feedback_sheets_in",
    "grader_workbooks",
    "draw_marks",
    "feedback_sheets",
    "SimulatedMarking",
    "Pack",
    "Sample",
    "build_moderation_pack",
    "flag_borderline",
    "next_grade_up",
    "read_moderation_manifest",
    "sample_for_moderation",
    "SiUpload",
    "read_si_file",
    "student_id_from_key",
    "write_si_marks",
    "allocate_graders",
    "build_group_membership",
    "GraderAllocation",
    "GroupMembership",
    "brightspace_name_folders",
    "KEEP_CHOICES",
    "resolve_multiple_subs",
    "Reconciliation",
    "reconcile_marks",
    "make_sub_date",
    "scan_multiple_subs",
    "find_unsubmitted",
    "DepartmentalLayout",
    "build_departmental_sheet",
    "DepartmentalWrite",
    "write_departmental_sheet",
]
