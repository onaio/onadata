# vim: set fileencoding=utf-8
"""
Base Django settings module.
"""
# this system uses structured settings as defined in
# http://www.slideshare.net/jacobian/the-best-and-worst-of-django
#
# this is the base settings.py -- which contains settings common to all
# implementations of ona: edit it at last resort
#
# local customizations should be done in several files each of which in turn
# imports this one.
# The local files should be used as the value for your DJANGO_SETTINGS_MODULE
# environment variable as needed.
import logging
import os
import socket
import sys
from importlib import reload

from celery.signals import after_setup_logger
from django.core.exceptions import SuspiciousOperation
from django.utils.log import AdminEmailHandler

# setting default encoding to utf-8
if sys.version[0] == "2":
    reload(sys)
    sys.setdefaultencoding("utf-8")

CURRENT_FILE = os.path.abspath(__file__)
PROJECT_ROOT = os.path.realpath(os.path.join(os.path.dirname(CURRENT_FILE), "../"))
PRINT_EXCEPTION = False

TEMPLATED_EMAIL_TEMPLATE_DIR = "templated_email/"

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)
MANAGERS = ADMINS


DEFAULT_FROM_EMAIL = "noreply@ona.io"
SHARE_PROJECT_SUBJECT = "{} Ona Project has been shared with you."
SHARE_ORG_SUBJECT = "{}, You have been added to {} organisation."
DEFAULT_SESSION_EXPIRY_TIME = 21600  # 6 hours
DEFAULT_TEMP_TOKEN_EXPIRY_TIME = 21600  # 6 hours

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = "America/New_York"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-us"

LANGUAGES = (
    ("fr", "Français"),
    ("en", "English"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("km", "ភាសាខ្មែរ"),
    ("ne", "नेपाली"),
    ("nl", "Nederlands"),
    ("zh", "中文"),
)

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = "http://localhost:8000/media/"

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = os.path.join(PROJECT_ROOT, "static")

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = "/static/"

# Enketo URL
ENKETO_PROTOCOL = "https"
ENKETO_URL = "https://enketo.ona.io/"
ENKETO_API_ALL_SURVEY_LINKS_PATH = "/api_v2/survey/all"
ENKETO_API_INSTANCE_PATH = "/api_v2/instance"
ENKETO_API_TOKEN = ""
ENKETO_API_INSTANCE_IFRAME_URL = ENKETO_URL + "api_v2/instance/iframe"
ENKETO_API_SALT = "secretsalt"
VERIFY_SSL = True
ENKETO_AUTH_COOKIE = "__enketo"
ENKETO_META_UID_COOKIE = "__enketo_meta_uid"
ENKETO_META_USERNAME_COOKIE = "__enketo_meta_username"

# Login URLs
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/login_redirect/"

# URL prefix for admin static files -- CSS, JavaScript and images.
# Make sure to use a trailing slash.
# Examples: "http://foo.com/static/admin/", "/static/admin/".
ADMIN_MEDIA_PREFIX = "/static/admin/"

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(PROJECT_ROOT, "libs/templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "csp.context_processors.nonce",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
                "onadata.apps.main.context_processors.google_analytics",
                "onadata.apps.main.context_processors.site_name",
            ],
        },
    },
]

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

MIDDLEWARE = (
    "onadata.libs.profiling.sql.SqlTimingMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # 'django.middleware.locale.LocaleMiddleware',
    "onadata.libs.utils.middleware.LocaleMiddlewareWithTweaks",
    "django.middleware.csrf.CsrfViewMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "onadata.libs.utils.middleware.HTTPResponseNotAllowedMiddleware",
    "onadata.libs.utils.middleware.OperationalErrorMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
)

X_FRAME_OPTIONS = "SAMEORIGIN"

LOCALE_PATHS = (os.path.join(PROJECT_ROOT, "onadata.apps.main", "locale"),)

ROOT_URLCONF = "onadata.apps.main.urls"
USE_TZ = True

# needed by guardian
ANONYMOUS_DEFAULT_USERNAME = "AnonymousUser"

