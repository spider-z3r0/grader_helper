from typing import List
import pandas as pd
import numpy as np


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
    updated_df = distribute_graders_individual(df, graders, overwrite=False)

    # Print the updated DataFrame
    print(updated_df)


def distribute_graders_individual(
    d: pd.DataFrame, l: List, overwrite=False, save=False
):
    """
    This assigns graders to each student in the dataframe.
    If the 'grader' column already exists and overwrite is False, the distribution is not changed.

    Args:
    d (pd.DataFrame): The DataFrame containing student information.
    l (list): The list of graders.
    overwrite (bool): If True, overwrite the existing grader distribution. Default is False.

    Returns:
    pd.DataFrame: The updated DataFrame with the grader distribution.
    """
    if "grader" in d.columns and not overwrite:
        user_input = input(
            "grader distribution already exists. Do you want to overwrite? (yes/no): "
        )
        if user_input.lower() != "yes":
            print("Existing grader distribution retained.")
            return d

    repeated_graders = np.repeat(l, np.ceil(len(d) / len(l)))
    shuffled_graders = np.random.choice(repeated_graders, len(d), replace=False)
    d["grader"] = shuffled_graders

    if d.loc[d["grader"] == "grader"].shape[0] >= 1:
        print(
            f"{d.loc[d['grader'] == 'grader'].shape[0]} students were not assigned a grader."
        )
        print("Please check the list of graders for empty strings and try agian.")
        return None
    else:
        return d


if __name__ == "__main__":
    main()
