# -*- coding: utf-8 -*-
"""
Messaging signal handlers
"""
from __future__ import unicode_literals

from importlib import import_module

from actstream.models import Action
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

BACKENDS = getattr(settings, 'NOTIFICATION_BACKENDS', [])


@receiver(post_save, sender=Action, dispatch_uid='messaging_backends_handler')
def messaging_backends_handler(sender, **kwargs):  # pylint: disable=W0613
    """
    Handler to send messages to notification backends e.g MQTT.
    """
    created = kwargs.get('created')
    instance = kwargs.get('instance')
    if instance and created:
        for backend in BACKENDS:
            backend_module = '.'.join(backend.split('.')[:-1])
            backend_class = backend.split('.')[-1:].pop()
            backend_module = import_module(backend_module)
            backend_class = getattr(backend_module, backend_class)
            backend_class().send(instance)