INSTALLED_APPS = (
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.admin",
    "django.contrib.admindocs",
    "django.contrib.gis",
    "registration",
    # "django_nose",
    "django_digest",
    "corsheaders",
    "oauth2_provider",
    "rest_framework",
    "rest_framework.authtoken",
    "taggit",
    "onadata.apps.logger",
    "onadata.apps.viewer",
    "onadata.apps.main",
    "onadata.apps.restservice",
    "onadata.apps.api",
    "guardian",
    "onadata.apps.sms_support",
    "onadata.libs",
    "reversion",
    "actstream",
    "onadata.apps.messaging.apps.MessagingConfig",
    "django_filters",
    "oidc",
)

OAUTH2_PROVIDER = {
    # this is the list of available scopes
    "SCOPES": {
        "read": "Read scope",
        "write": "Write scope",
        "groups": "Access to your groups",
    },
    "OAUTH2_VALIDATOR_CLASS": "onadata.libs.authentication.MasterReplicaOAuth2Validator",  # noqa
}

OPENID_CONNECT_VIEWSET_CONFIG = {
    "REDIRECT_AFTER_AUTH": "http://localhost:3000",
    "USE_SSO_COOKIE": True,
    "SSO_COOKIE_DATA": "email",
    "JWT_SECRET_KEY": "thesecretkey",
    "JWT_ALGORITHM": "HS256",
    "SSO_COOKIE_MAX_AGE": None,
    "SSO_COOKIE_DOMAIN": "localhost",
    "USE_AUTH_BACKEND": False,
    "AUTH_BACKEND": "",  # Defaults to django.contrib.auth.backends.ModelBackend # noqa
    "USE_RAPIDPRO_VIEWSET": False,
}

MSFT_OAUTH_ENDPOINT = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
OPENID_CONNECT_AUTH_SERVERS = {
    "microsoft": {
        "AUTHORIZATION_ENDPOINT": MSFT_OAUTH_ENDPOINT,
        "CLIENT_ID": "client_id",
        "JWKS_ENDPOINT": "https://login.microsoftonline.com/common/discovery/v2.0/keys",
        "SCOPE": "openid profile",
        "TOKEN_ENDPOINT": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "END_SESSION_ENDPOINT": "http://localhost:3000",
        "REDIRECT_URI": "http://localhost:8000/oidc/msft/callback",
        "RESPONSE_TYPE": "id_token",
        "RESPONSE_MODE": "form_post",
        "USE_NONCES": True,
    }
}

DEFAULT_MODEL_SERIALIZER_CLASS = "rest_framework.serializers.HyperlinkedModelSerializer"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",  # noqa
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 9,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
    {
        "NAME": "onadata.libs.utils.validators.PreviousPasswordValidator",
    },
]
REST_FRAMEWORK = {
    # Use hyperlinked styles by default.
    # Only used if the `serializer_class` attribute is not set on a view.
    "DEFAULT_MODEL_SERIALIZER_CLASS": DEFAULT_MODEL_SERIALIZER_CLASS,
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "onadata.libs.authentication.DigestAuthentication",
        "onadata.libs.authentication.TempTokenAuthentication",
        "onadata.libs.authentication.EnketoTokenAuthentication",
        "oauth2_provider.contrib.rest_framework.OAuth2Authentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework_jsonp.renderers.JSONPRenderer",
        "rest_framework_csv.renderers.CSVRenderer",
    ),
    "DEFAULT_THROTTLE_CLASSES": ["onadata.libs.throttle.RequestHeaderThrottle"],
    "DEFAULT_THROTTLE_RATES": {"header": "100/minute"},
}

SWAGGER_SETTINGS = {
    "exclude_namespaces": [],  # List URL namespaces to ignore
    "api_version": "1.0",  # Specify your API's version (optional)
    "enabled_methods": [  # Methods to enable in UI
        "get",
        "post",
        "put",
        "patch",
        "delete",
    ],
}

CORS_ORIGIN_ALLOW_ALL = False
CORS_ALLOW_CREDENTIALS = True
CORS_ORIGIN_WHITELIST = ("http://dev.ona.io",)
CORS_URLS_ALLOW_ALL_REGEX = (r"^/api/v1/osm/.*$",)

