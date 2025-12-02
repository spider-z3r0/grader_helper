#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import pathlib as pl
import re
from .scan_multiple_submissions import scan_multiple_subs





def alphabetise_folders(df:pd.DataFrame, subs_folder:pl.Path, verbose:bool = False):
    """
    Renames folders in subs_folder based on a DataFrame mapping of names to student IDs. It take the brightspace folder names and renames them
    to the format 'Last Name, First Name (Student ID)' (which is the one used by UL and which a lot of our systems expect). It also creates a log of the rename operations
    and saves it to a csv file called 'folder_rename_log.csv' in the subs_folder directory. This csv file will be updated if the function is run again allowing us to include
    late submissions.

    You can use the 'folder_rename_log.csv' file to run the `brightspace_name_folders()` function that will rename the folder *back* to the brightspace format so that they can be
    uploaded back to the brightspace assignment folder.

    Args:
        df (pd.DataFrame): DataFrame containing columns 'Last Name', 'First Name', and 'Student ID'.
        subs_folder (Path): pathlib.Path object pointing to the directory containing the folders to be renamed.


    """
    # test for multiple subs and fail if found. 
    duplicates = scan_multiple_subs(subs_folder)
    if duplicates:
        body = "\n".join(
            f" - {k}: {', '.join(map(str, v))}" for k, v in sorted(duplicates.items())
        )
        raise RuntimeError(
            "The following students have multiple submissions:\n"
            f"{body}\n"
            "Please delete extras or consolidate into one folder."
        )
    

    # look for logs of a previous renaming operations. 
    log_path = subs_folder / "folder_rename_log.csv"
    if log_path.exists():
        renames = pd.read_csv(log_path)
    else:
        renames = None

    # Convert DataFrame to a dictionary for easier lookup
    name_id_map = {
        str(row["Student ID"]): (row["Last Name"].upper(), row["First Name"].upper())
        for _, row in df.iterrows()
    }

    # This may not be needed anymore but I'm going to leave it here for now. 
    # def ask_to_rename(folder_name, suggested_name):
    #     """Prompts user for rename confirmation."""
    #     response = (
    #         input(f"Rename '{folder_name}' to '{suggested_name}'? (y/n): ")
    #         .strip()
    #         .lower()
    #     )
    #     return response == "y"

    rename_attempts = []  # Initialize a list to keep track of rename attempts

    student_number_pattern = re.compile(r"(?<= - )\d+\b")
    for folder in subs_folder.iterdir():
        if folder.is_dir() and (student_number := student_number_pattern.search(folder.stem)):
            #rename the folder
            try:
                (last,first) = name_id_map.get(student_number.group(0))
                new_folder_name = f"{last}, {first}({student_number.group(0)})"
                folder.rename(subs_folder / new_folder_name)
                # have a ticker for the user.
                if verbose:
                    print(f"Folder renamed for {new_folder_name}")
                #add the process details to the rename_attempts file
                rename_attempts.append(
                            {
                                "Original Name": folder.name,
                                "Suggested Name": new_folder_name,
                                "Outcome": "Renamed",
                                "Error": None,
                            }
                        )
            except TypeError as t:
                rename_attempts.append(
                            {
                                "Original Name": folder.name,
                                "Suggested Name": None,
                                "Outcome": "Failed",
                                "Error": "Student Number not present in class list",
                            }
                        )
            except Exception as e:
                rename_attempts.append(
                            {
                                "Original Name": folder.name,
                                "Suggested Name": new_folder_name,
                                "Outcome": "Failed",
                                "Error": repr(e),
                            }
                        )

    renames_log = pd.DataFrame(rename_attempts)

    if renames is not None:
        pd.concat([renames, renames_log]).to_csv(log_path)
    else:
        renames_log.to_csv(log_path)

