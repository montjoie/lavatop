#!/usr/bin/env python3

"""
    setup.py for lavatop
"""

import os
from setuptools import setup, find_packages

"""
  Utility function to read the README file.
  Used for the long_description.  It's nice, because now 1) we have a top level
  README file and 2) it's easier to type in the README file than to put a raw
  string in below ...
"""
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

NAME = 'lavatop'

setup(
    version='0.99',
    url='https://github.com/montjoie/lavatop.git',
    name=NAME,
    description='LAVA manager in ncurses',
    author='Corentin Labbe',
    author_email='clabbe.montjoie@gmail.com',
    packages=find_packages(),
    scripts=["lavatop.py"],
    license='Apache2',
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    keywords=['lava', 'curses'],
    install_requires=[
        'yaml'
    ],
    python_requires='>=3.6',
)
