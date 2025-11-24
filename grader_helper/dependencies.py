#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This script is just housing the dependencies for the other scripts in the src folder.
It is not intended to be run as a script.

"""
import sys
ON_WINDOWS = sys.platform == 'Win32'

import logging as log
import pandas as pd
import numpy as np
import pathlib as pl
from shutil import copy2, copytree
import re
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
import os

ON_WINDOWS = sys.platform == "win32"

# Always define these names, even if they're None
if ON_WINDOWS:
    try:
        import pythoncom  # type: ignore[import]
    except ImportError:
        pythoncom = None  # type: ignore[assignment]

    try:
        import xlwings as xw  # type: ignore[import]
    except ImportError:
        xw = None  # type: ignore[assignment]
else:
    pythoncom = None  # type: ignore[assignment]
    xw = None    
