# -*- coding: utf-8 -*-
"""
Celery module for onadata.
"""
import os

from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "onadata.settings.common")

app = Celery(__name__)  # pylint: disable=invalid-name

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.broker_transport_options = {"visibility_timeout": 10}


@app.task
def debug_task():
    """A test task"""
    print("Hello!")
    return True
