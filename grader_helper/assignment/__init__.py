#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""This is the init file for the functions that hanndle assigning students to graders."""

from .assign_graders_individual import assign_graders_individual
from .assign_graders_groups import assign_graders_groups


__all__ = [
    "assign_graders_individual",
    "assign_graders_groups",
]
