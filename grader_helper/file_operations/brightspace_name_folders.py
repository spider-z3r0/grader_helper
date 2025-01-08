#!/usr/bin/env python
# -*- coding: utf-8 -*-


from ..dependencies import pd, pl


def brightspace_name_folders(df: pd.DataFrame, subs_folder: pl.Path):
    rename_attempts = []
    unfound_names = []

    # Convert DataFrame columns to uppercase for case-insensitive comparison
    df["Suggested Name"] = df["Suggested Name"].str.upper()
    df["Original Name"] = df["Original Name"].str.upper()

    name_map = dict(zip(df["Suggested Name"], df["Original Name"]))

    for folder in subs_folder.iterdir():
        if folder.is_dir():
            folder_name_upper = folder.name.upper()
            if folder_name_upper in name_map:
                new_folder_name = name_map[folder_name_upper]
                try:
                    folder.rename(subs_folder / new_folder_name)
                    print(f"Folder {folder.name} renamed to {new_folder_name}")
                    rename_attempts.append(
                        {
                            "Original Name": folder.name,
                            "Suggested Name": new_folder_name,
                            "Outcome": "Renamed",
                        }
                    )
                except Exception as e:
                    print(
                        f"Failed to rename folder {folder.name} to {new_folder_name}: {e}"
                    )
                    rename_attempts.append(
                        {
                            "Original Name": folder.name,
                            "Suggested Name": new_folder_name,
                            "Outcome": f"Failed: {e}",
                        }
                    )
            elif folder_name_upper in df["Original Name"].values:
                rename_attempts.append(
                    {
                        "Original Name": folder.name,
                        "Suggested Name": folder.name,
                        "Outcome": "Already Correct",
                    }
                )
            else:
                unfound_names.append(folder.name)

    # Log unfound names
    if unfound_names:
        unfound_df = pd.DataFrame(unfound_names, columns=["Unfound Name"])
        log_path = subs_folder / "folder_brightspace_name_unfound.csv"
        unfound_df.to_csv(log_path, index=False)
        print("Unfound folder names logged to folder_brightspace_name_unfound.csv.")

    # Log rename attempts
    rename_log_df = pd.DataFrame(rename_attempts)
    log_path = subs_folder / "folder_brightspace_name_log.csv"
    if log_path.exists():
        renames = pd.read_csv(log_path)
        rename_log_df = pd.concat([renames, rename_log_df], ignore_index=True)
    rename_log_df.to_csv(log_path, index=False)
    print("Folder rename operations logged to folder_brightspace_name_log.csv.")
