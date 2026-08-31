#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Fill in the marks on the student information system's own upload file.

SI issues a file with one row per enrolled student and three columns blank --
``Mark``, ``Grade`` and a ``CD`` nobody fills -- and you send the same file
back. So this is the departmental sheet's problem again: **we fill in two
fields of somebody else's file, rather than producing a file in their
format.**

Everything else comes back byte for byte, and that is not fastidiousness. The
file has real quirks, and a round trip through a dataframe library loses them:

* **Line endings are bare LF**, on a file a Windows system produced. Python's
  ``open(path, "w")`` translates ``\\n`` to ``\\r\\n`` on Windows, so writing
  it back the obvious way changes *every line in the file*. Bytes are read and
  written here, with whatever terminator the file already used.
* **No field is quoted** and none holds a comma -- names are ``KEVIN
  O'MALLEY``, upper case with an apostrophe and no surname comma -- so a plain
  split is correct. A file that *did* contain a quote is refused rather than
  quietly mangled, because the simple splitter cannot promise fidelity there.
* **The ``#`` prefixes** are on headers as well as values (``#Module`` holds
  ``#PS3021``), ``#Ass#`` carries one at each end, and ``#CD`` holds values
  like ``#07`` whose leading zero matters. None of it is interpreted; it is
  copied.

``#SPR_Code`` is ``#<student id>/<attempt>``, the attempt being how many times
the student has taken the module. It is **matched on and never rebuilt** --
the attempt number is SI's and cannot be derived from anything we hold.

House convention: ``pl`` is pathlib, ``pr`` is polars.

    >>> import pathlib as pl
    >>> import polars as pr
