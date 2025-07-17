
# Grader Helper

Grader Helper is a Python-based tool designed to streamline academic grading workflows for module leaders in the University of Limerick, particularly for assignments hosted on Brightspace. It provides functionality to improve quality-of-life in various areas of assessment administration. 

It's designed to help with managing both specific coursework
 - managing student submissions 
   - renaming student submission folders into UL format (e.g. "Lastname, Firstname (Studentnumber)") and the Brightspace format ("1234-5678 - Lastname Firstname - 01 January 2001 0000 AM") and back again (for reupload to Brightspace).
 - randomly assigning submissions to graders (both group and individual assesments).
 - disrtibuting blank feedback sheets into each students submission folder (named using each students student number)
  
## Key Features

- **Automated Grader Assignment**: Assigns graders to students either individually or in groups.
- **Data Processing**: Extracts student IDs and grades from feedback files and aggregates them into a master dataset.
- **Brightspace Integration**: Imports class lists and handles data in Brightspace-compatible formats.
- **Feedback Management**: Distributes feedback sheets with rubrics to individual student folders.
- **File Organization**: Renames and organizes submission folders for clarity.
- **Score Calculation**: Computes total and weighted scores for modules, including letter grade conversion.

## Installation

### From PyPI

Install the package directly:
```
pip install grader-helper
```

### Using UV

[UV](https://docs.astral.sh/) is an incredibly fast python tool for dependency management in python. See the docs for guides on setting up a project with UV.  

```
uv add grader_helper
```


## Usage

Working on more full documentation - watch this space. 


## Dependencies

Key dependencies:
- `pandas` for data manipulation
- `pathlib` for file path handling
- `xlwings` for Excel file interaction
- `tqdm` for progress bars
- `numpy` for numerical operations
- `openpyxl` for handling Excel files

For a complete list, see `pyproject.toml`.

## Contributing

Contributions are welcome! To get started:
1. Fork the repository.
2. Create a feature branch: `git checkout -b feature-name`.
3. Commit your changes: `git commit -m "Description of changes"`.
4. Push to the branch: `git push origin feature-name`.
5. Create a pull request.

## License

This project is licensed under the MIT License. See `LICENSE` for more details.


# grader_helper

## Next steps

 - Integrate the functionality that allows us to randomly select students from each gradeband and copy them to the moderation folders.
 - Integrate the way of making the departmental gradefile. 
    - I've already got the functions that make the dataframes written, but not any explicit functionality for writing them into the departmental template. 
 - Write full documentation and a sample project (make fake student files)
 - Consider writing it all together into an gui/tui app? 
 - Use pydantic models for data validation and consider rewriting as methods on those classes

