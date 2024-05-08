import pandas as pd
import numpy as np


def main():
    # Example usage
    # Create a MultiIndex DataFrame with group information
    index = pd.MultiIndex.from_tuples(
        [
            ("Group1", "Student1"),
            ("Group1", "Student2"),
            ("Group2", "Student3"),
            ("Group2", "Student4"),
        ],
        names=["Group", "Student"],
    )
    data = {"Score": [90, 85, 88, 92]}
    df = pd.DataFrame(data, index=index)

    # List of graders
    graders = ["Grader1", "Grader2", "Grader3"]

    # Call the function
    updated_df = distribute_graders_groups(
        df, graders, assigned_grader_col="AssignedGrader"
    )

    # Print the updated DataFrame
    print(updated_df)


def distribute_graders_groups(
    d: pd.DataFrame, l: list, assigned_grader_col: str = "grader"
) -> pd.DataFrame:
    """
    Assigns a single grader to each group in a MultiIndex DataFrame.

    Parameters
    ----------
    d : pandas DataFrame
        A MultiIndex DataFrame containing a column named 'Group', where the first level of the MultiIndex corresponds to the group IDs.
    l : list
        A list of grader IDs.
    assigned_grader_col : str, optional
        The name of the column where the assigned grader IDs will be stored (default is 'grader').

    Returns
    -------
    pandas DataFrame
        The input DataFrame with an additional column containing the assigned grader IDs.
    """
    try:
        # Input validation
        if not isinstance(d, pd.DataFrame):
            raise ValueError("Argument 'd' must be a pandas DataFrame.")
        if not isinstance(l, list) or len(l) == 0:
            raise ValueError("Argument 'l' must be a non-empty list of grader IDs.")
        if assigned_grader_col in d.columns:
            raise ValueError(
                f"Column '{assigned_grader_col}' already exists in the DataFrame."
            )

        # Create a dictionary mapping each group to a random grader
        group_grader_map = dict(
            zip(
                d.index.get_level_values(0).unique(),
                np.random.choice(
                    l, len(d.index.get_level_values(0).unique()), replace=True
                ),
            )
        )

        # Assign the randomly chosen grader to each group
        d[assigned_grader_col] = d.index.get_level_values(0).map(group_grader_map)

        return d

    except ValueError as ve:
        print(f"Input error: {ve}")
        return None


if __name__ == "__main__":
    main()
