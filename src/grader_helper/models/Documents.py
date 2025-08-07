#!/usr/bin/env python
"""Document-related models for the grader helper.

This module defines simple Pydantic models used to describe various
documents such as class lists, grade files, calendars and handbooks. Each
model tracks the path to the underlying file and whether the document is
ready for use. The ``FileType`` enum captures the supported file
extensions.
"""

from enum import Enum
from typing import Self
from grader_helper.dependencies import BaseModel, PositiveFloat, pl, datetime


class FileType(Enum):
    """Supported file types for document models."""

    CSV = ".csv"
    XL = ".xlsx"


class ClassList(BaseModel):
    """Class list document.

    Attributes:
        path (pl.Path): Path to the class list file.
        type (FileType): File type of the class list.
        ready (bool): Whether the class list has been prepared for use.
    """

    path: pl.Path
    type: FileType
    ready: bool

    def toggle_ready(self) -> Self:
        """Flip the readiness state of the class list and return ``self``."""

        self.ready = not self.ready
        return self


class GradeFile(BaseModel):
    """Grade file document.

    Attributes:
        path (pl.Path): Path to the grade file.
        ready (bool): Whether the grade file is ready for processing.
        completed (bool): Indicates whether grading is complete.
        type (FileType): File type of the grade file.
    """

    path: pl.Path
    ready: bool
    completed: bool
    type: FileType

    def toggle_ready(self) -> Self:
        """Toggle the ``ready`` flag for the grade file and return ``self``."""

        self.ready = not self.ready
        return self


class Calendar(BaseModel):
    """Calendar document.

    Attributes:
        path (pl.Path): Path to the calendar file.
        ready (bool): Whether the calendar has been prepared for use.
    """

    path: pl.Path
    ready: bool

    def toggle_ready(self) -> Self:
        """Switch the readiness state of the calendar and return ``self``."""

        self.ready = not self.ready
        return self


class HandBook(BaseModel):
    """Handbook document.

    Attributes:
        path (pl.Path): Path to the handbook file.
        ready (bool): Whether the handbook is prepared for use.
    """

    path: pl.Path
    ready: bool

    def toggle_ready(self) -> Self:
        """Invert the ``ready`` flag for the handbook and return ``self``."""

        self.ready = not self.ready
        return self


def main():
    print("Hello from Documents.py")


if __name__ == '__main__':
    main()
