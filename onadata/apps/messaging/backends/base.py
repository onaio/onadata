# -*- coding: utf-8 -*-
"""
Messaging notification base module.
"""
from __future__ import unicode_literals

from django.utils.module_loading import import_string

from actstream.models import Action
from multidb.pinning import use_master


@use_master
def call_backend(backend, instance_id, backend_options=None):
    """
    Call notification backends like MQTT to send messages
    """
    try:
        instance = Action.objects.get(pk=instance_id)
    except Action.DoesNotExist:
        pass
    else:
        backend_class = import_string(backend)
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
