# -*- coding: utf-8 -*-
"""
Celery module for onadata.
"""
from __future__ import absolute_import, unicode_literals

import os

import celery
from django.conf import settings

import raven
from raven.contrib.celery import register_logger_signal, register_signal

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'onadata.settings.common')


class Celery(celery.Celery):
    """
    Celery class that allows Sentry configuration.
    """
    def on_configure(self):  # pylint: disable=method-hidden
        """
        Register Sentry for celery tasks.
        """
        if getattr(settings, 'RAVEN_CONFIG', None):
            client = raven.Client(settings.RAVEN_CONFIG['dsn'])

            # register a custom filter to filter out duplicate logs
            register_logger_signal(client)

            # hook into the Celery error handler
            register_signal(client)


app = Celery(__name__)  # pylint: disable=invalid-name

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
app.conf.broker_transport_options = {'visibility_timeout': 10}


@app.task
def debug_task():
    """A test task"""
    print("Hello!")
    return True
