#!/usr/bin/env python

from grader_helper.helpers import path_catcher
from grader_helper.dependencies import pl


def test_path_cather_xl_exists(existing_xlsx_path_str):
    tp = path_catcher(str(existing_xlsx_path_str))
    assert isinstance(tp, pl.Path)
