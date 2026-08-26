#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This script is just housing the dependencies for the other scripts in the src folder.
It is not intended to be run as a script.

Supported platforms are Windows (first-class) and macOS (second). Both have
Excel, and xlwings drives Excel on both -- via COM on Windows and via
AppleScript on macOS. The only genuinely Windows-only piece is ``pythoncom``,
so COM initialisation is the single OS conditional in the codebase. Gating
xlwings itself on Windows would disable working functionality on macOS.

``xw`` and ``pythoncom`` are always bound, to ``None`` when unavailable, so
importing this module never fails on a platform that lacks them.
"""

import sys

ON_WINDOWS = sys.platform == "win32"
ON_MACOS = sys.platform == "darwin"

#: Whether COM must be initialised before driving Excel. Windows only.
NEEDS_COM_INIT = ON_WINDOWS

import logging as log
import pandas as pd
import numpy as np
import pathlib as pl
from shutil import copy2, copytree
import re
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
import os

# xlwings works on both supported platforms, so it is not gated on Windows.
try:
    import xlwings as xw  # type: ignore[import]
except ImportError:
    xw = None  # type: ignore[assignment]

# pythoncom is Windows-only; it ships with pywin32.
if NEEDS_COM_INIT:
    try:
        import pythoncom  # type: ignore[import]
    except ImportError:
        pythoncom = None  # type: ignore[assignment]
else:
    pythoncom = None  # type: ignore[assignment]