USE_THOUSAND_SEPARATOR = True

COMPRESS = True

# extra data stored with users
AUTH_PROFILE_MODULE = "onadata.apps.main.UserProfile"

# case insensitive usernames
AUTHENTICATION_BACKENDS = (
    "onadata.apps.main.backends.ModelBackend",
    "guardian.backends.ObjectPermissionBackend",
)

# Settings for Django Registration
ACCOUNT_ACTIVATION_DAYS = 1


def skip_suspicious_operations(record):
    """Prevent django from sending 500 error
    email notifications for SuspiciousOperation
    events, since they are not true server errors,
    especially when related to the ALLOWED_HOSTS
    configuration

    background and more information:
    http://www.tiwoc.de/blog/2013/03/django-prevent-email-notification-on-susp\
    iciousoperation/
    """
    if record.exc_info:
        exc_value = record.exc_info[1]
        if isinstance(exc_value, SuspiciousOperation):
            return False
    return True


# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s"
            + " %(process)d %(thread)d %(message)s"
        },
        "simple": {"format": "%(levelname)s %(message)s"},
        "profiler": {"format": "%(levelname)s %(asctime)s %(message)s"},
        "sql": {
            "format": "%(levelname)s %(process)d %(thread)d"
            + " %(time)s seconds %(message)s %(sql)s"
        },
        "sql_totals": {
            "format": "%(levelname)s %(process)d %(thread)d %(time)s seconds"
            + " %(message)s %(num_queries)s sql queries"
        },
    },
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
        # Define filter for suspicious urls
        "skip_suspicious_operations": {
            "()": "django.utils.log.CallbackFilter",
            "callback": skip_suspicious_operations,
        },
    },
    "handlers": {
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false", "skip_suspicious_operations"],
            "class": "django.utils.log.AdminEmailHandler",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "stream": sys.stdout,
        },
        "audit": {
            "level": "DEBUG",
            "class": "onadata.libs.utils.log.AuditLogHandler",
            "formatter": "verbose",
            "model": "onadata.apps.main.models.audit.AuditLog",
        },
        # 'sql_handler': {
        #     'level': 'DEBUG',
        #     'class': 'logging.StreamHandler',
        #     'formatter': 'sql',
        #     'stream': sys.stdout
        # },
        # 'sql_totals_handler': {
        #     'level': 'DEBUG',
        #     'class': 'logging.StreamHandler',
        #     'formatter': 'sql_totals',
        #     'stream': sys.stdout
        # }
    },
    "loggers": {
        "django.request": {
            "handlers": ["mail_admins", "console"],
            "level": "DEBUG",
            "propagate": True,
        },
        "console_logger": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
        "audit_logger": {"handlers": ["audit"], "level": "DEBUG", "propagate": True},
        # 'sql_logger': {
        #     'handlers': ['sql_handler'],
        #     'level': 'DEBUG',
        #     'propagate': True
        # },
        # 'sql_totals_logger': {
        #     'handlers': ['sql_totals_handler'],
        #     'level': 'DEBUG',
        #     'propagate': True
        # }
    },
}

# PROFILE_API_ACTION_FUNCTION is used to toggle profiling a viewset's action
PROFILE_API_ACTION_FUNCTION = False
PROFILE_LOG_BASE = "/tmp/"


def configure_logging(logger, **kwargs):
    """
    Add AdminEmailHandler to the logger
    """
    admin_email_handler = AdminEmailHandler()
    admin_email_handler.setLevel(logging.ERROR)
    logger.addHandler(admin_email_handler)


after_setup_logger.connect(configure_logging)

GOOGLE_STEP2_URI = "http://ona.io/gwelcome"
GOOGLE_OAUTH2_CLIENT_ID = "REPLACE ME"
GOOGLE_OAUTH2_CLIENT_SECRET = "REPLACE ME"  # noqa

