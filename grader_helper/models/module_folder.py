#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""What is in a folder: a module, nothing yet, or something broken.

Pointing the tool at a folder is the first thing anyone does, and there are
four answers, not two. ``ModuleFile.load`` raises ``FileNotFoundError`` for
"no module here" and a ``ValidationError`` for "a module.toml that will not
load", and a caller that wraps both in one ``except`` cannot tell them
apart -- yet they need opposite offers. An empty folder should be offered
initialisation; a folder holding a file whose weights sum to 90 must not be,
because the fix is to edit that file and the file is the module's memory.

So the decision is made here, once, and returned as data:

    import pathlib as pl
    from grader_helper.models import FolderState, inspect_module_folder

    found = inspect_module_folder(pl.Path("PS4034"))
    match found.state:
        case FolderState.LOADED:        run(found.module)
        case FolderState.UNINITIALISED: offer_init(found.folder)
        case FolderState.UNREADABLE:    show(found.error, found.file_path)
        case FolderState.MISSING:       ask_again()

Nothing here writes, and nothing here raises: a bad folder is an answer, not
an accident. Which is what lets a dashboard cell call it on every keystroke.
"""

import pathlib as pl
from dataclasses import dataclass
from enum import Enum

from .module import Module
from .module_file import MODULE_FILENAME, ModuleFile


class FolderState(str, Enum):
    """What was found. A ``str`` Enum so it renders as itself in a UI."""

    #: A module.toml that loaded. ``module`` and ``file`` are populated.
    LOADED = "loaded"

    #: A directory with no module.toml in it. The one state where offering
    #: initialisation is safe -- init_module refuses to overwrite, and it is
    #: right to.
    UNINITIALISED = "uninitialised"

    #: A module.toml that is there but will not load: weights that do not
    #: sum to 100, a duplicate assessment id, malformed TOML. ``error``
    #: carries the message and ``file_path`` says what to edit.
    UNREADABLE = "unreadable"

    #: Nothing at that path, or it is a file that is not a module.toml. The
    #: path is wrong, which is a different problem from the folder being
    #: empty.
    MISSING = "missing"


@dataclass(frozen=True)
class ModuleFolder:
    """The answer to "what is in this folder?"."""

    #: The folder inspected. Always set, even when it does not exist, so a
    #: caller can report the path it was given.
    folder: pl.Path

    state: FolderState

    #: The loaded file, on LOADED only. Carries the parsed document as well
    #: as the model, so a caller can save without re-reading.
    file: ModuleFile | None = None

    #: Why it would not load, on UNREADABLE only. Already readable -- the
    #: validators in Module are written to be shown to a person.
    error: str | None = None

    #: The exception behind ``error``, for callers that want to match on the
    #: type rather than the text.
    cause: Exception | None = None

    @property
    def module(self) -> Module | None:
        """The module, on LOADED; ``None`` otherwise."""
        return self.file.module if self.file is not None else None

    @property
    def file_path(self) -> pl.Path:
        """Where the module.toml is, or would go."""
        return self.folder / MODULE_FILENAME

    @property
    def loaded(self) -> bool:
        return self.state is FolderState.LOADED

    @property
    def can_initialise(self) -> bool:
        """Whether offering to initialise here is safe.

        Only ever true for an empty folder. A folder whose module.toml is
        broken is deliberately excluded: initialising it would mean
        ``overwrite=True``, and that file holds the graders, the quiz rules
        and every status flag recorded so far. Editing it is the fix.
        """
        return self.state is FolderState.UNINITIALISED


def inspect_module_folder(path: "str | pl.Path") -> ModuleFolder:
    """
    Look in a folder and say what is there, without raising.

    Args:
    path (str | pl.Path): A module folder, or the ``module.toml`` inside one.
        A file path is accepted so that a caller who already has the file
        does not have to remember to pass its parent.

    Returns:
    ModuleFolder: The folder, the state, and whatever else that state
        carries -- the loaded file, or the message explaining why not.

    Example:
        >>> import pathlib as pl
        >>> found = inspect_module_folder(pl.Path("teaching/2026/Sem1/PS4034"))
        >>> found.state
        <FolderState.UNINITIALISED: 'uninitialised'>
        >>> found.can_initialise
        True
    """
    path = pl.Path(path)

    # A file was given. Only module.toml itself makes sense; anything else
    # is a mistyped path rather than a module folder.
    if path.is_file():
        if path.name != MODULE_FILENAME:
            return ModuleFolder(folder=path.parent, state=FolderState.MISSING)
        folder = path.parent
    else:
        folder = path

    if not folder.is_dir():
        return ModuleFolder(folder=folder, state=FolderState.MISSING)

    module_file = folder / MODULE_FILENAME
    if not module_file.is_file():
        return ModuleFolder(folder=folder, state=FolderState.UNINITIALISED)

    try:
        loaded = ModuleFile.load(module_file)
    except Exception as exc:  # noqa: BLE001 -- reporting, not handling
        # Deliberately broad. What the caller has to do is the same whatever
        # went wrong -- show the message, point at the file -- and the set of
        # things a hand-edited TOML can raise is not worth enumerating:
        # tomlkit parse errors, pydantic validation errors, a decoding error
        # from a file saved in the wrong encoding.
        return ModuleFolder(
            folder=folder,
            state=FolderState.UNREADABLE,
            error=str(exc),
            cause=exc,
        )

    return ModuleFolder(folder=folder, state=FolderState.LOADED, file=loaded)
