# flake8: noqa
from common import *

# this setting file will not work on "runserver" -- it needs a server for
# static files
DEBUG = False

# override to set the actual location for the production static and media
# directories
MEDIA_ROOT = '/var/formhub-media'
STATIC_ROOT = "/srv/formhub-static"
STATICFILES_DIRS = (
    os.path.join(PROJECT_ROOT, "static"),
)
ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)
# your actual production settings go here...,.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'formhub',
        'USER': 'formhub_prod',
        # the password must be stored in an environment variable
        'PASSWORD': os.environ['FORMHUB_PROD_PW'],
        # the server name may be in env
        'HOST': os.environ.get("FORMHUB_DB_SERVER", 'dbserver.yourdomain.org')
    },
    'gis': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'phis',
        'USER': 'staff',
        # the password must be stored in an environment variable
        'PASSWORD': os.environ['PHIS_PW'],
        'HOST': 'gisserver.yourdomain.org'
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Africa/Lagos'

TOUCHFORMS_URL = 'http://localhost:9000/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'mlfs33^s1l4xf6a36$0#j%dd*sisfo6HOktYXB9y'

# Caching
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyLibMCCache',
        'LOCATION': '127.0.0.1:11211',
    }
}

MIDDLEWARE_CLASSES += ('django.middleware.cache.UpdateCacheMiddleware',
                       'django.middleware.common.CommonMiddleware',
                       'django.middleware.cache.FetchFromCacheMiddleware',)

CACHE_MIDDLEWARE_SECONDS = 3600  # 1 hour
CACHE_MIDDLEWARE_KEY_PREFIX = ''

REST_SERVICES_TO_MODULES = {
    'google_sheets': 'google_export.services',
}

REST_SERVICES_TO_SERIALIZERS = {
    'google_sheets': 'google_export.serializers.GoogleSheetsSerializer'
}

CUSTOM_MAIN_URLS = {
    'google_export.urls'
}
