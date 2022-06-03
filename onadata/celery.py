# -*- coding: utf-8 -*-
"""
Celery module for onadata.
"""
from __future__ import absolute_import, unicode_literals

import os

from django.conf import settings

import celery
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "onadata.settings.common")


class Celery(celery.Celery):
    """
    Celery class that allows Sentry configuration.
    """

    def on_configure(self):  # pylint: disable=method-hidden
        """
        Register Sentry for celery tasks.
        """
        if getattr(settings, "RAVEN_CONFIG", None):
            sentry_sdk.init(
                dsn=settings.RAVEN_CONFIG["dsn"], integrations=[CeleryIntegration()]
            )


app = Celery(__name__)  # pylint: disable=invalid-name

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
app.conf.broker_transport_options = {"visibility_timeout": 10}


@app.task
def debug_task():
    """A test task"""
    print("Hello!")
    return True
