#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Allocate an assessment's marking, and write the files that record it.

The pieces have existed for a while -- ``assign_graders_individual``,
``assign_graders_groups``, ``save_distributed_graders``,
``save_grader_sheets`` -- but nothing joined them to an ``Assessment``, so
every caller had to know which allocator its assessment wanted, where the
two output files go, and what shape a grader's workbook should be. This is
that step: hand it an assessment and a class list and it does the right
thing for the kind of assessment it is.

It lives at the top level rather than inside ``assignment`` for the same
reason ``collating`` does: it is an assembly layer, reaching into
``ingesting``, ``assignment`` and ``file_operations`` at once, and those
packages deliberately do not reach sideways into each other.

House convention::

    import pathlib as pl        # pl is pathlib
    import polars as pr         # pr is polars

The three kinds
---------------

**Individual.** One grader per student. The grader's workbook has one row
per student, and that is the whole of it.

**Group, made in Brightspace** (``group_source = "brightspace"``). The
groups arrive in the class list. Brightspace gives the team one folder, one
feedback sheet and one mark, so **the grader's workbook has one row per
group** -- asking a grader to write the same mark against four students is
asking for three chances to mistype it.

**Group, made by the module leader** (``group_source = "module_leader"``).
The groups are collected from the leader's own sheets first. Brightspace
knows nothing about them, so the download is the ordinary individual shape:
one folder and one feedback sheet per student, and marks that may
legitimately differ within a group. **The grader's workbook therefore has
one row per student**, sorted by group -- the group decides *who marks it*,
not *what the mark is*.

