# -*- coding: utf-8 -*-
"""
Tests Messaging app implementation.
"""
from __future__ import unicode_literals

from actstream.models import Action
from django.test import TestCase
from django.test.utils import override_settings

from onadata.apps.messaging.signals import messaging_backends_handler


class TestSignals(TestCase):
    """
    Test messaging signals.
    """

    @override_settings(NOTIFICATION_BACKENDS=[
        'onadata.apps.messaging.backends.base.BaseBackend'])
    def test_messaging_backends_handler(self):
        """
        Test messaging backends handler function.
        """
        with self.assertRaises(NotImplementedError):
            messaging_backends_handler(Action, instance=Action(), created=True)
