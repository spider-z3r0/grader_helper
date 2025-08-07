#!/usr/bin/env python
"""Import model instances from YAML definitions.

Exports :func:`import_item_from_yaml`, which reads a YAML file and returns a
``Course`` or ``CourseWork`` instance based on the file's contents.
"""

from grader_helper.models import Course, CourseWork
from grader_helper.dependencies import ym, pl
from grader_helper.helpers import guess_model_type


def main():
    print(f"running {pl.Path(__file__)}")


def import_item_from_yaml(p: pl.Path) -> Course | CourseWork:
    if not p.exists():
        raise ValueError(f"The path {p} doesn't exist")

    try:
        yaml = ym.YAML()
        with open(p, "r") as conf:
            details = yaml.load(conf)

        if details is None:
            raise ValueError(f"YAML file {p} was empty or invalid.")

        guess = guess_model_type(details)

        match guess:
            case _ if guess is Course:
                return Course(**details)
            case _ if guess is CourseWork:
                return CourseWork(**details)
            case _:
                raise TypeError(f"Unknown model type guessed: {guess}")

    except Exception as e:
        raise ValueError("Failed to import item from YAML") from e


if __name__ == "__main__":
    main()
