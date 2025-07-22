#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" This is the top level init file for the src package. It imports all the sub-modules and makes them available to the package. """

# ingesting
from .src.ingesting.load_graders import load_graders
from .src.ingesting.import_brightspace_classlist import (
    import_brightspace_classlist,
)
from .src.ingesting.ingest_completed_graderfiles import (
    ingest_completed_graderfiles,
)

# assignment
from .src.assignment.assign_graders_individual import (
    assign_graders_individual,
)
from .src.assignment.assign_graders_groups import assign_graders_groups

# dataframe operations
from .src.dataframe_operations.make_letter_grade import make_letter_grade
from .src.dataframe_operations.calculate_weighted_score import (
    calculate_weighted_score,
)
from .src.dataframe_operations.calculate_total_module_score import (
    calculate_total_module_score,
)
from .src.dataframe_operations.sort_order_columns import sort_order_columns
from .src.dataframe_operations.check_for_weighted_columns import (
    check_for_weighted_columns,
)
from .src.dataframe_operations.prepare_data_for_departmental_template import (
    prepare_data_for_departmental_template,
)

# file operations
from .src.file_operations.distribute_feedback_sheets import (
    distribute_feedback_sheets,
)
from .src.file_operations.alphabetise_folders import alphabetise_folders
from .src.file_operations.save_distributed_graders import (
    save_distributed_graders,
)
from .src.file_operations.save_grader_sheets import save_grader_sheets
from .src.file_operations.extract_studentid_grade import (
    extract_studentid_grade,
)
from .src.file_operations.catch_grades import catch_grades
from .src.brightspace_name_folders import brightspace_name_folders


__all__ = [
    "load_graders",
    "distribute_feedback_sheets",
    "assign_graders_individual",
    "assign_graders_groups",
    "import_brightspace_classlist",
    "alphabetise_folders",
    "save_distributed_graders",
    "save_grader_sheets",
    "ingest_completed_graderfiles",
    "extract_studentid_grade",
    "catch_grades",
    "make_letter_grade",
    "calculate_weighted_score",
    "calculate_total_module_score",
    "sort_order_columns",
    "check_for_weighted_columns",
    "prepare_data_for_departmental_template",
    "brightspace_name_folders",
]
