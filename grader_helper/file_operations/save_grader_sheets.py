#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import pathlib as pl


def main():
    # Example usage
    # Create a DataFrame with student submissions
    data = {
        "student_id": [1, 2, 3, 4, 5],
        "name": ["Alice", "Bob", "Charlie", "David", "Emma"],
        "grader": ["Grader1", "Grader2", "Grader1", "Grader3", "Grader2"],
    }  # Example grader assignments
    df = pd.DataFrame(data)

    # Folder to save Excel sheets
    folder_path = pl.Path.cwd()

    # List of graders
    graders = df["grader"].unique().tolist()

    # Call the function
    save_grader_sheets(df, folder_path, graders)


def save_grader_sheets(
        data: pd.DataFrame,
        folder: pl.Path,
        graders: list,
        criteria: list | None = None
) -> None:
    """
    Creates and saves a separate Excel sheet for each grader.

    Parameters
    ----------
    d : pandas DataFrame
        The DataFrame containing the student submissions to be saved.
    folder : pathlib.Path
        The folder where the Excel sheets will be saved.
    g : list
        A list of grader IDs.
    c : List of strings of criteria names

    Returns
    -------
    None
    """
    if criteria is not None:
        new_cols = list(data.columns) + \
            [c for c in criteria if c not in data.columns]
        data = data.reindex(columns=new_cols)
    try:
        # Loop over each grader
        for i in graders:
            if (folder / f"{i}.xlsx").exists():
                choice = input(
                    f"{i}.xlsx already exists. Do you want to overwrite it? (y/n): "
                )
                if choice[0].lower() != "y" or choice == "":
                    print(f"Skipping {i}.xlsx")
                    continue
                else:
                    # Select the submissions assigned to the current grader
                    grader_submissions = data.loc[data["grader"] == f"{i}"]
                    # Save the submissions to an Excel sheet
                    grader_submissions.to_excel(
                        folder / f"{i}.xlsx", index=False)

            else:
                # Select the submissions assigned to the current grader
                grader_submissions = data.loc[data["grader"] == f"{i}"]
                # Save the submissions to an Excel sheet
                grader_submissions.to_excel(folder / f"{i}.xlsx", index=False)
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
