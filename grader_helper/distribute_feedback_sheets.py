import re
import pathlib as pl
from shutil import copy2


def distribute_feedback_sheets(subs_folder: pl.Path, rubric_name: pl.Path) -> None:
    """
    Copies a copy of the rubric to the feedback folder of each student who submitted an assignment.

    Parameters
    ----------
    subs_folder : pathlib.Path
        The folder where the student submissions are stored.
    rubric_name : pathlib.Path
        The name of the rubric file to be attached.

    Returns
    -------
    None
    """
    # Assuming 'subs' and 'root' are defined Path objects
    pattern = re.compile(r"\((\d+)\)")

    if not rubric_name.exists():
        raise FileNotFoundError(f"{rubric_name} does not exist.")

    for folder in subs_folder.iterdir():
        if not folder.is_dir():
            print(f"{folder} is not a directory.")
        else:
            # Extract student ID from folder name
            match = pattern.search(folder.name)
            if match:
                student_id = match.group(1)
                target_file = folder / f"Feedback sheet {student_id}.xlsx"

                # Check if the file already exists to prevent overwriting
                if not target_file.exists():
                    copy2(rubric_name, target_file)
                    print(f"Copied rubric to {target_file}")
                else:
                    print(
                        f"The file {target_file} already exists. Skipping copy to prevent overwrite."
                    )
            else:
                print(f"No student ID found in {folder.name}.")
