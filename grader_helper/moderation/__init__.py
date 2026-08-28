#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Choosing whose work gets a second opinion, and assembling it for them.

Three pieces, in the order they run:

``flag_borderline``
    who is within a point of the next grade up. Useful on its own, and the
    basis of the approach the department is discussing adopting instead of a
    per-band sample.
``sample_for_moderation``
    the draw -- *n* per band, plus anyone requested, plus the borderline
    cases if asked. Returns the seed that produced it.
``build_moderation_pack``
    the folders the second marker is handed, and the manifest that says what
    is in them and why.
"""

from .borderline import (
    BORDERLINE_COLUMN,
    DEFAULT_TOLERANCE,
    NEXT_GRADE_COLUMN,
    POINTS_COLUMN,
    flag_borderline,
    next_grade_up,
)
from .pack import (
    MANIFEST_NAME,
    Pack,
    build_moderation_pack,
    read_moderation_manifest,
)
from .sample import (
    BORDERLINE,
    BORDERLINE_MODES,
    DRAWN,
    REASON_COLUMN,
    REQUESTED,
    Sample,
    sample_for_moderation,
)

__all__ = [
    "BORDERLINE",
    "BORDERLINE_COLUMN",
    "BORDERLINE_MODES",
    "DEFAULT_TOLERANCE",
    "DRAWN",
    "MANIFEST_NAME",
    "NEXT_GRADE_COLUMN",
    "POINTS_COLUMN",
    "Pack",
    "REASON_COLUMN",
    "REQUESTED",
    "Sample",
    "build_moderation_pack",
    "flag_borderline",
    "next_grade_up",
    "read_moderation_manifest",
    "sample_for_moderation",
]
