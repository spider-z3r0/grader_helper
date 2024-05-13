import re

def is_already_renamed(folder_name):
    """Check if the folder name is already in the expected format."""
    pattern = r"^[A-Z]+, [A-Z]+ \(\d+\)$"
    return re.match(pattern, folder_name) is not None