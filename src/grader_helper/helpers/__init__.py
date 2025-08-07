#!/usr/bin/env python
"""Helper utilities for :mod:`grader_helper`.

Currently this module exposes :func:`guess_model_type`, which infers the model
class from a YAML mapping.
"""

from .guess_model_type import guess_model_type


__all__ = [
    "guess_model_type",
]
