# -*- coding: utf-8 -*-
"""
Django settings module or use on GitHub actions.
"""
# flake8: noqa
# this preset is used for automated testing of onadata
from __future__ import absolute_import

from onadata.settings.common import *  # noqa pylint: disable=W0401,W0614

# database settings
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": "onadata",
        "USER": "onadata",
        "PASSWORD": "onadata",
        "HOST": "localhost",
    }
}

SLAVE_DATABASES = []

SECRET_KEY = "mlfs33^s1l4xf6a36$0#j%dd*sisfoi&)&4s-v=91#^l01v)*j"  # nosec

JWT_SECRET_KEY = "thesecretkey"  # nosec
JWT_ALGORITHM = "HS256"

# This trick works only when we run tests from the command line.
TESTING_MODE = len(sys.argv) >= 2 and (
    sys.argv[1] == "test" or sys.argv[1] == "test_all"
)

if TESTING_MODE:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, "test_media/")
    # subprocess.call(["rm", "-r", MEDIA_ROOT])  # nosec
    # need to have CELERY_TASK_ALWAYS_EAGER True and BROKER_BACKEND as memory
    # to run tasks immediately while testing
    CELERY_BROKER_URL = "memory://"
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_RESULT_BACKEND = "cache"
    CELERY_CACHE_BACKEND = "memory"
    ENKETO_API_TOKEN = "abc"  # nosec
    ENKETO_PROTOCOL = "https"
    ENKETO_URL = "https://enketo.ona.io/"
    ENKETO_API_ALL_SURVEY_LINKS_PATH = "/api_v2/survey/all"
    ENKETO_API_INSTANCE_PATH = "/api_v1/instance"
    ENKETO_SINGLE_SUBMIT_PATH = "/api/v2/survey/single/once"
    ENKETO_API_INSTANCE_IFRAME_URL = ENKETO_URL + "api_v1/instance/iframe"
else:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, "media/")

PASSWORD_HASHERS = ("django.contrib.auth.hashers.MD5PasswordHasher",)

DEBUG = False
TEMPLATES[0]["OPTIONS"]["debug"] = DEBUG
MIDDLEWARE_CLASSES = (
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # 'django.middleware.locale.LocaleMiddleware',
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "onadata.libs.utils.middleware.HTTPResponseNotAllowedMiddleware",
)

VERIFIED_KEY_TEXT = "ALREADY_ACTIVATED"

ODK_TOKEN_FERNET_KEY = "ROsB4T8s1rCJskAdgpTQEKfH2x2K_EX_YBi3UFyoYng="  # nosec
OPENID_CONNECT_PROVIDERS = {}
AUTH_PASSWORD_VALIDATORS = []
