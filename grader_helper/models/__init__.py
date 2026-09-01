#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Domain models for a taught module and its assessment."""

from .assessment import (
    COLLECTED_TYPES,
    GROUP_MEMBERSHIP_FILENAME,
    Assessment,
    AssessmentStatus,
    AssessmentType,
    GroupSource,
    tidy_number,
)
from .module import (
    SCHEMA_VERSION,
    WEIGHT_TOLERANCE,
    Module,
    ModulePaths,
    ModuleStatus,
)
from .module_file import (
    MODULE_FILENAME,
    STARTER_ASSESSMENTS,
    ModuleFile,
    init_module,
    load_module,
)
from .module_folder import FolderState, ModuleFolder, inspect_module_folder
from .people import Person, as_person

__all__ = [
    "Assessment",
    "AssessmentStatus",
    "AssessmentType",
    "COLLECTED_TYPES",
    "FolderState",
    "GroupSource",
    "GROUP_MEMBERSHIP_FILENAME",
    "Module",
    "ModuleFile",
    "ModuleFolder",
    "ModulePaths",
    "ModuleStatus",
    "MODULE_FILENAME",
    "init_module",
    "inspect_module_folder",
    "load_module",
    "Person",
    "SCHEMA_VERSION",
    "STARTER_ASSESSMENTS",
    "WEIGHT_TOLERANCE",
    "as_person",
    "tidy_number",
]
