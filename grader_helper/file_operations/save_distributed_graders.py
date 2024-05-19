#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pandas as pd
import pathlib as pl
from ..assignment.assign_graders_individual import assign_graders_individual


def main():
    # Example usage
    # Create a DataFrame with student information
    data = {
        "student_id": [1, 2, 3, 4, 5],
        "name": ["Alice", "Bob", "Charlie", "David", "Emma"],
    }
    df = pd.DataFrame(data)

    # List of graders
    graders = ["Grader1", "Grader2", "Grader3"]

    # Call the function
    updated_df = assign_graders_individual(df, graders, overwrite=False)

    # Print the updated DataFrame
    print(updated_df)

    # Save the distributed graders to an Excel sheet
    save_distributed_graders(updated_df, pl.Path.cwd())
    print(f'Distributed graders saved to {pl.Path.cwd()/ "distributed.xlsx"}')


def save_distributed_graders(d: pd.DataFrame, folder: pl.Path):
    """
    Saves the distributed graders to separate Excel sheets.

    Args:
    d (pd.DataFrame): The DataFrame containing the student information.
    folder (Path): The folder where the Excel sheets will be saved.

    Returns:
    None
    """
    # save the distributed students to a master excel sheet
    if not (folder / "distributed.xlsx").exists():
        d.to_excel(folder / "distributed.xlsx", index=False)
    else:
        choice = input(
            "distributed.xlsx already exists. Do you want to overwrite it? (y/n): "
        )
        if choice.lower() == "y":
            d.to_excel(folder / "distributed.xlsx")
        else:
            print("Operation cancelled.")


if __name__ == "__main__":
    main()