THUMB_CONF = {
    "large": {"size": 1280, "suffix": "-large"},
    "medium": {"size": 640, "suffix": "-medium"},
    "small": {"size": 240, "suffix": "-small"},
}
# order of thumbnails from largest to smallest
THUMB_ORDER = ["large", "medium", "small"]
DEFAULT_IMG_FILE_TYPE = "jpg"

# celery
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_IGNORE_RESULT = False
CELERY_TASK_TRACK_STARTED = True
CELERY_IMPORTS = ("onadata.libs.utils.csv_import",)


CSV_FILESIZE_IMPORT_ASYNC_THRESHOLD = 100000  # Bytes
GOOGLE_SHEET_UPLOAD_BATCH = 1000
ZIP_REPORT_ATTACHMENT_LIMIT = 5242880000  # 500 MB in Bytes

# duration to keep zip exports before deletion (in seconds)
ZIP_EXPORT_COUNTDOWN = 3600  # 1 hour

# number of records on export or CSV import before a progress update
EXPORT_TASK_PROGRESS_UPDATE_BATCH = 1000
EXPORT_TASK_LIFESPAN = 6  # six hours

# default content length for submission requests
DEFAULT_CONTENT_LENGTH = 10000000

# TEST_RUNNER = "django_nose.NoseTestSuiteRunner"
# NOSE_ARGS = ["--with-fixture-bundling", "--nologcapture", "--nocapture"]

# fake endpoints for testing
TEST_HTTP_HOST = "testserver.com"
TEST_USERNAME = "bob"

# specify the root folder which may contain a templates folder and a static
# folder used to override templates for site specific details
TEMPLATE_OVERRIDE_ROOT_DIR = None

# Use 1 or 0 for multiple selects instead of True or False for csv, xls exports
BINARY_SELECT_MULTIPLES = False

# Use 'n/a' for empty values by default on csv exports
NA_REP = "n/a"

if isinstance(TEMPLATE_OVERRIDE_ROOT_DIR, str):
    # site templates overrides
    TEMPLATES[0]["DIRS"] = [
        os.path.join(PROJECT_ROOT, TEMPLATE_OVERRIDE_ROOT_DIR, "templates"),
    ] + TEMPLATES[0]["DIRS"]
    # site static files path
    STATICFILES_DIRS += (
        os.path.join(PROJECT_ROOT, TEMPLATE_OVERRIDE_ROOT_DIR, "static"),
    )

# Set wsgi url scheme to HTTPS
os.environ["wsgi.url_scheme"] = "https"

SUPPORTED_MEDIA_UPLOAD_TYPES = [
    "audio/mp3",
    "audio/mpeg",
    "audio/wav",
    "audio/x-m4a",
    "image/jpeg",
    "image/png",
    "image/svg+xml",
    "text/csv",
    "text/json",
    "video/3gpp",
    "video/mp4",
    "application/json",
    "application/geo+json",
    "application/pdf",
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.\
     presentation",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/zip",
]

CSV_ROW_IMPORT_ASYNC_THRESHOLD = 100
SEND_EMAIL_ACTIVATION_API = False
METADATA_SEPARATOR = "|"

PARSED_INSTANCE_DEFAULT_LIMIT = 1000000
PARSED_INSTANCE_DEFAULT_BATCHSIZE = 1000

PROFILE_SERIALIZER = (
    "onadata.libs.serializers.user_profile_serializer.UserProfileSerializer"
)
ORG_PROFILE_SERIALIZER = (
    "onadata.libs.serializers.organization_serializer.OrganizationSerializer"
)
BASE_VIEWSET = "onadata.libs.baseviewset.DefaultBaseViewset"

path = os.path.join(PROJECT_ROOT, "..", "extras", "reserved_accounts.txt")

EXPORT_WITH_IMAGE_DEFAULT = True
try:
    with open(path, "r", encoding="utf-8") as f:
        RESERVED_USERNAMES = [line.rstrip() for line in f]
except EnvironmentError:
    RESERVED_USERNAMES = []

STATIC_DOC = "/static/docs/index.html"

HOSTNAME = socket.gethostname()

CACHE_CONTROL_DIRECTIVES = {"max_age": 60}
TAGGIT_CASE_INSENSITIVE = True

