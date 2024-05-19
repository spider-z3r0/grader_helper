#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ..dependencies import pd, os, tqdm, ThreadPoolExecutor, pl
from .process_grade_file import process_file




def catch_grades(directory: str, cell: str) -> pd.DataFrame:
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
    data = []  # List to store the student ID and grade

    file_paths = []  # List to store the file paths
    directory_path = pl.Path(directory)
    for file_path in directory_path.glob():
        try:
            if file_path.suffix == '.xlsx' and "Feedback sheet" in file_path.stem:
                file_paths.append(file_path)
        except FileNotFoundError:
            print(f"File not found: {file_path}")

    
    with ThreadPoolExecutor() as executor, tqdm(total=len(file_paths)) as pbar:
        futures = []
        for file_path in file_paths:
            future = executor.submit(process_file, file_path, cell)
            future.add_done_callback(lambda _: pbar.update())
            futures.append(future)

        for future in futures:
            result = future.result()
            if result:
                data.append(result)

    df = pd.DataFrame(data, columns=['Student ID', 'grade'])
    return df

   
