#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Domain models for a taught module and its assessment."""

from .assessment import (
    COLLECTED_TYPES,
    Assessment,
    AssessmentStatus,
    AssessmentType,
)
from .module import SCHEMA_VERSION, WEIGHT_TOLERANCE, Module, ModulePaths
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
    "Module",
    "ModuleFile",
    "ModuleFolder",
    "ModulePaths",
    "MODULE_FILENAME",
    "init_module",
    "inspect_module_folder",
    "load_module",
    "Person",
    "SCHEMA_VERSION",
    "STARTER_ASSESSMENTS",
    "WEIGHT_TOLERANCE",
    "as_person",
]
