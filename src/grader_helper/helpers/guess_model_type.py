#!/usr/bin/env python

from grader_helper.models import Course, CourseWork
from grader_helper.dependencies import pl


def main():
    print(f"\n Running {pl.Path(__file__).name}")


def guess_model_type(data: dict) -> type[Course] | type[CourseWork]:
    if not isinstance(data, dict):
        raise TypeError(
            "'data' must be a dictionary mapping of either the Course of CourseWork model.")

    if 'module_leader' in data.keys():
        return Course
    elif 'due_date' in data.keys():
        return CourseWork
    else:
        raise ValueError("'data' must be a dictionary mapping of either the Course of CourseWork model. "
                         "Please check the contents of the dict yout are passing.")


if __name__ == "__main__":
    main()
