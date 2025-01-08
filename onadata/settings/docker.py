# -*- coding: utf-8 -*-
"""
Example settings.py used by the Dockerfile.
"""
# this system uses structured settings.py as defined in http://www.slideshare.net/jacobian/the-best-and-worst-of-django
#
# this third-level staging file overrides some definitions in staging.py
# You may wish to alter it to agree with your local environment
#
# get most settings from staging_example.py (which in turn, imports from settings.py)
import os
import subprocess
import sys

from onadata.settings.common import *  # noqa pylint: disable=W0401,W0614

# # # now override the settings which came from staging # # # #
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("DB_NAME", "onadata"),
        "USER": os.environ.get("DB_USER", "onadata"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "onadata"),
        "HOST": os.environ.get("DB_HOST", "database"),
        "PORT": 5432,
    }
}

DATABASE_ROUTERS = []  # turn off second database
SLAVE_DATABASES = []

# Make a unique unique key just for testing, and don't share it with anybody.
SECRET_KEY = os.environ.get("SECRET_KEY", "~&nN9d`bxmJL2[$HhYE9qAk=+4P:cf3b")  # noqa

CORS_ALLOWED_ORIGINS = ["http://192.168.100.229:3000"]
CORS_ALLOW_ALL_ORIGINS = True
ALLOWED_HOSTS = CORS_ALLOWED_ORIGINS + ["192.168.100.229", "localhost"]

INTERNAL_IPS = ["127.0.0.1"]

DEBUG = True
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = (
    "x-requested-with",
    "content-type",
    "accept",
    "origin",
    "authorization",
    "x-csrftoken",
    "x-csrf-token",
    "cache-control",
    "if-none-match",
    "Authorization",
)
CHECK_EXPIRED_TEMP_TOKEN = True

# pylint: disable=simplifiable-if-statement
if len(sys.argv) >= 2 and (sys.argv[1] == "test" or sys.argv[1] == "test_all"):
    # This trick works only when we run tests from the command line.
    TESTING_MODE = True
else:
    TESTING_MODE = False

REDIS_HOST = os.environ.get("REDIS_HOST", "cache")
CELERY_BROKER_URL = f"redis://{ REDIS_HOST }:6379"
CELERY_RESULT_BACKEND = f"redis://{ REDIS_HOST }:6379"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_CACHE_BACKEND = "memory"
CELERY_BROKER_CONNECTION_MAX_RETRIES = 2

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{ REDIS_HOST }:6379",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}

NOTIFICATION_BACKENDS = {}
# NOTIFICATION_BACKENDS = {
#    "mqtt": {
#        "BACKEND": "onadata.apps.messaging.backends.mqtt.MQTTBackend",
#        "OPTIONS": {
#            "HOST": "notifications",
#            "PORT": 1883,
#            "QOS": 1,
#            "RETAIN": False,
#            "SECURE": False,
#            "TOPIC_BASE": "onadata",
#        },
#    }
# }
FULL_MESSAGE_PAYLOAD = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
# AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
# AWS_STORAGE_BUCKET_NAME = "onadata"
# AWS_DEFAULT_ACL = "private"
# AWS_S3_FILE_OVERWRITE = False
# AWS_S3_SECURE_URLS = True
# AWS_S3_ENDPOINT_URL = "http://192.168.100.229:9000"
# DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"

if TESTING_MODE:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, "test_media/")  # noqa
    subprocess.call(["rm", "-r", MEDIA_ROOT])
    # need to have TASK_ALWAYS_EAGERY True and BROKER_URL as memory
    # to run tasks immediately while testing
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_RESULT_BACKEND = "cache"
    CELERY_CACHE_BACKEND = "memory"
    ENKETO_API_SALT = "3A@a4hurU?4CefrU"
    ENKETO_API_TOKEN = "abc"
    ENKETO_PROTOCOL = "http"
    ENKETO_URL = "http://localhost:8005"
    ENKETO_API_ALL_SURVEY_LINKS_PATH = "/api_v2/survey"
    ENKETO_API_INSTANCE_PATH = "/api_v1/instance"
    ENKETO_SINGLE_SUBMIT_PATH = "/api/v2/survey/single/once"
    ENKETO_API_INSTANCE_IFRAME_URL = ENKETO_URL + "api_v1/instance/iframe"
    NOTIFICATION_BACKENDS = {}
