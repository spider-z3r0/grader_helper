"""Dependencies for the grader_helper package."""

import logging as log
import pandas as pd
import xlwings as wx
import pathlib as pl
from shutil import copy2, copytree
import re
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor 
import pythoncom
import os
