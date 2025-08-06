#!/usr/bin/env python

from enum import Enum
from typing import Self
from ..dependencies import BaseModel, PositiveFloat, pl, datetime


class FileType(Enum):
    CSV = ".csv"
    XL = ".xlsx"


class ClassList(BaseModel):
    path: pl.Path
    type: FileType
    ready: bool

    def toggle_ready(self) -> Self:
        self.ready = not self.ready
        return self


class GradeFile(BaseModel):
    path: pl.Path
    ready: bool
    completed: bool
    type: FileType

    def toggle_ready(self) -> Self:
        self.ready = not self.ready
        return self


class Calendar(BaseModel):
    path: pl.Path
    ready: bool

    def toggle_ready(self) -> Self:
        self.ready = not self.ready
        return self


class HandBook(BaseModel):
    path: pl.Path
    ready: bool

    def toggle_ready(self) -> Self:
        self.ready = not self.ready
        return self


def main():
    print("Hello from Documents.py")


if __name__ == '__main__':
    main()
