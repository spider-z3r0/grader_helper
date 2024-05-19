#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import List
import pathlib as pl


def main():
    print("loading graders...")


def load_graders(file: pl.Path) -> List[str]:
    """
    Loads a list of graders from a text file.

    Parameters
    ----------
    file : pathlib.Path
        The path to the text file containing the list of graders.

    Returns
    -------
    List[str]
        A list of graders.
    """
    with open(file, "r") as f:
        graders = [
            i.strip() for i in f.readlines() if i.strip()
        ]  # Add condition to check if line is not empty
    return graders


if __name__ == "__main__":
    main()
