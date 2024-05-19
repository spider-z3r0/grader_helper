from dependencies import xw, pythoncom, pd, pl
import logging

def extract_studentid_grade(file_path, cell):
    """
    This function extracts the student ID and grade from a feedback file.

    Args:
        file_path (str): The path to the feedback file.
        cell (str): The cell containing the grade in the feedback file.

    Returns:
        Tuple: A tuple containing the student ID and grade.

    Note:
        This function uses the xlwings library to read the Excel file.
        This *has* to be run on grade files that have been saved in the .xlsx format.
    """
    try:
        # Initialize COM environment
        pythoncom.CoInitialize()
        # Open Excel in background
        with xw.App(visible=False) as app:
            # Open the workbook
            workbook = app.books.open(file_path)
            # Access the first worksheet
            sheet = workbook.sheets[0]
            # Extract student ID from filename
            student_id = pl.Path(file_path).stem.split(' ')[-1]  
            # Extract grade from the specified cell
            grade = sheet[cell].value
            # Close the workbook
            workbook.close()
            # Return the student ID and grade
            return student_id, grade
    except FileNotFoundError:
        # Log error if file not found
        logging.error(f"File not found: {file_path}")
        return None
    except IndexError as e:
        # Log error if unable to extract student ID
        logging.error(f"Error extracting student ID from filename '{file_path}': {e}")
        return None
    except Exception as e:
        # Log other errors
        logging.error(f"Error processing file '{file_path}': {e}")
        return None
    finally:
        # Uninitialize COM environment
        pythoncom.CoUninitialize()



