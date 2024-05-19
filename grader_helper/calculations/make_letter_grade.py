#!/usr/bin/env python
# -*- coding: utf-8 -*-

def make_letter_grade(score: int|float, fail_threshold: int|float=35) -> str:
    """
    Convert a numerical score to a letter grade.

    Args:
    score (int|float): The numerical score.
    fail_threshold (int): The threshold for failing. Default is 35.
        this is only here for courses that have higher requriemens, such as professional accreditation or professional courses.  

    Returns:
    str: The letter grade.    
    """

    #check that score is an int or float
    if not isinstance(score, (int, float)):
        raise ValueError("Score must be an integer or float.")
    
    #check that fail_threshold is an int or float
    if not isinstance(fail_threshold, (int, float)):
        raise ValueError("Fail threshold must be an integer or float.")
    
    #check that score is between 0 and 100
    if not 0 <= score <= 100:
        raise ValueError("Score must be between 0 and 100.")
    
    # check that fail_threshold is between 0 and 100
    if not 0 <= fail_threshold <= 100:
        raise ValueError("Fail threshold must be between 0 and 100.")
    



    if 10 < score < fail_threshold: # check if score is between 10 and fail_threshold
        return "F"
    elif 35 <= score < 40: # check if score is between 35 and 40
        return "D2"
    elif 40 <= score < 45:
        return "D1"
    elif 45 <= score < 50:
        return "C3"
    elif 50 <= score < 55:
        return "C2"
    elif 55 <= score < 60:
        return "C1"
    elif 60 <= score < 65:
        return "B3"
    elif 65 <= score < 70:
        return "B2"
    elif 70 <= score < 75:
        return "B1"
    elif 75 <= score < 80:
        return "A2"
    elif 80 <= score < 101:
        return "A1"
    else:
        return "NG"