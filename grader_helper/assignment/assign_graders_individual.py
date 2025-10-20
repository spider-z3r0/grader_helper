#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
from typing import Mapping, Sequence


def main():
    # Example usage
    data = {"student_id": [1, 2, 3, 4, 5, 6, 7], "name": ["A", "B", "C", "D", "E", "F", "G"]}
    df = pd.DataFrame(data)

    graders = ["Grader1", "Grader2", "Grader3"]  # read from file in your real use-case

    updated_df = assign_graders_individual(df, graders, overwrite=True)
    print(updated_df)



def assign_graders_individual(
    df: pd.DataFrame,
    graders: Sequence[str],
    *,
    weights: Mapping[str, float] | None = None,
    column: str = "grader",
    overwrite: bool = False,
    seed: int | None = None,
) -> pd.DataFrame:
    """
    Even (or weighted-even) random assignment of graders to rows in `df`.

    - Unweighted: each grader gets either ⌊N/k⌋ or ⌈N/k⌉.
    - Weighted: uses Hamilton's largest-remainder method to convert weights to integer quotas summing to N.
    - Reproducible with `seed`. No interactive prompts.

    Args:
        df: DataFrame of students (one row per student).
        graders: list/sequence of grader names (must be unique).
        weights: optional mapping {grader_name: weight >= 0}. Missing or all-zero -> uniform.
        column: name of the output column to write (default "grader").
        overwrite: if False and column exists, return a copy unchanged.
        seed: optional RNG seed for reproducibility.

    Returns:
        A new DataFrame with `column` filled.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    if column in df.columns and not overwrite:
        return df.copy()

    if not isinstance(graders, list):
        raise TypeError("graders must be a list of strings")

    graders = list(graders)
    if len(graders) == 0:
        raise ValueError("graders must be a non-empty sequence")
    if len(set(graders)) != len(graders):
        raise ValueError("grader names must be unique")

    n = len(df)
    if n == 0:
        out = df.copy()
        out[column] = pd.Series([], dtype="object")
        return out

    rng = np.random.default_rng(seed)

    # --- determine quotas (counts per grader) ---
    k = len(graders)
    print(graders)

    if weights is None:
        # Uniform quotas via divmod (exactly even)
        q, r = divmod(n, k)
        # Randomize which graders get the +1 using a permutation
        order = rng.permutation(k)
        counts = np.full(k, q, dtype=int)
        counts[order[:r]] += 1
    else:
        # Build nonnegative weights aligned to graders
        w = np.array([max(0.0, float(weights.get(g, 0.0))) for g in graders], dtype=float)
        if not np.isfinite(w).all():
            raise ValueError("weights must be finite numbers")
        if w.sum() <= 0:
            # fall back to uniform if all zero/missing
            w = np.ones(k, dtype=float)

        p = w / w.sum()
        exp = p * n
        base = np.floor(exp).astype(int)
        remainder = exp - base
        r = int(n - base.sum())
        # Break ties on remainder randomly to keep it fair
        tiebreak = rng.random(k)
        order = np.lexsort((-tiebreak, -remainder))  # sort by remainder desc, then random desc
        counts = base.copy()
        if r > 0:
            counts[order[:r]] += 1

    assert counts.sum() == n, "internal error: quotas must sum to N"

    # --- build pool and assign ---
    pool = np.repeat(np.array(graders, dtype=object), counts)
    rng.shuffle(pool)  # random pairing student<->grader

    out = df.copy()
    out[column] = pool
    return out
if __name__ == "__main__":
    main()
