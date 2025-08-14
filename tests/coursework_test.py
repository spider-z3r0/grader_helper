

#!/usr/bin/env python

from grader_helper.dependencies import pd


def test_coursework_creation(dummy_coursework_min):
    assert dummy_coursework_min.name == "Test Assignment"
    assert dummy_coursework_min.weight == 50.0


def test_set_classlist_path_with_string


def test_assign_individual_graders(dummy_coursework_min, example_graders_txt, dummy_gradefile):
    dummy_coursework_min.set_students(dummy_gradefile)
    dummy_coursework_min.set_graders(example_graders_txt)
    dummy_coursework_min.assign_graders_individual()

    df = dummy_coursework_min._class_list
    assert "grader" in df.columns
