#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Rounding that matches Excel, because the grade sheet is the source of truth.

Python's built-in ``round``, and numpy's and pandas' ``.round()``, use
round-half-to-even ("banker's rounding"): ``round(64.5) == 64`` and
``round(65.5) == 66``. Excel's ``ROUND`` rounds half away from zero, so
``ROUND(64.5, 0)`` is ``65``.

That divergence is not cosmetic. In the 2026 departmental sample data, two
of twenty rows land on an exact half:

    row 43: 60.5  ->  Python 60, Excel 61
    row 35: 64.5  ->  Python 64 (B3), Excel 65 (B2)

The second crosses a band boundary, so a student on an exact half mark
would be given a different letter grade by this package than by the sheet
the department reads. Anywhere a total is rounded for the grade sheet, use
``excel_round``.
"""

from decimal import ROUND_HALF_UP, Decimal

import pandas as pd


def excel_round(value, ndigits: int = 0):
    """Round half away from zero, as Excel's ROUND does.

    Returns ``value`` unchanged if it is null, so a missing mark stays
    missing rather than becoming zero.

    >>> excel_round(64.5)
    65.0
    >>> excel_round(65.5)
    66.0
    >>> round(64.5)          # Python, for contrast
    64
    >>> excel_round(-2.5)
    -3.0
    """
    if value is None or pd.isna(value):
        return value

    exponent = Decimal(1).scaleb(-ndigits)
    # str() gives the shortest representation that round-trips, so a float
    # that is exactly 64.5 quantizes as 64.5 rather than 64.4999...
    rounded = Decimal(str(value)).quantize(exponent, rounding=ROUND_HALF_UP)
    return float(rounded)


def excel_round_series(series: pd.Series, ndigits: int = 0) -> pd.Series:
    """Apply :func:`excel_round` across a Series.

    Use in place of ``Series.round()``, which rounds half to even.
    """
    return series.map(lambda v: excel_round(v, ndigits))
