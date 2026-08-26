#!/usr/bin/env python
# -*- coding: utf-8 -*-


from typing import Mapping, Sequence

from ..dependencies import pd
from ..ingesting.import_brightspace_classlist import find_group_column
from .assign_graders_individual import assign_graders_individual


def main():
    # Example usage
    df = pd.DataFrame(
        {
            "Student ID": list("123456"),
            "Group": ["Team 1"] * 3 + ["Team 2"] * 3,
        }
    )

    graders = ["Grader1", "Grader2", "Grader3"]

    print(assign_graders_groups(df, graders, seed=1))


def assign_graders_groups(
    d: pd.DataFrame,
    l: Sequence[str],
    assigned_grader_col: str = "grader",
    group_col: str | None = None,
    *,
    weights: Mapping[str, float] | None = None,
    overwrite: bool = False,
    seed: int | None = None,
) -> pd.DataFrame:
    """
    Assign one grader to each group, so a group's work is marked by one person.

    The group is read from a **column**, not from a MultiIndex. Nothing in
    the package ever produced a MultiIndex -- ``import_brightspace_classlist(
    group=True)`` returns a flat frame with a 'Group' column -- so the old
    MultiIndex form silently degraded to per-student allocation and split
    teams across graders. Polars has no index either, so a column is the
    durable choice.

    Allocation is delegated to :func:`assign_graders_individual` over the
    *unique groups*, which gives an even split of groups across graders
    (rather than sampling with replacement, which could leave one grader
    with everything and another with nothing), plus optional weights and a
    seed for reproducibility.

    Parameters
    ----------
    d : pandas DataFrame
        One row per student, with a column naming each student's group.
    l : sequence of str
        Grader IDs.
    assigned_grader_col : str, optional
        Column to write the allocation into (default 'grader').
    group_col : str, optional
        The column holding the group. Found automatically when not given --
        see ``find_group_column``.
    weights : mapping, optional
        Optional {grader: weight}, applied to the share of *groups*.
    overwrite : bool, optional
        If False (default) and ``assigned_grader_col`` already exists, the
        frame is returned unchanged, so a re-run cannot reshuffle an
        allocation graders have already started working to.
    seed : int, optional
        Seed for reproducible allocation.

    Returns
    -------
    pandas DataFrame
        A copy of ``d`` with the grader column filled.

    Raises
    ------
    TypeError
        If ``d`` is not a DataFrame.
    ValueError
        If ``l`` is empty, or no group column can be found.
    """
    if not isinstance(d, pd.DataFrame):
        raise TypeError("Argument 'd' must be a pandas DataFrame.")
    if len(list(l)) == 0:
        raise ValueError("Argument 'l' must be a non-empty sequence of grader IDs.")

    if assigned_grader_col in d.columns and not overwrite:
        return d.copy()

    # Raises ValueError naming the columns present if there is no group column.
    col = find_group_column(d.columns, group_col)

    # Allocate over the distinct groups, then map back onto the students.
    groups = pd.DataFrame({col: sorted(d[col].dropna().unique().tolist())})
    allocated = assign_graders_individual(
        groups,
        list(l),
        weights=weights,
        column=assigned_grader_col,
        overwrite=True,
        seed=seed,
    )
    group_grader_map = dict(
        zip(allocated[col], allocated[assigned_grader_col])
    )

    out = d.copy()
    out[assigned_grader_col] = out[col].map(group_grader_map)
    return out


if __name__ == "__main__":
    main()
