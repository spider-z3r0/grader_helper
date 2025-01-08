#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" This is the init file for the calculations module."""

from matplotlib.pylab import f
from .make_letter_grade import make_letter_grade
from .calculate_weighted_score import calculate_weighted_score
from .calculate_total_module_score import calculate_total_module_score
from .sort_order_columns import sort_order_columns
from .check_for_weighted_columns import check_for_weighted_columns
from .prepare_data_for_departmental_template import (
    prepare_data_for_departmental_template,
)


__all__ = [
    "make_letter_grade",
    "calculate_weighted_score",
    "calculate_total_module_score",
    "sort_order_columns",
    "check_for_weighted_columns",
    "prepare_data_for_departmental_template",
]
