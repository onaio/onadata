"""
Setup file for onadata

Ona is a social enterprise that builds the data infrastructure to drive change.
We believe technology affords new opportunities for governments and development
organizations to be increasingly data driven, collaborative and accountable.
Our goal is never simply to build a great product, but to support great
outcomes.

See:
https://github.com/onaio/onadata
https://ona.io
"""

from setuptools import setup, find_packages

setup(
    name="onadata",
    version="1.13.0",
    description="Collect Analyze and Share Data!",
    author="Ona Systems Inc",
    author_email="support@ona.io",
    license="Copyright (c) 2014 Ona Systems Inc All rights reserved.",
    packages=find_packages(exclude=['docs', 'tests']),
    install_requires=['Django==1.11.11'])