"""

import pathlib as pl
from typing import NamedTuple

from .dependencies import pd
from .models import tidy_number

#: The two columns we fill. The bare ``CD`` beside them stays empty -- that is
#: the internal system's business and not ours to tidy up.
MARK_COLUMN = "Mark"
GRADE_COLUMN = "Grade"

#: The column carrying the student id and the attempt number.
KEY_COLUMN = "#SPR_Code"

#: What the file must have for this to recognise it as an SI upload.
REQUIRED_COLUMNS = (KEY_COLUMN, MARK_COLUMN, GRADE_COLUMN)


class SiUpload(NamedTuple):
    """What `write_si_marks` did."""

    #: The file written.
    path: pl.Path
    #: How many of SI's rows were given a mark.
    filled: int
    #: Students with a mark whom SI's file has no row for. SI's roll is the
    #: authority on who is enrolled, so these are reported, never added.
    not_enrolled: list[str]
    #: Students on SI's roll with no mark. Empty unless `allow_unmarked`.
    unmarked: list[str]

    def __str__(self) -> str:
        extra = ""
        if self.not_enrolled:
            extra += f", {len(self.not_enrolled)} not on SI's roll"
        if self.unmarked:
            extra += f", {len(self.unmarked)} left blank"
        return f"{self.path.name}: {self.filled} marks written{extra}"


def student_id_from_key(value: str) -> str:
    """The student id out of ``#23304308/1``.

    The ``#`` comes off and the attempt number after the ``/`` is dropped. The
    id stays **text**: a leading zero is part of it, and an id that goes
    through an integer loses one.

    >>> student_id_from_key("#23304308/1")
    '23304308'
    >>> student_id_from_key("#00123456/3")
    '00123456'
    """
    return value.strip().lstrip("#").split("/")[0].strip()


def read_si_file(si_file: pl.Path | str) -> tuple[list[str], list[list[str]], str]:
    """
    Read SI's file into its header, its rows and its line terminator.

    Args:
    si_file (pl.Path | str): The file SI issued.

    Returns:
    tuple: ``(headers, rows, terminator)``. Every value is text, exactly as
    the file holds it -- ``#`` prefixes, leading zeros and all.

    Raises:
    FileNotFoundError: If the file is not there.
    ValueError: If it is empty, holds a quote character, is missing a column
        this needs, or has a row whose field count differs from the header's.

    Example:
        >>> headers, rows, terminator = read_si_file("PS3021_SI.CSV")
        >>> headers[:3]
        ['Year', 'Period', '#Module']
    """
    path = pl.Path(si_file)
    if not path.is_file():
        raise FileNotFoundError(f"No SI file at {path}")

    raw = path.read_bytes()
    if b'"' in raw:
        raise ValueError(
            f"{path.name} contains a quote character. Every SI file seen so "
            "far has none and no field holds a comma, so this splits on "
            "commas and copies every other byte through unchanged -- which it "
            "cannot promise for a quoted file. Rather than mangle it "
            "silently this refuses; if quoted SI files are now a thing, the "
            "splitter has to learn about them."
        )

    terminator = "\r\n" if b"\r\n" in raw else "\n"
    lines = [line for line in raw.decode("utf-8-sig").split(terminator) if line != ""]
    if not lines:
        raise ValueError(f"{path.name} is empty, so there is nothing to fill in")

    headers = lines[0].split(",")
    missing = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing:
        raise ValueError(
            f"{path.name} has no {missing} column(s) in its header row. It "
            f"holds: {headers}.\nIs this an SI upload file?"
        )

    rows = []
    for number, line in enumerate(lines[1:], start=2):
        fields = line.split(",")
        if len(fields) != len(headers):
            raise ValueError(
                f"{path.name} line {number} has {len(fields)} fields where the "
                f"header has {len(headers)}. Rewriting it would put values in "
                "the wrong columns, so this refuses rather than guessing which "
                "field is which."
            )
        rows.append(fields)
    return headers, rows, terminator


def write_si_marks(
    df: pd.DataFrame,
    si_file: pl.Path | str,
    destination: pl.Path | str | None = None,
    id_column: str = "Student ID",
    total_column: str = "Total % Grade",
    letter_column: str = "Letter Grade",
    allow_unmarked: bool = False,
) -> SiUpload:
    """
    Write a module's marks into SI's upload file.

    Args:
    df (pd.DataFrame): The prepared marks, as
        `prepare_data_for_departmental_template` returns them.
    si_file (pl.Path | str): The file SI issued.
    destination (pl.Path | str | None): Where to write. Defaults to None,
        meaning write `si_file` back in place.
    id_column (str): The column holding the student id.
    total_column (str): The column holding the module total.
    letter_column (str): The column holding the letter grade.
    allow_unmarked (bool): Leave a student on SI's roll with no mark blank
        rather than refusing. Defaults to False -- see the note.

    Returns:
    SiUpload: The path written, how many rows were filled, and who was on
    neither side of the match.

    Note:
        **A student on SI's roll with no mark is refused, not blanked.** The
        scratch version of this replaced `Mark` unconditionally, so a re-run
        against a partial marks frame wrote nulls over marks already in the
        file. Blanking a mark is not something to do quietly, so this raises
        and names them; `allow_unmarked=True` if that is genuinely wanted.

        **SI's roll decides the cohort.** A student in the marks but not in
        SI's file is reported in `not_enrolled`, never appended -- a row with
        an empty `#SPR_Code` is not something SI can use.

        The mark is written as a whole number, which the departmental total
        always is: the sheet computes `ROUND(SUM(...),0)`. The grade is the
        band letter verbatim.

    Raises:
    FileNotFoundError: If `si_file` is not there.
    ValueError: If the frame is empty or missing a column; if the file cannot
        be read faithfully; or if a student on SI's roll has no mark and
        `allow_unmarked` is False.

    Example:
        >>> sheet = prepare_data_for_departmental_template(marks, module)
        >>> write_si_marks(sheet, module.si_file_path, module.root / "upload.CSV")
    """
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a pandas DataFrame")
    if df.empty:
        raise ValueError("DataFrame is empty, so there are no marks to write")
    for column in (id_column, total_column, letter_column):
        if column not in df.columns:
            raise ValueError(
                f"DataFrame has no {column!r} column. Run "
                "prepare_data_for_departmental_template first; it produces the "
                "shape this expects."
            )

    headers, rows, terminator = read_si_file(si_file)
    key_at = headers.index(KEY_COLUMN)
    mark_at = headers.index(MARK_COLUMN)
    grade_at = headers.index(GRADE_COLUMN)

    marks = {
        str(row[id_column]): (row[total_column], row[letter_column])
        for _, row in df.iterrows()
    }

    filled = 0
    unmarked: list[str] = []
    on_the_roll: set[str] = set()

    for fields in rows:
        student_id = student_id_from_key(fields[key_at])
        on_the_roll.add(student_id)

        found = marks.get(student_id)
        if found is None or pd.isna(found[0]):
            # Left exactly as the file had it. Writing a blank here is what
            # overwrote real marks on a re-run.
            unmarked.append(student_id)
            continue

        total, letter = found
        fields[mark_at] = tidy_number(float(total))
        fields[grade_at] = str(letter)
        filled += 1

    if unmarked and not allow_unmarked:
        shown = sorted(unmarked)
        raise ValueError(
            f"{len(unmarked)} student(s) on SI's roll have no mark: "
            f"{shown[:10]}{' ...' if len(shown) > 10 else ''}.\n"
            "Their Mark and Grade are left as the file had them, so on a "
            "re-run the file keeps whatever it already held and the two "
            "records disagree without saying so. Collate the missing marks, "
            "or pass allow_unmarked=True if they really are meant to go up "
            "blank."
        )

    not_enrolled = sorted(set(marks) - on_the_roll)

    path = pl.Path(destination) if destination is not None else pl.Path(si_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = terminator.join([",".join(headers), *(",".join(row) for row in rows)])
    # Bytes, and the file's own terminator. Writing text on Windows would turn
    # every one of these bare LFs into CRLF -- every line in the file changed
    # by a function that was asked to change two fields.
    path.write_bytes((body + terminator).encode("utf-8"))

    return SiUpload(
        path=path,
        filled=filled,
        not_enrolled=not_enrolled,
        unmarked=sorted(unmarked),
    )
