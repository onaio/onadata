# -*- coding: utf-8 -*-
"""
Messaging notification base module.
"""
from __future__ import unicode_literals

from importlib import import_module

from actstream.models import Action


def call_backend(backend, instance_id, backend_options=None):
    """
    Call notification backends like MQTT to send messages
    """
    try:
        instance = Action.objects.get(pk=instance_id)
    except Action.DoesNotExist:
        pass
    else:
        backend_module = '.'.join(backend.split('.')[:-1])
        backend_class = backend.split('.')[-1:].pop()
        backend_module = import_module(backend_module)
        backend_class = getattr(backend_module, backend_class)
        backend_class(options=backend_options).send(instance)


class BaseBackend(object):  # pylint: disable=too-few-public-methods
    """
    Base class for notification backends
    """

    def __init__(self, options=None):
        pass

    def send(self, instance):  # pylint: disable=unused-argument
        """
        This method actually sends the message
        """
        raise NotImplementedError()
