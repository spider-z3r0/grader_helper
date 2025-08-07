#!/usr/bin/env python


from grader_helper.models import Course
from grader_helper.dependencies import ym, pl


def main():
    print(f"running {pl.Path(__file__)}")


def import_item_from_yaml(p: pl.Path) -> Course:
    if not p.exists():
        raise ValueError(f"the path {p} doesn't exist")
    try:
        yaml = ym.YAML()
        with open(p, "r") as conf:
            details = yaml.load(conf)

        course = Course(**details)

        return course
    except Exception as e:
        raise ValueError("exception from tryblock")


if __name__ == "__main__":
    main()
