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


def test_write_course_yaml_creates_file(dummy_course, tmp_path):
    # Redirect course root to temp directory
    dummy_course.root = tmp_path

    # Call the function
    write_item_to_yaml(dummy_course)

    # Build expected file path
    expected_path = tmp_path / f"{dummy_course.code}_config.yaml"

    # Assert the file was created
    assert expected_path.exists()


def test_create_course_from_yaml(resources_dir):
    path = resources_dir / "0001_config.yaml"
    test_course = import_item_from_yaml(path)
    assert isinstance(test_course, Course)
