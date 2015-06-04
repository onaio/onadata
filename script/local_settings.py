# get most settings from staging_example.py (which in turn, imports from
# settings.py)
from onadata.settings.common import *  # noqa

# # # now override the settings which came from staging # # # #
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'DB_NAME',
        'USER': 'DB_USER',
        'PASSWORD': 'DB_PASSWORD',
        'HOST': '127.0.0.1',
        'OPTIONS': {
            # note: this option obsolete starting with django 1.6
            'autocommit': True,
        }
    }
}

DATABASE_ROUTERS = []  # turn off second database

# Make a unique unique key just for testing, and don't share it with anybody.
SECRET_KEY = 'SECRET KEY HERE'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

REST_FRAMEWORK = {
    # Use hyperlinked styles by default.
    # Only used if the `serializer_class` attribute is not set on a view.
    'DEFAULT_MODEL_SERIALIZER_CLASS':
    'rest_framework.serializers.HyperlinkedModelSerializer',

    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
        'rest_framework.permissions.DjangoModelPermissions'
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'onadata.libs.authentication.DigestAuthentication',
        'oauth2_provider.ext.rest_framework.OAuth2Authentication',
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'onadata.libs.authentication.TempTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.UnicodeJSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
        'rest_framework.renderers.JSONPRenderer',
        'rest_framework.renderers.XMLRenderer',
        'rest_framework_csv.renderers.CSVRenderer',
    ),
}
OAUTH2_PROVIDER['AUTHORIZATION_CODE_EXPIRE_SECONDS'] = 600
BROKER_TRANSPORT = 'librabbitmq'

DEBUG = True
TEMPLATE_DEBUG = True

ALLOWED_HOSTS = [
    "SERVER IP HERE",
    "DOMAIN NAME HERE",
    "127.0.0.1"
]
CORS_ORIGIN_WHITELIST = (
    "DOMAIN NAME HERE",
    "SERVER IP HERE",
    'localhost:3000',
    'localhost:4000',
    'localhost:8000'
)

# Google credentials
# GOOGLE_SITE_VERIFICATION = ''
# GOOGLE_ANALYTICS_PROPERTY_ID = ''
# GOOGLE_ANALYTICS_DOMAIN = ''

# Flags
TESTING_MODE = False

# Enketo settings
# ENKETO_URL = '127.0.0.1:8005'
# ENKETO_PREVIEW_URL = ENKETO_URL + 'webform/preview'
# ENKETO_API_INSTANCE_IFRAME_URL = ENKETO_URL + 'api_v2/instance/iframe'
# ENKETO_API_TOKEN = 'enketo_api_token'
# ENKETO_API_SURVEY_PATH = '/api_v2/survey'
# ENKETO_PROTOCOL = 'http'

CORS_EXPOSE_HEADERS = (
    'Content-Type', 'Location', 'WWW-Authenticate', 'Content-Language',
)

MEDIA_URL = "http://DOMAIN NAME OR SERVER IP HERE/media/"
MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'media/')
