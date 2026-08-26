#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Platform handling: COM initialisation is the only OS-conditional piece.

Supported targets are Windows (first-class) and macOS (second). Both have
Excel, and xlwings drives Excel on both -- via COM on Windows and
AppleScript on macOS. Only ``pythoncom`` is Windows-only.

So the conditional is *whether to initialise COM*, not whether Excel is
reachable and not whether to attempt the fallback at all. Gating the
fallback on "am I on Windows?" would disable working functionality on
macOS, which is what the windows-lock branch did.

These tests mock Excel out entirely, so they carry no ``excel`` marker.
"""

import importlib
import inspect
from unittest.mock import MagicMock

import pytest

# NB: the package __init__ re-exports the *function* under the same name as
# the module, so `from ... import extract_studentid_grade` yields the
# function. Go through importlib to get the module itself.
mod = importlib.import_module(
    "grader_helper.file_operations.extract_studentid_grade"
)


@pytest.fixture
def fake_excel(monkeypatch):
    """Replace xlwings and pythoncom with mocks, returning both."""
    fake_com = MagicMock(name="pythoncom")
    fake_xw = MagicMock(name="xlwings")
    fake_xw.App.return_value.books.open.return_value.sheets.__getitem__.return_value.__getitem__.return_value.value = 72
    monkeypatch.setattr(mod, "pythoncom", fake_com)
    monkeypatch.setattr(mod, "xw", fake_xw)
    return fake_com, fake_xw


def test_com_is_initialised_when_needed(monkeypatch, fake_excel, tmp_path):
    """On Windows, COM must be initialised before driving Excel."""
    fake_com, fake_xw = fake_excel
    monkeypatch.setattr(mod, "NEEDS_COM_INIT", True, raising=False)

    mod._read_xlwings_value(tmp_path / "sheet.xlsx", "D30")

    fake_com.CoInitialize.assert_called_once()
    fake_xw.App.assert_called_once()


def test_com_is_not_initialised_when_not_needed(monkeypatch, fake_excel, tmp_path):
    """On macOS, COM must be skipped -- but Excel must still be driven.

    This is the crux. The failure being guarded against is calling
    ``pythoncom.CoInitialize()`` when pythoncom is ``None``, which raises
    AttributeError, gets swallowed by the broad handler in
    ``extract_studentid_grade``, and silently returns None for every sheet.
    """
    fake_com, fake_xw = fake_excel
    monkeypatch.setattr(mod, "NEEDS_COM_INIT", False, raising=False)

    result = mod._read_xlwings_value(tmp_path / "sheet.xlsx", "D30")

    fake_com.CoInitialize.assert_not_called()
    fake_com.CoUninitialize.assert_not_called()
    fake_xw.App.assert_called_once(), "xlwings must still run on macOS"
    assert result == 72


def test_xlwings_helper_returns_none_when_excel_unavailable(monkeypatch, tmp_path):
    """With no xlwings at all, fail explicitly rather than by AttributeError."""
    monkeypatch.setattr(mod, "xw", None)
    monkeypatch.setattr(mod, "pythoncom", None)

    assert mod._read_xlwings_value(tmp_path / "sheet.xlsx", "D30") is None


def test_fallback_default_is_true_on_every_platform():
    """``allow_xlwings_fallback`` is a user switch, not a platform gate.

    windows-lock replaced the default value ``= True`` with a type
    annotation ``: ON_WINDOWS``, which makes the keyword-only parameter
    *required* -- every caller that omits it raises TypeError.
    """
    param = inspect.signature(mod.extract_studentid_grade).parameters[
        "allow_xlwings_fallback"
    ]
    assert param.default is not inspect.Parameter.empty, (
        "allow_xlwings_fallback has no default -- the default value was "
        "replaced by a type annotation, making it a required argument"
    )
    assert param.default is True
