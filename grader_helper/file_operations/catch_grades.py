#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ..dependencies import pd, pl, tqdm
from .extract_studentid_grade import extract_studentid_grade
import logging

def catch_grades(directory: pl.Path, cell: str) -> pd.DataFrame:
    """
    Walk `directory`, find .xlsx/.xlsm/.xlsb feedback files, extract (student_id, grade)
    serially, and return a DataFrame with columns ["Student ID", "grade"].
    """
    if not isinstance(directory, pl.Path):
        raise TypeError("directory must be a Path object")
    if not isinstance(cell, str):
        raise TypeError("cell must be a string")
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    # Case-insensitive match on stem; include common Excel formats
    exts = {".xlsx", ".xlsm", ".xlsb", ".xls"}
    file_paths = [
        p for p in directory.rglob("*")
        if p.suffix.lower() in exts and "feedback sheet" in p.stem.lower()
    ]

    data = []
    for p in tqdm(file_paths, desc="Reading feedback"):
        logging.debug(f"Reading: {p}")
        res = extract_studentid_grade(p, cell, allow_xlwings_fallback=True)
        if res is not None:
            data.append(res)
        else:
            logging.warning(f"Skipped (no value): {p}")

    return pd.DataFrame(data, columns=["Student ID", "grade"])

# def catch_grades(directory: pl.Path, cell: str) -> pd.DataFrame:
#     """
#     Walk `directory`, find .xlsx feedback files, extract (student_id, grade)
#     serially, and return a DataFrame with columns ["Student ID", "grade"].
#     """
#     if not isinstance(directory, pl.Path):
#         raise TypeError("directory must be a Path object")
#     if not isinstance(cell, str):
#         raise TypeError("cell must be a string")
#     if not directory.exists():
#         raise FileNotFoundError(f"Directory not found: {directory}")
#
#     # Case-insensitive match on stem; recurse only for .xlsx
#     file_paths = [
#         p for p in directory.rglob("*.xlsx")
#         if "feedback sheet" in p.stem.lower()
#     ]
#
#     data = []
#     for p in tqdm(file_paths, desc="Reading feedback"):
#         logging.debug(f"Reading: {p}")
#         res = extract_studentid_grade(p, cell)
#         if res is not None:
#             data.append(res)
#         else:
#             logging.warning(f"Skipped (read error): {p}")
#
#     return pd.DataFrame(data, columns=["Student ID", "grade"])
