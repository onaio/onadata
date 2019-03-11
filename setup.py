"""
Setup file for onadata.

Onadata is a Django application that provides APIs for data collection and
aggregation.

It provides:
- ODK aggregate server API
- ODK briefcase API
- REST APIs to interact with data that is used by ona.io

See:
https://github.com/onaio/onadata
https://ona.io
https://opendatakit.org
"""

from setuptools import setup, find_packages

import onadata

setup(
    name="onadata",
    version=onadata.__version__,
    description="Collect Analyze and Share Data!",
    author="Ona Systems Inc",
    author_email="support@ona.io",
    license="Copyright (c) 2014 Ona Systems Inc All rights reserved.",
    project_urls={
        'Source': 'https://github.com/onaio/onadata',
    },
    packages=find_packages(exclude=['docs', 'tests']),
    install_requires=[
        "Django<2",
        "django-guardian",
        "django-registration-redux",
        "django-templated-email",
        "django-reversion",
        "django-filter<2.0",
        "django-nose",
        "django-ordered-model",
        # generic relation
        "django-query-builder",
        "celery",
        "django-celery-results",
        # cors
        "django-cors-headers",
        "django-debug-toolbar",
        # oauth2 support
        "django-oauth-toolkit<1.2",
        "oauth2client",
        "jsonpickle",
        # jwt
        "PyJWT",
        # captcha
        "recaptcha-client",
        # API support
        "djangorestframework",
        "djangorestframework-csv",
        "djangorestframework-gis",
        "djangorestframework-jsonapi",
        "djangorestframework-jsonp",
        "djangorestframework-xml",
        # geojson
        "geojson",
        # tagging
        "django-taggit",
        # database
        "psycopg2>2.7.1",
        "pymongo",
        # sms support
        "dict2xml",
        "lxml",
        # pyxform
        "pyxform",
        # spss
        "savreaderwriter",
        # tests
        "mock",
        "httmock",
        # JSON data type support, keeping it around for previous migration
        "jsonfield<1.0",
        # memcached support
        "pylibmc",
        "python-memcached",
        # docs
        "sphinx",
        "Markdown",
        # others
        "unicodecsv",
        "xlrd",
        "xlwt",
        "openpyxl",
        "dpath",
        "elaphe3",
        "httplib2",
        "modilabs-python-utils",
        "numpy",
        "Pillow",
        "python-dateutil",
        "pytz",
        "requests",
        "requests-mock",
        "simplejson",
        "google-api-python-client",
        "uwsgi",
        "flake8",
        "raven",
        "django-activity-stream",
        "paho-mqtt",
    ],
    dependency_links=[
        'https://github.com/onaio/python-digest/tarball/3af1bd0ef6114e24bf23d0e8fd9d7ebf389845d1#egg=python-digest',  # noqa pylint: disable=line-too-long
        'https://github.com/onaio/django-digest/tarball/eb85c7ae19d70d4690eeb20983e94b9fde8ab8c2#egg=django-digest',  # noqa pylint: disable=line-too-long
        'https://github.com/onaio/django-multidb-router/tarball/9cf0a0c6c9f796e5bd14637fafeb5a1a5507ed37#egg=django-multidb-router',  # noqa pylint: disable=line-too-long
        'https://github.com/onaio/floip-py/tarball/3bbf5c76b34ec49c438a3099ab848870514d1e50#egg=floip',  # noqa pylint: disable=line-too-long
        'https://github.com/onaio/python-json2xlsclient/tarball/62b4645f7b4f2684421a13ce98da0331a9dd66a0#egg=python-json2xlsclient',  # noqa pylint: disable=line-too-long
    ],
    extras_require={
        ':python_version=="2.7"': [
            'functools32>=3.2.3-2'
        ]
    }
)