DEFAULT_CELERY_MAX_RETIRES = 3
DEFAULT_CELERY_INTERVAL_START = 2
DEFAULT_CELERY_INTERVAL_MAX = 0.5
DEFAULT_CELERY_INTERVAL_STEP = 0.5

# email verification
ENABLE_EMAIL_VERIFICATION = False
VERIFIED_KEY_TEXT = "ALREADY_ACTIVATED"

XLS_EXTENSIONS = ["xls", "xlsx"]

CSV_EXTENSION = "csv"

PROJECT_QUERY_CHUNK_SIZE = 5000

# Prevents "The number of GET/POST parameters exceeded" exception
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000000
SECRET_KEY = "mlfs33^s1l4xf6a36$0#j%dd*sisfoi&)&4s-v=91#^l01v)*j"  # noqa

# Time in minutes to lock out user from account
LOCKOUT_TIME = 30 * 60
MAX_LOGIN_ATTEMPTS = 10
SUPPORT_EMAIL = "support@example.com"
FULL_MESSAGE_PAYLOAD = False

# Project & XForm Visibility Settings
ALLOW_PUBLIC_DATASETS = True

# Segment Analytics
ENABLE_SEGMENT_ANALYTICS = False

# Cache xform submission stat by 10 min 10 * 60
XFORM_SUBMISSION_STAT_CACHE_TIME = 600

XFORM_CHARTS_CACHE_TIME = 600

SLAVE_DATABASES = []

