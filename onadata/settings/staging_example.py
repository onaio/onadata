# -*- coding: utf-8 -*-
"""
Example staging module.
"""
import os
import subprocess
import sys

from onadata.settings.common import *  # noqa pylint: disable=W0401,W0614

DEBUG = True
TEMPLATES[0]["OPTIONS"]["debug"] = DEBUG  # noqa
TEMPLATE_STRING_IF_INVALID = ""

# see: http://docs.djangoproject.com/en/dev/ref/settings/#databases

# postgres
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "formhub_dev",
        "USER": "formhub_dev",
        "PASSWORD": "12345678",
        "HOST": "localhost",
    },
}

# TIME_ZONE = 'UTC'

SECRET_KEY = "please replace this text"

# This trick works only when we run tests from the command line.
TESTING_MODE = len(sys.argv) >= 2 and (
    sys.argv[1] == "test" or sys.argv[1] == "test_all"
)

if TESTING_MODE:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, "test_media/")  # noqa
    subprocess.call(["rm", "-r", MEDIA_ROOT])  # noqa
    # need to have CELERY_TASK_ALWAYS_EAGER True and BROKER_BACKEND as memory
    # to run tasks immediately while testing
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_RESULT_BACKEND = "cache"
    CELERY_CACHE_BACKEND = "memory"
    ENKETO_API_TOKEN = "abc"
else:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, "media/")  # noqa

if PRINT_EXCEPTION and DEBUG:  # noqa
    MIDDLEWARE += ("utils.middleware.ExceptionLoggingMiddleware",)  # noqa
