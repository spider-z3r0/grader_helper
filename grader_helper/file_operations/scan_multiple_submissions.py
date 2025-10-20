#!/usr/bin/env python

import pathlib as pl
import datetime as dt

def main():
    folder = pl.Path(
        r"C:\Users\Kevin.OMalley\OneDrive - University of Limerick\Teaching\grader_helper\example_project\data\Week 1 Lab workbook submission  Download 14 October 2025 320 PM"
        )
    scan_multiple_subs(folder=folder)

def make_sub_date(s: str, fmt="%d %B %Y %I:%M %p") -> dt.datetime:
    # Brightspace: "13 September 2025 310 PM" or "13 September 2025 3:10 PM"
    day, month, year, time, ap = s.strip().split()

    if ":" not in time:              # e.g., "310" -> "3:10"
        time = time[:-2] + ":" + time[-2:]

    return dt.datetime.strptime(f"{day} {month} {year} {time} {ap}", fmt)

    


def scan_multiple_subs(folder: pl.Path) -> dict[str,dt.datetime]:

    """scan folder for multiple submissions by the same person
    """
    if not folder.is_dir():
        raise RuntimeError(
                f"{folder.name} is not a directory/folder, please make sure you are calling "
                "this function on the unzipped folder you downloaded from Brightspace "
                "which contains the student submissions"
        )

    f_names = [
        (f.name.strip().split(' - ')[1], make_sub_date(f.name.strip().split(' - ')[-1])) for f in folder.iterdir() if f.is_dir()
            ]

    temp_dict = {}


    for (id, date) in f_names:
        if id in temp_dict.keys():
            temp_dict[id].append(date)
        else:
            temp_dict[id] = [date]
    
    duplicates = {k:v for (k,v) in temp_dict.items() if len(v) > 1}


    return duplicates







if __name__ == '__main__':
    main()


