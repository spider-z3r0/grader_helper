#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""What counts as a step having been done.

Status is kept two ways. Where a step leaves evidence on disk the code sets
the flag itself; where only a person can know, somebody presses a button. This
module holds the first half: one rule per result type, saying which flag that
type can justify and what it has to show to justify it.

**"It did not raise" is not evidence.** Three functions in this package
complete perfectly happily having done nothing much:

* ``distribute_feedback_sheets`` returns a ``Distribution`` that can be all
  ``unmatched`` -- forty folders, no ids recognised, no exception.
* ``collate_module_marks`` *warns* for an assessment it found no marks for and
  gives it an empty column.
* ``ingest_completed_graderfiles(require_all=False)`` warns rather than
  raises.

A green tick against a step that did nothing is the same failure as a total
missing a component: it looks exactly like the real thing. So each rule reads
the *return value*.

The rules live here rather than on :class:`~grader_helper.models.ModuleFile`
because they have to know about `file_operations` and `moderation`, and those
import `models`. Keeping them one layer up is what stops that being a cycle.

House convention: ``pl`` is pathlib, ``pr`` is polars.

    >>> import pathlib as pl
    >>> import polars as pr
"""

from typing import Callable, NamedTuple

from .file_operations.distribute_feedback_sheets import Distribution
from .file_operations.write_departmental_sheet import DepartmentalWrite
from .moderation.pack import Pack
from .si_upload import SiUpload


class Evidence(NamedTuple):
    """The rule for one kind of result."""

    #: The status flag this result can justify.
    flag: str
    #: Whether the result shows the step actually happened.
    satisfied: Callable[[object], bool]
    #: "assessment" or "module" -- which status object the flag lives on.
    scope: str


#: One rule per result type. Adding a step means adding a line here and
#: nothing else.
RULES: dict[type, Evidence] = {
    # Sheets were distributed if any were copied *and* nothing was left
    # unrecognised. A run that matched forty folders and missed one has not
    # finished, and the tick would hide the one.
    Distribution: Evidence(
        flag="sheets_distributed",
        satisfied=lambda r: bool(r.copied or r.skipped) and not r.unmatched,
        scope="assessment",
    ),
    # The sheet was written if rows went into it.
    DepartmentalWrite: Evidence(
        flag="departmental_sheet_written",
        satisfied=lambda r: r.written > 0,
        scope="module",
    ),
    # A pack was built if its manifest exists. Deliberately not "files were
    # copied": a pack whose sampled students all submitted nothing is still a
    # pack that was properly built, and the manifest is what says so.
    Pack: Evidence(
        flag="moderation_pack_built",
        satisfied=lambda r: r.manifest.is_file(),
        scope="module",
    ),
    # The upload was written if marks went in and SI's roll was fully
    # accounted for. A student with a mark whom SI has no row for means the
    # two records disagree, which is not a finished step.
    SiUpload: Evidence(
        flag="si_file_written",
        satisfied=lambda r: r.filled > 0 and not r.not_enrolled,
        scope="module",
    ),
}


def evidence_for(result) -> tuple[str, bool, str]:
    """
    Read the status a step's result justifies.

    Args:
    result: What a step returned.

    Returns:
    tuple[str, bool, str]: ``(flag, satisfied, scope)``.

    Raises:
    TypeError: If no rule covers `result`. Better than guessing: a result
        nothing knows how to read is a step whose status would otherwise be
        set on no evidence at all.

    Example:
        >>> evidence_for(distribution)
        ('sheets_distributed', True, 'assessment')
    """
    rule = RULES.get(type(result))
    if rule is None:
        raise TypeError(
            f"Nothing knows what {type(result).__name__} says about a step's "
            f"status. Known results: "
            f"{sorted(cls.__name__ for cls in RULES)}.\n"
            "Add a rule to grader_helper.recording.RULES, or set the flag by "
            "hand with set_status() / set_module_status() if a person is the "
            "one who knows."
        )
    return rule.flag, bool(rule.satisfied(result)), rule.scope
