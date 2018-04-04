"""
Setup file for onadata

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

setup(
    name="onadata",
    version="1.13.1",
    description="Collect Analyze and Share Data!",
    author="Ona Systems Inc",
    author_email="support@ona.io",
    license="Copyright (c) 2014 Ona Systems Inc All rights reserved.",
    project_urls={
        'Source': 'https://github.com/onaio/onadata',
    },
    packages=find_packages(exclude=['docs', 'tests']),
    install_requires=[
        "Django>=1.11<2",
        "django-guardian",
        "django-registration-redux",
        "django-templated-email",
        "django-reversion",
        "django-filter",
        # generic relation
        "django-query-builder",
        "celery",
        "django-celery",
        # cors
        "django-cors-headers",
        "django-debug-toolbar",
        # digest authentication
        "python-digest",
        # oauth2 support
        "django-oauth-toolkit",
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
        "elaphe",
        "httplib2",
        "modilabs-python-utils",
        "numpy",
        "Pillow",
        "python-dateutil",
        "pytz",
        "requests",
        "simplejson",
        "google-api-python-client",
        "uwsgi",
        "flake8",
        "raven",
        "django-activity-stream",
        "paho-mqtt",
    ],
    extras_require={
        ':python_version=="2.7"': [
            'functools32>=3.2.3-2'
        ]
    }
)