``distributed.xlsx`` is one row per student in all three cases. It is the
file you open when a student asks who marked their work, and that question
has an answer whoever the work was submitted by.
"""

import pathlib as pl
from typing import Mapping, NamedTuple, Sequence

import pandas as pd

from .assignment.assign_graders_groups import assign_graders_groups
from .assignment.assign_graders_individual import assign_graders_individual
from .file_operations.save_distributed_graders import (
    Allocation,
    save_distributed_graders,
)
from .file_operations.save_grader_sheets import GRADER_COLUMN, save_grader_sheets
from .ingesting.collect_group_membership import (
    AmbiguousGroupError,
    attach_group_membership,
    collect_group_membership,
)
from .ingesting.import_brightspace_classlist import (
    group_key,
    resolve_group_column,
)
from .models import Assessment, GroupSource

#: The column a grader writes their mark into. ``collating.MARK_COLUMN`` reads
#: it back out again; they are the two ends of one contract.
MARK_COLUMN = "Mark"


class GroupMembership(NamedTuple):
    """A collected student-id-to-group table, and where it was written."""

    frame: pd.DataFrame
    path: pl.Path | None

    def __str__(self) -> str:
        return (
            f"{len(self.frame)} students in "
            f"{self.frame['Group'].nunique()} groups"
        )


class GraderAllocation(NamedTuple):
    """What an allocation run produced.

    Returned rather than printed, so a notebook or the dashboard can show it
    and a test can assert on it. It carries the ``Allocation`` that
    ``save_distributed_graders`` returned rather than a bare path, so
    ``ModuleFile.record`` can read the same evidence off either -- see
    :mod:`grader_helper.recording`.
    """

    #: One row per student, with the grader column filled. What went into
    #: ``distributed.xlsx``.
    frame: pd.DataFrame
    #: What went into the grader workbooks -- per student, except for a
    #: Brightspace-managed group assessment, where it is per group.
    per_grader: pd.DataFrame
    #: ``distributed.xlsx`` and how many students it allocates.
    allocation: Allocation
    #: Each grader mapped to their workbook in ``grading_output/``.
    workbooks: dict[str, pl.Path]
    #: The collected group membership, for a leader-managed group assessment.
    #: ``None`` for the other two kinds, which have nothing to collect.
    membership: pl.Path | None

    @property
    def master(self) -> pl.Path:
        """``distributed.xlsx``, at the assessment root."""
        return self.allocation.path

    def __str__(self) -> str:
        rows = "group" if "Student ID" not in self.per_grader.columns else "student"
        return (
            f"{self.allocation.students} students across "
            f"{len(self.workbooks)} graders, one row per {rows} in each workbook"
        )


def build_group_membership(
    assessment: Assessment,
    *,
    save: bool = True,
    id_column: str | None = None,
    group_column: "str | Sequence[str] | None" = None,
) -> GroupMembership:
    """
    Collect a leader-managed assessment's group sheets into one table.

    Worth running on its own before allocating anything: it is the step where
    a mistyped id or a student left off every sheet shows up, and both are
    much cheaper to fix before graders have workbooks.

    Parameters
    ----------
    assessment
        A bound assessment with ``group_source = "module_leader"``.
    save : bool
        Also write ``group_membership.csv`` into ``grading_output/``.
    id_column, group_column : str or sequence of str, optional
        Passed through to :func:`collect_group_membership` for sheets whose
        columns are named unusually. ``group_column`` defaults to the
        assessment's own, so a module that has answered the question in
        ``module.toml`` never has to answer it again here.

    Returns
    -------
    GroupMembership
        The frame, and the file written (``None`` when ``save`` is False).

    Raises
    ------
    ValueError
        If the assessment does not manage its own groups -- a
        Brightspace-managed one reads its membership from the class list,
        and an individual one has none.

    Notes
    -----
    The file is **derived**, and rewritten every time this runs. The group
    sheets are the record; correct those, not the collected file.
    """
    if assessment.group_source is not GroupSource.MODULE_LEADER:
        source = assessment.group_source.value if assessment.group_source else None
        raise ValueError(
            f"Assessment {assessment.id!r} does not keep its own group sheets "
            f"(group={assessment.group}, group_source={source!r}). Only "
            "group_source = 'module_leader' has sheets to collect; a "
            "Brightspace-managed group assessment gets its groups from the "
            "class list, via import_brightspace_classlist(group=True)."
        )

    sheets = assessment.group_sheets_path
    assert sheets is not None  # guaranteed by the check above
    frame = collect_group_membership(
        sheets,
        id_column=id_column,
        group_column=_group_column_for(assessment, group_column),
    )

    if not save:
        return GroupMembership(frame, None)

    target = assessment.group_membership_path
    assert target is not None
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False)
    return GroupMembership(frame, target)


def _group_column_for(
    assessment: Assessment, override: "str | Sequence[str] | None"
) -> "str | Sequence[str] | None":
    """Which column holds the group: this call's answer, or the module's.

    One definition, used by both the leader-managed and the Brightspace
    path. Two fallbacks would each hide the other going missing, which is
    exactly what happened when there were two.
    """
    return override if override is not None else assessment.group_column


def _graders_for(assessment: Assessment, graders: Sequence[str] | None) -> list[str]:
    """The grader ids to allocate across, from the argument or the module."""
    if graders is not None:
        found = list(graders)
        if not found:
            raise ValueError(
                "graders is empty, so there is nobody to allocate the marking "
                "to."
            )
        return found

    found = [g.initials for g in assessment.graders]
    if not found:
        raise ValueError(
            f"Assessment {assessment.id!r} lists no graders, so there is "
            "nobody to allocate the marking to. Either set graders in "
            "module.toml or pass graders= here."
        )
    return found


def allocate_graders(
    assessment: Assessment,
    class_list: pd.DataFrame,
    graders: Sequence[str] | None = None,
    *,
    weights: Mapping[str, float] | None = None,
    seed: int | None = None,
    overwrite: bool = False,
    criteria: Sequence[str] | None = (MARK_COLUMN,),
    group_column: "str | Sequence[str] | None" = None,
    grader_column: str = GRADER_COLUMN,
) -> GraderAllocation:
    """
    Allocate this assessment's marking and write the two files that record it.

    Which allocator runs, and what shape a grader's workbook comes out, are
    decided by the assessment -- see this module's docstring for the three
    kinds and why they differ.

    Parameters
    ----------
    assessment
        A bound assessment, i.e. one reached through a module loaded with
        ``load_module``. It supplies the graders, the paths and the kind.
    class_list : pandas DataFrame
        As ``import_brightspace_classlist`` returns it. **This decides the
        cohort.** A Brightspace-managed group assessment needs it imported
        with ``group=True``, so it carries the group column.
    graders : sequence of str, optional
        Grader ids, overriding ``assessment.graders``. Their initials name
        their workbooks.
    weights : mapping, optional
        ``{grader: weight}``, for an uneven split -- someone marking half
        time, say. Applied to the share of *groups* for a group assessment,
        because a group is what gets allocated.
    seed : int, optional
        For a reproducible allocation.
    overwrite : bool
        Replace ``distributed.xlsx`` and the grader workbooks if they are
        already there. Defaults to False: a workbook may already hold marks,
        and a re-allocation reshuffles work graders have started.
    criteria : sequence of str, optional
        Empty columns appended to each grader's workbook for them to fill
        in. Defaults to one ``Mark`` column, which is what
        ``collate_module_marks`` reads back.
    group_column : str or sequence of str, optional
        The column holding the group, overriding the assessment's own. A
        sequence composes one key from several columns. Only read for a
        group assessment.
    grader_column : str
        The column the allocation is written into.

    Returns
    -------
    GraderAllocation
        The frames, the files written, and the collected membership. Hand it
        to ``ModuleFile.record(result, assessment.id)`` to set
        ``graders_allocated`` from the evidence.

    Raises
    ------
    ValueError
        If the assessment has no graders, or a Brightspace-managed group
        assessment's class list has no group column.
    FileExistsError
        If a file exists and ``overwrite`` is False. ``distributed.xlsx`` is
        written first, so a refusal on the workbooks leaves it replaced --
        pass ``overwrite=True`` on a re-run, which is the normal way to
        re-allocate.

    Examples
    --------
    ::

        import pathlib as pl        # pl is pathlib

        module = load_module(pl.Path("module.toml"))
        cw1 = module.assessment("cw1")

        # Brightspace made the groups, so the class list carries them.
        cl = import_brightspace_classlist(module.classlist_path, group=True)
        allocation = allocate_graders(cw1, cl, seed=1)

    A leader-managed group assessment needs no ``group=True``: the groups
    come from the sheets in ``<folder>/groups/``, and this collects them::

        cl = import_brightspace_classlist(module.classlist_path)
        allocation = allocate_graders(module.assessment("cw2"), cl, seed=1)
        allocation.membership   # grading_output/group_membership.csv

    Notes
    -----
    **Nothing is written to ``module.toml``.** The status a run justifies is
    read off its result, not off its not having raised, so recording is a
    separate call the caller makes::

        handle.record(allocation, assessment.id)

    See :mod:`grader_helper.recording`.
    """
    if not isinstance(assessment, Assessment):
        raise ValueError(
            "assessment must be an Assessment, reached through a module "
            "loaded with load_module() -- an unbound one does not know where "
            "its own files go."
        )
    if not isinstance(class_list, pd.DataFrame):
        raise TypeError("class_list must be a pandas DataFrame.")

    grader_ids = _graders_for(assessment, graders)
    membership_path: pl.Path | None = None
    # The assessment's own answer, unless this call overrides it. Resolved
    # here for the Brightspace path; the leader-managed path hands the
    # override down and lets build_group_membership resolve it the same way.
    wanted_column = _group_column_for(assessment, group_column)

    if not assessment.group:
        allocated = assign_graders_individual(
            class_list,
            grader_ids,
            weights=weights,
            column=grader_column,
            overwrite=True,
            seed=seed,
        )
        per_grader = allocated

    else:
        if assessment.group_source is GroupSource.MODULE_LEADER:
            membership = build_group_membership(
                assessment, group_column=group_column
            )
            membership_path = membership.path
            with_groups = attach_group_membership(class_list, membership.frame)
            column = "Group"
        else:
            # Brightspace made the groups, so they are already here. Say so
            # plainly rather than letting the allocator's own message talk
            # about a frame the caller did not build.
            try:
                column = resolve_group_column(class_list, wanted_column)
            except AmbiguousGroupError:
                # Already says which columns and what to pass. Wrapping it
                # in "this class list has no group column" would be a worse
                # message about a different problem.
                raise
            except ValueError as exc:
                raise ValueError(
                    f"Assessment {assessment.id!r} has group_source = "
                    "'brightspace', so its groups come down in the class "
                    f"list -- but this class list has none. {exc} Import it "
                    "with import_brightspace_classlist(..., group=True)."
                ) from exc

            with_groups = class_list
            if not isinstance(column, str):
                # A composed key has to become a real column before anything
                # can allocate over it or sort by it.
                with_groups = class_list.copy()
                with_groups["Group"] = group_key(class_list, column)
                column = "Group"

        allocated = assign_graders_groups(
            with_groups,
            grader_ids,
            assigned_grader_col=grader_column,
            group_col=column,
            weights=weights,
            overwrite=True,
            seed=seed,
        ).sort_values([column, "Student ID"], ignore_index=True)

        if assessment.group_source is GroupSource.BRIGHTSPACE:
            # One folder, one feedback sheet, one mark per group -- so one
            # row per group. A per-student workbook here would ask the
            # grader to copy the same mark four times.
            per_grader = allocated[[column, grader_column]].drop_duplicates(
                ignore_index=True
            )
        else:
            # One feedback sheet per student, and marks that may differ
            # within a group, so the grader needs every student.
            per_grader = allocated

    written = save_distributed_graders(
        allocated, assessment.folder_path, overwrite=overwrite
    )
    workbooks = save_grader_sheets(
        per_grader,
        assessment.grading_output_path,
        grader_ids,
        criteria=criteria,
        overwrite=overwrite,
        grader_column=grader_column,
    )

    return GraderAllocation(
        allocated, per_grader, written, workbooks, membership_path
    )
