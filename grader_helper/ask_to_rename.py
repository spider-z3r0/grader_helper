def ask_to_rename(folder_name, suggested_name):
    """Prompts user for rename confirmation."""
    response = input(f"Rename '{folder_name}' to '{suggested_name}'? (y/n): ").strip().lower()
    return response == 'y'