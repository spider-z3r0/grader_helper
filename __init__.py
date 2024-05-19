#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" This is the top-level init file. Honestly, I'm not 100% sure if I need it, but it's here."""


# dependencies
from .grader_helper import dependencies

# ingesting
from .grader_helper.ingesting.load_graders import load_graders
from .grader_helper.ingesting.import_brightspace_classlist import (
    import_brightspace_classlist,
)


# calculations
from .grader_helper.calculations.make_letter_grade import make_letter_grade

# grader assignment
from .grader_helper.assignment.assign_graders_individual import (
    assign_graders_individual,
)
from .grader_helper.assignment.assign_graders_groups import assign_graders_groups

# file saving
from .grader_helper.file_operations.distribute_feedback_sheets import (
    distribute_feedback_sheets,
)
from .grader_helper.file_operations.rename_folders import rename_folders
from .grader_helper.file_operations.save_distributed_graders import (
    save_distributed_graders,
)
from .grader_helper.file_operations.save_grader_sheets import save_grader_sheets
from .grader_helper.file_operations.extract_studentid_grade import extract_studentid_grade
from .grader_helper.file_operations.catch_grades import catch_grades

__all__ = [
    "distribute_feedback_sheets",
    "distribute_graders_individual",
    "distribute_graders_groups",
    "import_brightspace_classlist",
    "load_graders",
    "rename_folders",
    "save_distributed_graders",
    "save_grader_sheets",
    "make_letter_grade",
    "extract_studentid_grade",
    "catch_grades",
]
