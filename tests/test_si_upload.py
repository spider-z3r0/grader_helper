#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Filling in the student information system's own upload file.

The load-bearing test is `test_only_the_mark_and_grade_change`: this function
promises to change two fields of somebody else's file and leave every other
byte alone, and that promise is checkable directly.

Second to it is the line-ending test. The real file uses **bare LF** despite
coming from a Windows system, and Python's text-mode write turns those into
CRLF on Windows -- every line in the file changed by a function asked to
change two fields. Linux CI would never notice, because on Linux text mode
writes LF anyway, so the test asserts on bytes rather than trusting the
platform.

House convention: ``pl`` is pathlib, ``pr`` is polars.
"""

import pathlib as pl
import sys

import pandas as pd
import pytest

from grader_helper import read_si_file, student_id_from_key, write_si_marks

sys.path.insert(0, str(pl.Path(__file__).parent))
from fake_module import SI_COLUMNS, write_si_export  # noqa: E402

#: Where Mark and Grade sit in SI's thirteen columns.
MARK_AT = SI_COLUMNS.index("Mark")
GRADE_AT = SI_COLUMNS.index("Grade")


@pytest.fixture
def si_file(tmp_path) -> pl.Path:
    """A blank export for the fixture cohort, as SI would issue it."""
    return write_si_export(tmp_path / "PS4001_SI.CSV", "PS4001")


@pytest.fixture
def marks() -> pd.DataFrame:
    """Marks for the whole fixture cohort, including the non-participant."""
    from fake_module import COHORT

    return pd.DataFrame(
        {
            "Student ID": [sid for sid, *_ in COHORT],
            "Total % Grade": [float(70 if sid != "23304309" else 0) for sid, *_ in COHORT],
            "Letter Grade": ["B1" if sid != "23304309" else "NG" for sid, *_ in COHORT],
        }
    )


# --------------------------------------------------------------------------
# The key.


@pytest.mark.parametrize(
    "key, expected",
    [
        ("#23304308/1", "23304308"),
        ("#00123456/3", "00123456"),   # a leading zero is part of the id
        ("#23304307/2", "23304307"),
        (" #23304301/1 ", "23304301"),
    ],
)
def test_the_student_id_comes_out_of_the_key(key, expected):
    assert student_id_from_key(key) == expected


# --------------------------------------------------------------------------
# Fidelity -- the whole point.


def test_only_the_mark_and_grade_change(si_file, marks):
    """Two fields of thirteen. Every other byte comes back as it went in."""
    before = si_file.read_bytes().decode()
    write_si_marks(marks, si_file)
    after = si_file.read_bytes().decode()

    old = before.split("\n")
    new = after.split("\n")
    assert len(old) == len(new), "the file gained or lost a line"
    assert old[0] == new[0], "the header row was rewritten"

    for line_number, (was, now) in enumerate(zip(old[1:], new[1:]), start=2):
        was_fields, now_fields = was.split(","), now.split(",")
        assert len(was_fields) == len(now_fields), f"line {line_number} changed shape"
        changed = {
            index
            for index, (a, b) in enumerate(zip(was_fields, now_fields))
            if a != b
        }
        assert changed <= {MARK_AT, GRADE_AT}, (
            f"line {line_number} changed fields {sorted(changed)}; only "
            f"{MARK_AT} (Mark) and {GRADE_AT} (Grade) are ours"
        )


def test_the_bare_lf_line_endings_survive(si_file, marks):
    """The Windows hazard, asserted on bytes because Linux would hide it.

    The real file uses bare LF though a Windows system produced it. Writing it
    back in text mode on Windows turns every one of them into CRLF -- the
    whole file changed by a function asked to change two fields. On Linux a
    text-mode write happens to produce LF, so only a byte-level assertion
    catches this anywhere.
    """
    assert b"\r\n" not in si_file.read_bytes(), "the fixture is not bare-LF"

    write_si_marks(marks, si_file)
    written = si_file.read_bytes()

    assert b"\r\n" not in written, "a CRLF got in; the file was written as text"
    assert written.endswith(b"\n"), "the trailing newline went missing"
    assert not written.startswith(b"\xef\xbb\xbf"), "a BOM got added"


def test_a_name_with_an_apostrophe_survives(tmp_path, marks):
    """`KEVIN O'MALLEY` -- upper case, an apostrophe, and no surname comma.

    Names are the field most likely to carry something a naive writer would
    quote or escape. This one is never written at all, and must come back
    exactly as it went in.
    """
    header = ",".join(SI_COLUMNS)
    row = (
        "2025/6,SEM1,#PS4001,A,#PS4001,#1,#23304301/1,"
        "KEVIN O'MALLEY,#07,,,,#23304301/1"
    )
    path = tmp_path / "one.CSV"
    path.write_bytes(f"{header}\n{row}\n".encode())

    write_si_marks(marks, path)
    written = path.read_text()

    assert "KEVIN O'MALLEY" in written
    assert '"' not in written, "a quote was introduced around the apostrophe"


def test_the_hash_prefixes_and_leading_zeros_are_untouched(si_file, marks):
    """`#07` through anything numeric comes back as `#7` or 7."""
    write_si_marks(marks, si_file)
    _, rows, _ = read_si_file(si_file)

    codes = {row[SI_COLUMNS.index("#CD")] for row in rows}
    assert "#07" in codes, "the leading zero on #CD was lost"
    assert all(row[SI_COLUMNS.index("#Module")].startswith("#") for row in rows)
    assert all(row[SI_COLUMNS.index("#Ass#")] == "#1" for row in rows)


def test_the_attempt_number_is_preserved(si_file, marks):
    """`#SPR_Code` is matched on, never rebuilt.

    The attempt count after the `/` is SI's and cannot be derived from
    anything we hold, so a writer that reconstructed the key would get every
    resitting student wrong and nobody else.
    """
    write_si_marks(marks, si_file)
    _, rows, _ = read_si_file(si_file)

    keys = {row[SI_COLUMNS.index("#SPR_Code")] for row in rows}
    assert "#23304311/3" in keys, "a third attempt was rewritten as a first"
    assert "#23304307/2" in keys
    # And the second copy of the key agrees with the first.
    for row in rows:
        assert row[SI_COLUMNS.index("#SPR_Code")] == row[SI_COLUMNS.index("#Cand Key")]


def test_the_bare_cd_column_stays_empty(si_file, marks):
    """Nobody fills it, us included."""
    write_si_marks(marks, si_file)
    _, rows, _ = read_si_file(si_file)

    assert all(row[SI_COLUMNS.index("CD")] == "" for row in rows)


# --------------------------------------------------------------------------
# The marks themselves.


def test_the_mark_is_a_whole_number_and_the_grade_a_letter(si_file, marks):
    write_si_marks(marks, si_file)
    _, rows, _ = read_si_file(si_file)

    written = {
        row[SI_COLUMNS.index("#SPR_Code")]: (row[MARK_AT], row[GRADE_AT])
        for row in rows
    }
    assert written["#23304301/1"] == ("70", "B1"), "not '70.0'"
    # A non-participant goes up as zero and NG. SI accepts that letter --
    # confirmed with the module leader rather than assumed -- so the grade
    # the departmental sheet gives is the grade SI receives, with no special
    # case anywhere in the chain.
    assert written["#23304309/1"] == ("0", "NG")


def test_a_leading_zero_id_is_matched(si_file, marks):
    """'00123456' must not be looked up as 123456."""
    result = write_si_marks(marks, si_file)

    assert result.not_enrolled == []
    _, rows, _ = read_si_file(si_file)
    for row in rows:
        if row[SI_COLUMNS.index("#SPR_Code")] == "#00123456/1":
            assert row[MARK_AT] != "", "the student with a leading zero got no mark"
            break
    else:
        pytest.fail("00123456 is not in the fixture's SI file")


# --------------------------------------------------------------------------
# Refusals.


def test_refuses_to_blank_a_mark_for_a_student_with_none(si_file, marks):
    """The fault in the scratch version, which this exists to prevent.

    It replaced `Mark` unconditionally, so any SI row unmatched in the grades
    frame was written as null. Harmless the first time -- the column is empty
    anyway -- and on a re-run it overwrites real marks with nothing.
    """
    partial = marks.iloc[:3]

    with pytest.raises(ValueError, match="have no mark"):
        write_si_marks(partial, si_file)


def test_marks_already_in_the_file_survive_a_partial_rerun(si_file, marks):
    """And with the escape hatch, they are left alone rather than blanked."""
    write_si_marks(marks, si_file)
    partial = marks.iloc[:3]

    result = write_si_marks(partial, si_file, allow_unmarked=True)
    _, rows, _ = read_si_file(si_file)

    assert result.filled == 3
    assert len(result.unmarked) == len(marks) - 3
    assert all(row[MARK_AT] != "" for row in rows), (
        "a mark already in the file was blanked by a partial re-run"
    )


def test_a_student_not_on_sis_roll_is_reported_not_appended(si_file, marks):
    """SI's file decides who is enrolled.

    The scratch version's full join appended a row with a null `#SPR_Code`,
    which is not something SI can use.
    """
    extra = pd.concat(
        [
            marks,
            pd.DataFrame(
                {
                    "Student ID": ["99999999"],
                    "Total % Grade": [55.0],
                    "Letter Grade": ["C1"],
                }
            ),
        ],
        ignore_index=True,
    )
    before = len(si_file.read_text().splitlines())
    result = write_si_marks(extra, si_file)

    assert result.not_enrolled == ["99999999"]
    assert len(si_file.read_text().splitlines()) == before, "a row was appended"


def test_refuses_a_quoted_file(tmp_path, marks):
    """The simple splitter cannot promise fidelity on a quoted file."""
    header = ",".join(SI_COLUMNS)
    row = '2025/6,SEM1,#PS4001,A,#PS4001,#1,#23304301/1,"O\'MALLEY, KEVIN",#07,,,,#23304301/1'
    path = tmp_path / "quoted.CSV"
    path.write_bytes(f"{header}\n{row}\n".encode())

    with pytest.raises(ValueError, match="quote character"):
        write_si_marks(marks, path)


def test_refuses_a_row_with_the_wrong_field_count(tmp_path, marks):
    header = ",".join(SI_COLUMNS)
    path = tmp_path / "short.CSV"
    path.write_bytes(f"{header}\n2025/6,SEM1,#PS4001\n".encode())

    with pytest.raises(ValueError, match="fields where the header has"):
        write_si_marks(marks, path)


def test_refuses_a_file_that_is_not_an_si_upload(tmp_path, marks):
    path = tmp_path / "something.CSV"
    path.write_bytes(b"Name,Mark\nAOIFE ANGOOD,70\n")

    with pytest.raises(ValueError, match="#SPR_Code"):
        write_si_marks(marks, path)


def test_refuses_a_missing_file(tmp_path, marks):
    with pytest.raises(FileNotFoundError):
        write_si_marks(marks, tmp_path / "nope.CSV")


def test_refuses_an_empty_frame(si_file):
    with pytest.raises(ValueError, match="empty"):
        write_si_marks(pd.DataFrame(), si_file)


def test_writing_to_a_destination_leaves_the_original_alone(si_file, marks, tmp_path):
    before = si_file.read_bytes()
    result = write_si_marks(marks, si_file, tmp_path / "upload.CSV")

    assert result.path == tmp_path / "upload.CSV"
    assert si_file.read_bytes() == before, "the file SI issued was modified"
    assert result.path.read_bytes() != before