# Google Export settings
GOOGLE_FLOW = {
    "web": {
        "client_id": "",
        "project_id": "",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_secret": "",
        "redirect_uris": [],
        "javascript_origins": [],
    }
}
GOOGLE_FLOW_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CSP_CONNECT_SRC = ["https://maps.googleapis.com", "http://localhost:8000"]
CSP_FONT_SRC = [
    "http://netdna.bootstrapcdn.com",
    "https://netdna.bootstrapcdn.com",
    "https://fonts.gstatic.com",
    "data:",
]
CSP_FRAME_SRC = ["http://localhost:8000"]
CSP_IMG_SRC = [
    "'self'",
    "data:",
    "https://netdna.bootstrapcdn.com",
    "https://secure.gravatar.com",
    "https://i1.wp.com",
    "https://code.jquery.com",
    "https://www.dropbox.com",
    "http://localhost:8000",
]
CSP_FRAME_ANCESTORS = ["http://localhost:8000"]
CSP_SCRIPT_SRC = [
    "http://netdna.bootstrapcdn.com",
    "https://netdna.bootstrapcdn.com",
    "https://code.jquery.com",
    "https://www.dropbox.com",
    "https://maps.google.com",
    "https://maps.googleapis.com",
    "http://a.tiles.mapbox.com",
    "http://localhost:8000",
    "'unsafe-eval'",
    "'unsafe-hashes'",
    "'sha256-FCfJFhLnM7FTKq9fzONrOpi3h5WfmVM7YZD94t/7kJo='",
]
CSP_STYLE_SRC = [
    "http://netdna.bootstrapcdn.com",
    "https://netdna.bootstrapcdn.com",
    "http://fonts.googleapis.com/",
    "https://fonts.googleapis.com/",
    "https://www.dropbox.com",
    "http://localhost:8000",
    "'unsafe-hashes'",
    "'sha256-2EA12+9d+s6rrc0rkdIjfmjbh6p2o0ZSXs4wbZuk/tA='",
    "'sha256-SDLD8eJrQqbeuh9+xh0t5VE9P3oV9KP/BhfZq96U2RI='",
    "'sha256-BSTKIYoPCaklkJ9YS/ZVYuKW8e+DG8jZJCXznBzHjgg='",
    "'sha256-giUzRe8cXWgbvRZsDFMO4ElBrNJCUKIBBMl1ks7MJkk='",
    "'sha256-+17AcPK/e5AtiK52Z2vnx3uG3BMzyzRr4Qv5UQsEbDU='",
    "'sha256-nzHi23DROym7G011m6y0DyDd9mvQL2hSJ0Gy3g2T/5Q='",
    "'sha256-48t63itaFWU13cRm0yfVJfhH9W643157SmpC3WbnDQc='",
    "'sha256-0EZqoz+oBhx7gF4nvY2bSqoGyy4zLjNF+SDQXGp/ZrY='",
    "'sha256-aqNNdDLnnrDOnTNdkJpYlAxKVJtLt9CtFLklmInuUAE='",
    "'sha256-1d5RrnRwOR2fbv1b5q8P0cFPTvzxiTVvsdM1Ph/PhrU='",
    "'sha256-pPhsZ7AvE4iZV+LC07MKgTV72ojy2HmGNl+WO1ECv7Q='",
    "'sha256-ZqhM5xQOj0Og/l+8qEbc5F5YYumTdWvc5mtn7dECFuE='",
    "'sha256-RjGsQKP6nC+fFonhmcbTW9dtBRAtlBlOvD8Zhc+Zw/M='",
    "'sha256-h74jMOgFaP1qJMEzRpj+xmoYLGUXUK/Uspo5kFn2CN0='",
    "'sha256-8oXPQtuG9cVYyk8MyeXPRaAkUJimrP5eUgEqnPNdbt0='",
    "'sha256-rDHuGvvtanq4kWMPipd6D0I9Nh8rt53loEiI4P49tI8='",
    "'sha256-D9r+qrbBHq5cfcQoWJY4TmdnhLcji7xqZgud4kXvfAA='",
    "'sha256-5AbUaZkl33hI/zVKBGpMBZa3aQvyaNjs5CA9ND9MIfg='",
    "'sha256-GV1HqzN6rwzXrwy8zJIm7Vra5RQyHzNNM/gqEvm5S3k='",
    "'sha256-wGVBXcVRlwlhnedEI2if7xVXLVzyMb2De9M+DhNvMao='",
    "'sha256-ZqhM5xQOj0Og/l+8qEbc5F5YYumTdWvc5mtn7dECFuE='",
    "'sha256-RjGsQKP6nC+fFonhmcbTW9dtBRAtlBlOvD8Zhc+Zw/M='",
    "'sha256-h74jMOgFaP1qJMEzRpj+xmoYLGUXUK/Uspo5kFn2CN0='",
    "'sha256-8oXPQtuG9cVYyk8MyeXPRaAkUJimrP5eUgEqnPNdbt0='",
    "'sha256-rDHuGvvtanq4kWMPipd6D0I9Nh8rt53loEiI4P49tI8='",
    "'sha256-YFOIjkCvZnAH6R5z1ZjUI/Zgf7uslK5vN80+lsdvYss='",
    "'sha256-cPZkOFZiciU3Z+6kyM3mPJQjEG34QI4YxweiB7n45DQ='",
    "'sha256-47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU='",
    "'sha256-XF40drMRON9Qm0dC4qU9NBiM+fma+ykSbIFIj6R5yb4='",
    "'sha256-VWkG3rR92tqWKwxTi7FGCwo0s3+n19OMWDS2+QN0eiU='",
    "'sha256-lN0P8SqX9AfsOHh/CO1C2+xj4daAI1pykwL4hbWmQ0g='",
    "'sha256-Nb6974zAN1POcePwKBPsyhirac5vQfjPHQ9VvdQ5EMc='",
    "'sha256-28J4mQEy4Sqd0R+nZ89dOl9euh+Y3XvT+VfXD5pOiOE='",
    "'sha256-dlVFva77C91S8Wn24REidEasjl4VM1zOkxe/fwc/jy4='",
    "'sha256-iUo/gR1ZpfvbyyW8pBPaq1LFvqEAnqd/uyPwly6P/SQ='",
    "'sha256-G3Xm3ZS21FJH+2uN2TQz2S2fm1GRbOTSg2Qr3MisSEg='",
    "'sha256-71Gb4W6A/s78onLpjMXIIFjXMB7YFIRd5Z1NKJ+UwHY='",
    "'sha256-52i34Zg+qg4/kTYjnNHEmW8jhzGRxjt77FX9aveiXqw='",
]
CSP_INCLUDE_NONCE_IN = ["script-src", "style-src"]
