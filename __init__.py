#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Top-level shim for the grader_helper package.

The repository directory is itself named ``grader_helper``, so when the
repo's *parent* is on ``sys.path`` -- an ordinary situation for a script or
notebook sitting beside the checkout -- ``import grader_helper`` resolves to
this file rather than to ``grader_helper/grader_helper/``. This module exists
to make that resolution behave identically to the real package.

It deliberately re-exports rather than restating. The previous version
maintained its own parallel list of imports, which drifted out of sync with
the real package ``__init__``: it pointed at ``brightspace_name_folders`` on
the top level after that module had moved into ``file_operations``, and it
was missing ``distribute_feedback_sheets_groups``, ``make_sub_date`` and
``scan_multiple_subs`` entirely. A star re-export cannot drift, so the single
source of truth for the public API is ``grader_helper/__init__.py``.

This file is not shipped in the wheel -- ``[tool.hatch.build.targets.wheel]``
packages only ``grader_helper`` -- so it affects development checkouts only.
"""

from .grader_helper import *  # noqa: F401,F403
from .grader_helper import __all__ as __all__
