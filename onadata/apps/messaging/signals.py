# -*- coding: utf-8 -*-
"""
Messaging signal handlers
"""
from __future__ import unicode_literals

from actstream.models import Action
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from onadata.apps.messaging.backends.base import call_backend
from onadata.apps.messaging.tasks import call_backend_async


@receiver(post_save, sender=Action, dispatch_uid='messaging_backends_handler')
def messaging_backends_handler(sender, **kwargs):  # pylint: disable=W0613
    """
    Handler to send messages to notification backends e.g MQTT.
    """
    backends = getattr(settings, 'NOTIFICATION_BACKENDS', {})
    as_task = getattr(settings, 'MESSAGING_ASYNC_NOTIFICATION', False)
    created = kwargs.get('created')
    instance = kwargs.get('instance')
    if instance and created:
        for name in backends:
            backend = backends[name]['BACKEND']
            backend_options = backends[name].get('OPTIONS')
            if as_task:
                call_backend_async.delay(backend, instance.id, backend_options)
            else:
                call_backend(backend, instance.id, backend_options)
