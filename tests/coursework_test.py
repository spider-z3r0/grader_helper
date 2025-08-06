#!usr/bin/env python
from dependencies import pd


def test_coursework_creation(dummy_coursework):
    assert dummy_coursework.name == "Dummy Assignment"
    assert dummy_coursework.weight == 50.0


def test_ingest_graders_from_file(dummy_coursework, example_graders_txt):
    dummy_coursework.set_graders(example_graders_txt)
    assert isinstance(dummy_coursework.graders, list)
    assert len(dummy_coursework.graders) != 0
    assert dummy_coursework.graders[0] == 'KOM'
    assert dummy_coursework.graders[-1] == 'DEF'


def test_set_students_from_gradesfile(dummy_coursework, dummy_gradefile):
    dummy_coursework.set_students(dummy_gradefile)
    assert isinstance(
        dummy_coursework.students, pd.DataFrame)
    assert 'last_name' in dummy_coursework.students.columns
    assert (
        dummy_coursework.students.columns[-2] == dummy_coursework.name.lower().replace(
            ' ', '_').strip()
    )


def test_assign_individual_graders(dummy_coursework, example_graders_txt, dummy_gradefile):
    dummy_coursework.set_students(dummy_gradefile)
    dummy_coursework.set_graders(example_graders_txt)
    dummy_coursework.assign_graders_individual()
    assert 'grader' in dummy_coursework.students.columns


def test_chained_graderd_assignment(dummy_coursework, example_graders_txt, dummy_gradefile):
    dummy_coursework.set_students(dummy_gradefile).set_graders(
        example_graders_txt).assign_graders_individual()
    assert 'grader' in dummy_coursework.students.columns
