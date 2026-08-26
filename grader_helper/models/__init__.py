#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Domain models for a taught module and its assessment."""

from .assessment import Assessment, AssessmentStatus, AssessmentType
from .module import SCHEMA_VERSION, Module, ModulePaths
from .module_file import (
    MODULE_FILENAME,
    ModuleFile,
    init_module,
    load_module,
)
from .people import Person, as_person

__all__ = [
    "Assessment",
    "AssessmentStatus",
    "AssessmentType",
    "Module",
    "ModuleFile",
    "ModulePaths",
    "MODULE_FILENAME",
    "init_module",
    "load_module",
    "Person",
    "SCHEMA_VERSION",
    "as_person",
]
