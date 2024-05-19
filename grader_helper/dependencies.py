#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
This script is just housing the dependencies for the other scripts in the src folder.
It is not intended to be run as a script.

'''

import logging as log
import pandas as pd
import numpy as np  
import xlwings as xw
import pathlib as pl
from shutil import copy2, copytree
import re
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor 
import pythoncom
import os
