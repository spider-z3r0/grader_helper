#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""catch_grades must not override the platform-aware default."""

import importlib

mod = importlib.import_module("grader_helper.file_operations.catch_grades")


def test_catch_grades_discovers_feedback_sheets(monkeypatch, feedback_sheet_tree):
    """Sanity check on discovery, so the delegation test means something."""
    seen = []

    def fake_extract(path, cell, **kwargs):
        seen.append(path)
        return (path.stem.split(" ")[-1], 61)

    monkeypatch.setattr(mod, "extract_studentid_grade", fake_extract)

    df = mod.catch_grades(feedback_sheet_tree, "D30")

    assert len(seen) == 1
    assert list(df.columns) == ["Student ID", "grade"]
    assert df.iloc[0].tolist() == ["12345678", 61]


def test_catch_grades_does_not_override_fallback_default(
    monkeypatch, feedback_sheet_tree
):
    """The caller must defer to the function's own default.

    Hardcoding ``allow_xlwings_fallback=True`` here is what made the
    windows-lock platform gate a no-op: whatever the default computed,
    this call site overrode it.
    """
    captured = {}

    def fake_extract(path, cell, **kwargs):
        captured.update(kwargs)
        return ("12345678", 61)

    monkeypatch.setattr(mod, "extract_studentid_grade", fake_extract)

    mod.catch_grades(feedback_sheet_tree, "D30")

    assert "allow_xlwings_fallback" not in captured, (
        "catch_grades overrode the platform-aware default with "
        f"allow_xlwings_fallback={captured.get('allow_xlwings_fallback')!r}"
    )
