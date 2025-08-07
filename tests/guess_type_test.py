#!/usr/bin/env python

from grader_helper.helpers import guess_model_type
from grader_helper.models import Course, CourseWork
from grader_helper.dependencies import ym
from io import StringIO

yaml = ym.YAML()
yaml.register_class(Course)
yaml.register_class(CourseWork)


def test_guess_course(dummy_course):
    yaml_str = StringIO()
    yaml = ym.YAML()
    yaml.dump(dummy_course.model_dump(mode='json'), yaml_str)

    yaml_str.seek(0)  # rewind to start
    data_dict = yaml.load(yaml_str)

    guess = guess_model_type(data_dict)
    assert guess is Course


def test_guess_cw(dummy_coursework_min):
    yaml_str = StringIO()
    yaml = ym.YAML()
    yaml.dump(dummy_coursework_min.model_dump(mode='json'), yaml_str)

    yaml_str.seek(0)  # rewind to start
    data_dict = yaml.load(yaml_str)

    guess = guess_model_type(data_dict)
    assert guess is CourseWork
