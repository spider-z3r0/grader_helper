#!/usr/bin/env python

from grader_helper import (write_item_to_yaml, Course, import_item_from_yaml)


def test_write_course_yaml_creates_file(dummy_course, tmp_path):
    # Redirect course root to temp directory
    dummy_course.root = tmp_path

    # Call the function
    write_item_to_yaml(dummy_course)

    # Build expected file path
    expected_path = tmp_path / \
        f"{dummy_course.name.replace(' ', '_')}_config.yaml"

    # Assert the file was created
    assert expected_path.exists()


def test_create_course_from_yaml(resources_dir):
    path = resources_dir / "test_course_config.yaml"
    test_course = import_item_from_yaml(path)
    print(test_course.name)
    assert isinstance(test_course, Course)
