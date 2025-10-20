#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import pathlib as pl
from .scan_multiple_submissions import scan_multiple_subs


def alphabetise_folders(df, subs_folder):
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

    # Convert DataFrame to a dictionary for easier lookup
    name_id_map = {
        (row["Last Name"].upper(), row["First Name"].upper()): row["Student ID"]
        for _, row in df.iterrows()
    }

    def ask_to_rename(folder_name, suggested_name):
        """Prompts user for rename confirmation."""
        response = (
            input(f"Rename '{folder_name}' to '{suggested_name}'? (y/n): ")
            .strip()
            .lower()
        )
        return response == "y"

    rename_attempts = []  # Initialize a list to keep track of rename attempts

    for folder in subs_folder.iterdir():
        if folder.is_dir():
            folder_name_upper = folder.name.upper()
            matched = False

            for (last_name, first_name), student_id in name_id_map.items():
                if last_name in folder_name_upper and student_id in folder_name_upper:
                    new_folder_name = f"{last_name}, {first_name} ({student_id})"
                    try:
                        folder.rename(subs_folder / new_folder_name)
                        print(f"Folder renamed for {new_folder_name}")
                        rename_attempts.append(
                            {
                                "Original Name": folder.name,
                                "Suggested Name": new_folder_name,
                                "Outcome": "Renamed",
                            }
                        )
                        matched = True
                        break
                    except Exception as e:
                        print(f"Failed to rename folder for {new_folder_name}: {e}")
                        rename_attempts.append(
                            {
                                "Original Name": folder.name,
                                "Suggested Name": new_folder_name,
                                "Outcome": "Failed",
                            }
                        )
                        matched = True
                        break

            if not matched:
                for (last_name, first_name), student_id in name_id_map.items():
                    if f" {student_id} " in folder_name_upper and not matched:
                        new_folder_name = f"{last_name}, {first_name} ({student_id})"
                        if ask_to_rename(folder.name, new_folder_name):
                            try:
                                folder.rename(subs_folder / new_folder_name)
                                rename_attempts.append(
                                    {
                                        "Original Name": folder.name,
                                        "Suggested Name": new_folder_name,
                                        "Outcome": "User Confirmed",
                                    }
                                )
                                matched = True
                                break
                            except Exception as e:
                                print(
                                    f"Failed to rename folder for {new_folder_name}: {e}"
                                )
                                rename_attempts.append(
                                    {
                                        "Original Name": folder.name,
                                        "Suggested Name": new_folder_name,
                                        "Outcome": "Failed After User Confirmation",
                                    }
                                )
                                matched = True
                                break

                    elif f" {last_name} " in folder_name_upper and not matched:
                        new_folder_name = f"{last_name}, {first_name} ({student_id})"
                        if ask_to_rename(folder.name, new_folder_name):
                            try:
                                folder.rename(subs_folder / new_folder_name)
                                rename_attempts.append(
                                    {
                                        "Original Name": folder.name,
                                        "Suggested Name": new_folder_name,
                                        "Outcome": "User Confirmed",
                                    }
                                )
                                matched = True
                            except Exception as e:
                                print(
                                    f"Failed to rename folder for {new_folder_name}: {e}"
                                )
                                rename_attempts.append(
                                    {
                                        "Original Name": folder.name,
                                        "Suggested Name": new_folder_name,
                                        "Outcome": "Failed After User Confirmation",
                                    }
                                )
                        else:
                            rename_attempts.append(
                                {
                                    "Original Name": folder.name,
                                    "Suggested Name": new_folder_name,
                                    "Outcome": "User Rejected",
                                }
                            )
                            matched = True

            if not matched:
                rename_attempts.append(
                    {
                        "Original Name": folder.name,
                        "Suggested Name": "N/A",
                        "Outcome": "No Match Found",
                    }
                )

    # Log rename attempts
    rename_log_df = pd.DataFrame(rename_attempts)
    log_path = subs_folder / "folder_rename_log.csv"
    if log_path.exists():
        renames = pd.read_csv(log_path)
        rename_log_df = pd.concat([renames, rename_log_df], ignore_index=True)
    rename_log_df.to_csv(log_path, index=False)
    print("Folder rename operations logged to folder_rename_log.csv.")
