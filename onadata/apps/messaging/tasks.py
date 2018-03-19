# -*- coding: utf-8 -*-
"""
Messaging tasks
"""
from __future__ import unicode_literals

from celery import task

from onadata.apps.messaging.backends.base import call_backend


@task(ignore_result=True)
def call_backend_async(backend, instance_id, backend_options=None):
    """
    Task to send messages to notification backeds such as MQTT
    """
    call_backend(backend, instance_id, backend_options)
