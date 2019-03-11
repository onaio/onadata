# -*- coding=utf-8 -*-
"""
Example local_settings.py used by the Dockerfile.
"""
# this system uses structured settings.py as defined in
# http://www.slideshare.net/jacobian/the-best-and-worst-of-django
#
# this third-level staging file overrides some definitions in staging.py
# You may wish to alter it to agree with your local environment
#

# get most settings from staging_example.py (which in turn, imports from
# settings.py)
import os
import subprocess
import sys

from future.moves.urllib.parse import urljoin

from onadata.settings.common import *  # noqa

# # # now override the settings which came from staging # # # #
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'onadata',
        'USER': 'onadata',
        'PASSWORD': 'onadata',
        'HOST': 'db',
        'PORT': 5432
    }
}

DATABASE_ROUTERS = []  # turn off second database
SLAVE_DATABASES = []

# Make a unique unique key just for testing, and don't share it with anybody.
SECRET_KEY = '~&nN9d`bxmJL2[$HhYE9qAk=+4P:cf3b'

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

INTERNAL_IPS = ['127.0.0.1']

DEBUG = True
CORS_ORIGIN_ALLOW_ALL = True
CHECK_EXPIRED_TEMP_TOKEN = False

# pylint: disable=simplifiable-if-statement
if len(sys.argv) >= 2 and (sys.argv[1] == "test" or sys.argv[1] == "test_all"):
    # This trick works only when we run tests from the command line.
    TESTING_MODE = True
else:
    TESTING_MODE = False

CELERY_BROKER_URL = 'amqp://guest:@queue:5672//'
CELERY_TASK_ALWAYS_EAGER = False
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_CACHE_BACKEND = 'memory'
CELERY_BROKER_CONNECTION_MAX_RETRIES = 2

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

if TESTING_MODE:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'test_media/')  # noqa
    subprocess.call(["rm", "-r", MEDIA_ROOT])
    # need to have TASK_ALWAYS_EAGERY True and BROKER_URL as memory
    # to run tasks immediately while testing
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_RESULT_BACKEND = 'cache'
    CELERY_CACHE_BACKEND = 'memory'
    ENKETO_API_TOKEN = 'abc'
    ENKETO_PROTOCOL = 'https'
    ENKETO_URL = 'https://enketo.ona.io/'
    ENKETO_API_SURVEY_PATH = '/api_v1/survey'
    ENKETO_API_INSTANCE_PATH = '/api_v1/instance'
    ENKETO_PREVIEW_URL = urljoin(ENKETO_URL, ENKETO_API_SURVEY_PATH +
                                 '/preview')
    ENKETO_SINGLE_SUBMIT_PATH = '/api/v2/survey/single/once'
    ENKETO_API_INSTANCE_IFRAME_URL = ENKETO_URL + "api_v1/instance/iframe"
else:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'media/')  # noqa
