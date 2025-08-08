

#!/usr/bin/env python

from grader_helper.dependencies import pd


def test_coursework_creation(dummy_coursework_min):
    assert dummy_coursework_min.name == "Test Assignment"
    assert dummy_coursework_min.weight == 50.0


def test_ingest_graders_from_file(dummy_coursework_min, example_graders_txt):
    dummy_coursework_min.set_graders(example_graders_txt)
    assert isinstance(dummy_coursework_min.graders, list)
    assert len(dummy_coursework_min.graders) != 0
    # Keep your expected sentinel values from the resource file
    assert dummy_coursework_min.graders[0] == "KOM"
    assert dummy_coursework_min.graders[-1] == "DEF"


def test_set_students_from_gradesfile(dummy_coursework_min, dummy_gradefile):
    # sets class_list_path and loads into the private DataFrame
    dummy_coursework_min.set_students(dummy_gradefile)

    # Access private attr in tests is fine to verify behavior
    df = dummy_coursework_min._class_list
    assert isinstance(df, pd.DataFrame)

    # Coursework-specific blank column should exist (don’t rely on exact position)
    cw_col = dummy_coursework_min.name.lower().replace(" ", "_").strip()
    assert cw_col in df.columns


def test_assign_individual_graders(dummy_coursework_min, example_graders_txt, dummy_gradefile):
    dummy_coursework_min.set_students(dummy_gradefile)
    dummy_coursework_min.set_graders(example_graders_txt)
    dummy_coursework_min.assign_graders_individual()

    df = dummy_coursework_min._class_list
    assert "grader" in df.columns


def test_chained_graderd_assignment(dummy_coursework_min, example_graders_txt, dummy_gradefile):
    # chaining still works because set_students returns self
    dummy_coursework_min.set_students(dummy_gradefile) \
                        .set_graders(example_graders_txt) \
                        .assign_graders_individual()

    df = dummy_coursework_min._class_list
    assert "grader" in df.columns
