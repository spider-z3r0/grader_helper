from conftest import resources_dir
#!/usr/bin/env python

from grader_helper import (write_item_to_yaml, Course, import_item_from_yaml)


def test_course_creation(dummy_course):
    assert dummy_course.name == "Intro to Testing"
    assert len(dummy_course.coursework) == 0


def test_update_course_coursework(dummy_course, dummy_coursework):
    dummy_course.set_coursework(dummy_coursework)
    assert len(dummy_course.coursework) == 1
    assert dummy_course.coursework[0].name == "Dummy Assignment"
