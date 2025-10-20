#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ..dependencies import pd, pl
from datetime import datetime

def find_unsubmitted(df:pd.DataFrame, subs_dir:pl.Path, save=False) -> pd.DataFrame:
    """
        placeholder docs
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            "df must be a pandas dataframe"
            )
    if not 'Student ID' in df.columns:
        raise ValueError(
            "df must have been produced by the grader_helper package. "
            "It can produced by passing the Brightpace grades file to "
            "gh.import_brightspace_classlist(), or by reimporting the completed graderfiles."
            )

    if not subs_dir.is_dir():
        raise TypeError(
            "This function operates on the unzipped folder of student submissions, "
            "please make sure you've downloaded the student submissions from Brightspace "
            "and extracted the archive to a folder."
            )
    if not subs_dir.exists():
        raise ValueError(
            f"Could not find the folder at {subs_dir.absolute()}"
            "This function operates on the unzipped folder of student submissions, "
            "please make sure you've downloaded the student submissions from Brightspace "
            "and extracted the archive to a folder."
            )

    # capture the sub_directory names
    dirs = [dir.name for dir in subs_dir.iterdir() if dir.is_dir()]
    if len(dirs) == 0:
        raise ValueError(
                "It seems there are no student submission folders in {subs_dir.name}"
        )
    first = str(dirs[0])
    # check the format of the folder names
    # if they haven't been renamed yet 
    match first:
        case first if ' - ' in first:
            ids = [i.split(' - ')[1].split(' ')[0] for i in dirs]
        case first if '(' in first:
            ids = [i.split('(')[1].strip(')').strip() for i in dirs]
        case _: 
            raise ValueError(
                "This subs_dir must be a folder of student submissions downloaded from Brightspace."
                "You can check for missing submissions either before or after renaming the folders, "
                "Please make sure you are calling this function on the submissions folder."
        )


    df['Student ID'] = df['Student ID'].astype(str)

    out = df[~df['Student ID'].isin(ids)]

    if save:
        try:
            now = datetime.today()
            out.to_csv(subs_dir.parent/f'unsubmitted_{now.strftime("%Y-%m-%d")}.csv')
        except Exception as e:
            print(f"{e}")

    return df[~df['Student ID'].isin(ids)]
