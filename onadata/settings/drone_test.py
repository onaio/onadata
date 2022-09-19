# -*- coding: utf-8 -*-
"""
Example local_settings.py for use with DroneCI.
"""
# flake8: noqa
# this preset is used for automated testing of formhub
#
import subprocess

from onadata.settings.common import *  # noqa pylint: disable=W0401,W0614

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": "onadata_test",
        "USER": "postgres",
        "PASSWORD": "",
        "HOST": "127.0.0.1",
    }
}

SECRET_KEY = "please replace this text"

PASSWORD_HASHERS = (
    "django.contrib.auth.hashers.MD5PasswordHasher",
    "django.contrib.auth.hashers.SHA1PasswordHasher",
)

DEBUG = True

if PRINT_EXCEPTION and DEBUG:
    MIDDLEWARE += ("utils.middleware.ExceptionLoggingMiddleware",)

# This trick works only when we run tests from the command line.
TESTING_MODE = len(sys.argv) >= 2 and (
    sys.argv[1] == "test" or sys.argv[1] == "test_all"
)

if TESTING_MODE:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, "test_media/")
    subprocess.call(["rm", "-r", MEDIA_ROOT])
    # need to have CELERY_TASK_ALWAYS_EAGER True and BROKER_BACKEND as memory
    # to run tasks immediately while testing
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_RESULT_BACKEND = "cache"
    CELERY_CACHE_BACKEND = "memory"
    ENKETO_API_TOKEN = "abc"
else:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, "media/")
