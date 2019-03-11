# flake8: noqa
# this preset is used for automated testing of formhub
from __future__ import absolute_import

from future.moves.urllib.parse import urljoin

from .common import *  # nopep8

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'onadata_test',
        'USER': 'postgres',
        'PASSWORD': '',
        'HOST': '127.0.0.1'
    }
}

SLAVE_DATABASES = []

SECRET_KEY = 'mlfs33^s1l4xf6a36$0#j%dd*sisfoi&)&4s-v=91#^l01v)*j'

JWT_SECRET_KEY = 'thesecretkey'
JWT_ALGORITHM = 'HS256'

if len(sys.argv) >= 2 and (sys.argv[1] == "test" or sys.argv[1] == "test_all"):
    # This trick works only when we run tests from the command line.
    TESTING_MODE = True
else:
    TESTING_MODE = False

if TESTING_MODE:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'test_media/')
    subprocess.call(["rm", "-r", MEDIA_ROOT])
    # need to have CELERY_TASK_ALWAYS_EAGER True and BROKER_BACKEND as memory
    # to run tasks immediately while testing
    CELERY_BROKER_URL = "memory://"
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
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'media/')

PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.MD5PasswordHasher',
)

DEBUG = False
TEMPLATES[0]['OPTIONS']['debug'] = DEBUG
MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # 'django.middleware.locale.LocaleMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'onadata.libs.utils.middleware.HTTPResponseNotAllowedMiddleware',
)

VERIFIED_KEY_TEXT = 'ALREADY_ACTIVATED'
