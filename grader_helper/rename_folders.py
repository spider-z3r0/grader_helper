import pandas as pd
import pathlib as pl
import re
from .ask_to_rename import ask_to_rename
from .is_already_renamed import is_already_renamed

def rename_folders(df, subs_folder):
    """
    Renames folders in subs_folder based on a DataFrame mapping of names to student IDs.
    
    Args:
        df (pd.DataFrame): DataFrame containing columns 'Last Name', 'First Name', and 'Student ID'.
        subs_folder (pl.Path): pathlib.Path object pointing to the directory containing the folders to be renamed.
    """
    # Convert DataFrame to a dictionary for easier lookup
    name_id_map = {(row['Last Name'].upper(), row['First Name'].upper()): row['Student ID'] for _, row in df.iterrows()}

    rename_attempts = []  # Initialize a list to keep track of rename attempts

    for folder in subs_folder.iterdir():
        if folder.is_dir() and not is_already_renamed(folder.name.upper()):
            folder_name_upper = folder.name.upper()
            matched = False
            
            for (last_name, first_name), student_id in name_id_map.items():
                if last_name in folder_name_upper and first_name in folder_name_upper:
                    new_folder_name = f"{last_name}, {first_name} ({student_id})"
                    try:
                        folder.rename(subs_folder / new_folder_name)
                        print(f"Folder renamed for {new_folder_name}")
                        rename_attempts.append({'Original Name': folder.name, 'Suggested Name': new_folder_name, 'Outcome': 'Renamed'})
                        matched = True
                        break
                    except Exception as e:
                        print(f"Failed to rename folder for {new_folder_name}: {e}")
                        rename_attempts.append({'Original Name': folder.name, 'Suggested Name': new_folder_name, 'Outcome': 'Failed'})
                        matched = True
                        break

            if not matched:
                for (last_name, first_name), student_id in name_id_map.items():
                    if f" {first_name} " in folder_name_upper and not matched:
                        new_folder_name = f"{last_name}, {first_name} ({student_id})"
                        if ask_to_rename(folder.name, new_folder_name):
                            try:
                                folder.rename(subs_folder / new_folder_name)
                                rename_attempts.append({'Original Name': folder.name, 'Suggested Name': new_folder_name, 'Outcome': 'User Confirmed'})
                                matched = True
                                break
                            except Exception as e:
                                print(f"Failed to rename folder for {new_folder_name}: {e}")
                                rename_attempts.append({'Original Name': folder.name, 'Suggested Name': new_folder_name, 'Outcome': 'Failed After User Confirmation'})
                                matched = True
                                break

                    elif f" {last_name} " in folder_name_upper and not matched:
                        new_folder_name = f"{last_name}, {first_name} ({student_id})"
                        if ask_to_rename(folder.name, new_folder_name):
                            try:
                                folder.rename(subs_folder / new_folder_name)
                                rename_attempts.append({'Original Name': folder.name, 'Suggested Name': new_folder_name, 'Outcome': 'User Confirmed'})
                                matched = True
                            except Exception as e:
                                print(f"Failed to rename folder for {new_folder_name}: {e}")
                                rename_attempts.append({'Original Name': folder.name, 'Suggested Name': new_folder_name, 'Outcome': 'Failed After User Confirmation'})
                        else:
                            rename_attempts.append({'Original Name': folder.name, 'Suggested Name': new_folder_name, 'Outcome': 'User Rejected'})
                            matched = True

            if not matched:
                rename_attempts.append({'Original Name': folder.name, 'Suggested Name': 'N/A', 'Outcome': 'No Match Found'})

    # Log rename attempts
    rename_log_df = pd.DataFrame(rename_attempts)
    log_path = subs_folder / "folder_rename_log.csv"
    
    # Append to log file if it exists or create a new one
    rename_log_df.to_csv(log_path, mode='a', header=not log_path.exists(), index=False)
    print("Folder rename operations logged to folder_rename_log.csv.")