else:
    MEDIA_ROOT = os.path.join(PROJECT_ROOT, "media/")  # noqa

ENKETO_API_ALL_SURVEY_LINKS_PATH = "/api_v2/survey/all"
SUBMISSION_RETRIEVAL_THRESHOLD = 1000
CSV_FILESIZE_IMPORT_ASYNC_THRESHOLD = 100000

PRICING = True
CUSTOM_MAIN_URLS = set()
INSTALLED_APPS += ("pricing",)
CUSTOM_MAIN_URLS.add("pricing.urls")
PROFILE_SERIALIZER = "pricing.serializer.PersonalAccountSerializer"
ORG_PROFILE_SERIALIZER = "pricing.serializer.OrganizationAccountSerializer"
BASE_VIEWSET = "pricing.baseviewset.DefaultBaseViewset"
ZOHO_OAUTH_REFRESH_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
ZOHO_OAUTH_CLIENT_ID = "ZOHO_OAUTH_CLIENT_ID"
ZOHO_OAUTH_CLIENT_SECRET = "ZOHO_OAUTH_CLIENT_SECRET"
ZOHO_OAUTH_CALLBACK_URI = "http://localhost:3000/oauth2callback"
ZOHO_OAUTH_REFRESH_TOKEN = "ZOHO_OAUTH_REFRESH_TOKEN"
PRICING_ZOHO_ENTERPRISE_PLAN_CODES = [
    "209",
    "208",
    "308",
    "007",
    "EP2024-401",
    "EP2024-402",
    "EP2024-403",
    "EP2024-404",
    "EP2024-501",
    "EP2024-502",
    "EP2024-503",
    "EP2024-504",
    "EP2024-601",
    "EP2024-602",
    "EP2024-603",
    "EP2024-604",
]
PRICING_ZOHO_PRO_PLAN_CODES = [
    "ONA-203",
    "ONA-205",
    "310",
    "305",
    "210",
    "405",
    "312",
    "406",
    "408",
    "407",
    "409",
    "410",
    "411",
    "PP2024-201",
    "PP2024-202",
    "PP2024-203",
]
PRICING_ZOHO_STANDARD_PLAN_CODES = [
    "ONA-202",
    "ONA-206",
    "109",
    "302",
    "301",
    "306",
    "303",
    "304",
    "309",
    "401",
    "402",
    "403",
    "404",
    "SP2024-101",
    "SP2024-102",
    "SP2024-103",
]

# update to point to pk of the new plans
ORG_ACCOUNT_ID = 22
PERSONAL_ACCOUNT_ID = 19
PRICING_CURRENT_PRO_PLAN = "pro-2024-10"
PRICING_CURRENT_STANDARD_PLAN = "standard-2024-10"
PRICING_CURRENT_FREE_PLAN = "free-2024-01"

PRICING_FREE_PLANS = ["community", "free", "free-2017-01", "free-2024-01"]
PRICING_STANDARD_PLANS = [
    "standard",
    "standard-2017-01",
    "standard-2024-01",
    "standard-2024-10",
]
PRICING_PRO_PLANS = ["pro", "pro-2017-01", "pro-2024-01", "pro-2024-10"]

PRICING_LIMIT_ENABLED = False
PRICING_API_LIMIT_ENABLED = False
PRICING_NO_ACCOUNT_BEHAVIOUR = "default"
PRICING_COUNT_API_CALLS = False
PRICING_STANDARD_PLAN_FEATURES = [
    "filtered_datasets",
    "merged_datasets",
    "third_party_intergrations",
    "submission_reviews",
    "entity_datasets",
]
PRICING_PRO_PLAN_FEATURES = PRICING_STANDARD_PLAN_FEATURES + ["webhooks"]
PRICING_ENTERPRISE_PLAN_FEATURES = PRICING_PRO_PLAN_FEATURES

OAUTH2_PROVIDER_APPLICATION_MODEL = "oauth2_provider.Application"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        }
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
        }
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "django.server": {  # Logs HTTP requests
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {  # Logs database queries
            "level": "DEBUG",
            "handlers": ["console"],
        },
    },
}
