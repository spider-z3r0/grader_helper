#!/usr/bin/env python

from grader_helper.models import Course, CourseWork
from grader_helper.dependencies import pl


def main():
    print(f"\n Running {pl.Path(__file__).name}")


def guess_model_type(data: dict) -> type[Course] | type[CourseWork]:
    """Infer which model class is represented by ``data``.

    The function inspects the keys of ``data`` to determine whether the
    mapping corresponds to the :class:`Course` or :class:`CourseWork` schema.

    Args:
        data: Dictionary of field names and values describing a model.

    Returns:
        The :class:`Course` or :class:`CourseWork` class depending on the
        detected schema.

    Raises:
        TypeError: If ``data`` is not a dictionary.
        ValueError: If ``data`` does not match either schema.
    """

    if not isinstance(data, dict):
        raise TypeError(
            "'data' must be a dictionary mapping to a Course or CourseWork schema."
        )

    if "module_leader" in data:
        return Course
    if "due_date" in data:
        return CourseWork

    raise ValueError(
        "'data' must map to a Course or CourseWork schema. "
        "Include 'module_leader' for Course data or 'due_date' for CourseWork data."
    )


if __name__ == "__main__":
    main()
