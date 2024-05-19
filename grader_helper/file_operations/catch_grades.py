#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ..dependencies import pd, os, tqdm, ThreadPoolExecutor, pl
from .extract_studentid_grade import extract_studentid_grade




def catch_grades(directory: pl.Path, cell: str) -> pd.DataFrame:
    """
    Iterates through a directory of student submissions, finds the student's feedback file, and extracts the grade.
    Args:
        directory (str): The directory containing the student submissions subdirectories.
        cell (str): The cell containing the grade in the feedback file.

    Returns:
        pd.DataFrame: A DataFrame containing the student ID and grade.

    Note:
        This should allow you to compare the grades in the feedback files with the grades in the master file.
    """
    # check if directory is a Path object
    if not isinstance(directory, pl.Path):
        raise TypeError("directory must be a Path object")
    # check if cell is a string
    if not isinstance(cell, str):
        raise TypeError("cell must be a string")
    
    
    data = []  # List to store the student ID and grade

    file_paths = []  # List to store the file paths
    for file_path in directory.glob("**/*"):
        try:
            if file_path.suffix == '.xlsx' and "Feedback sheet" in file_path.stem:
                file_paths.append(file_path)
        except FileNotFoundError:
            print(f"File not found: {file_path}")

    
    with ThreadPoolExecutor() as executor, tqdm(total=len(file_paths)) as pbar:
        futures = []
        for file_path in file_paths:
            future = executor.submit(extract_studentid_grade, file_path, cell)
            future.add_done_callback(lambda _: pbar.update())
            futures.append(future)

        for future in futures:
            result = future.result()
            if result:
                data.append(result)

    df = pd.DataFrame(data, columns=['Student ID', 'grade'])
    return df

   
