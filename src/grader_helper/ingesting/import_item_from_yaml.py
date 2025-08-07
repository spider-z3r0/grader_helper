#!/usr/bin/env python
"""Helpers for importing model instances from YAML definitions.

The :func:`import_item_from_yaml` function reads a YAML file and constructs a
``Course`` or ``CourseWork`` model based on the file's contents.
"""

from grader_helper.models import Course, CourseWork
from grader_helper.dependencies import ym, pl
from grader_helper.helpers import guess_model_type


def main():
    print(f"running {pl.Path(__file__)}")


def import_item_from_yaml(p: pl.Path) -> Course | CourseWork:
    """Load a model instance from a YAML configuration file.

    Parameters
    ----------
    p:
        Path to the YAML file that describes either a ``Course`` or
        ``CourseWork`` instance.

    Returns
    -------
    Course | CourseWork
        A ``Course`` or ``CourseWork`` model built from the YAML contents.

    Raises
    ------
    FileNotFoundError
        If ``p`` does not exist.
    ValueError
        If the YAML file is empty or contains invalid YAML content.
    TypeError
        If the model type cannot be determined from the YAML data.
    """
    if not p.exists():
        raise FileNotFoundError(f"YAML file {p} does not exist.")

    yaml = ym.YAML()
    try:
        with open(p, "r") as conf:
            details = yaml.load(conf)
    except ym.YAMLError as e:
        raise ValueError(f"Invalid YAML content in {p}.") from e

    if not details:
        raise ValueError(f"YAML file {p} was empty or invalid.")

    guess = guess_model_type(details)

    match guess:
        case _ if guess is Course:
            return Course(**details)
        case _ if guess is CourseWork:
            return CourseWork(**details)
        case _:
            raise TypeError(f"Unknown model type guessed: {guess}")


if __name__ == "__main__":
    main()
