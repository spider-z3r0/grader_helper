#!/usr/bin/env python

"""
This module handles writing a Module to yaml for easy ingesting and picking up where we left off.
"""

from grader_helper.models import Course, CourseWork
from grader_helper.dependencies import pl, ym
import sys


def main():
    print(f"running {pl.Path(__file__).name}")

    test_dict = {
        "name": "test_course",
        "code": "0001",
        "root": pl.Path(__file__).parent.parent.parent.parent / 'tests/output',
        "model_leader": "John Smith",
        "year": "2025(26)",  # This will be in the format 20xx(xy)
        "internal_moderator": "Joan Smith",
        "ready": False,
        "handbook": None,
        "coursework": None,
        "departmental_gradefile": None,
        "classlist": None,
        "completed": False
    }

    test_course = Course(**test_dict)
    print(test_course.model_dump_json(indent=2))

    write_item_to_yaml(test_course)

    yaml = ym.YAML()
    yaml.register_class(Course)
    yaml.dump(test_course.model_dump(mode='json'), sys.stdout)


def write_item_to_yaml(c: Course | CourseWork, update: bool = False) -> None:
    path = pl.Path(f"{c.root / c.name}_config.yaml")
    if path.exists() and not update:
        raise ValueError(
            f"{path.name} already exists "
            "if you wish to overwrite this file please call this function again "
            "with 'update' set to 'True'."
        )
    yaml = ym.YAML()
    try:
        yaml.register_class(Course)
        with open(f"{c.root / c.name.replace(' ', '_')}_config.yaml", 'w') as f:
            yaml.dump(c.model_dump(mode='json'), f)
    except Exception as e:
        raise ValueError(
            "could not write Course configuration to yaml"
            f"the exception was raised"
            f"{e}"
        )


if __name__ == "__main__":
    main()
