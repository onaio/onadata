# -*- coding: utf-8 -*-
"""
Tests Messaging app signals.
"""
from __future__ import unicode_literals

from django.test import TestCase
from django.test.utils import override_settings

from actstream.models import Action
from mock import patch

from onadata.apps.messaging.signals import messaging_backends_handler


class TestSignals(TestCase):
    """
    Test messaging signals.
    """

    # pylint: disable=invalid-name
    @override_settings(
        NOTIFICATION_BACKENDS={
            'mqtt': {
                'BACKEND': 'onadata.apps.messaging.backends.base.BaseBackend'
            },
        },
        MESSAGING_ASYNC_NOTIFICATION=True)
    @patch('onadata.apps.messaging.signals.call_backend_async.delay')
    def test_messaging_backends_handler_async(self, call_backend_async_mock):
        """
        Test messaging backends handler function.
        """
        messaging_backends_handler(Action, instance=Action(id=9), created=True)
        self.assertTrue(call_backend_async_mock.called)
        call_backend_async_mock.assert_called_with(
            'onadata.apps.messaging.backends.base.BaseBackend', 9, None)

    @override_settings(NOTIFICATION_BACKENDS={
        'mqtt': {
            'BACKEND': 'onadata.apps.messaging.backends.base.BaseBackend'
        },
    })
    @patch('onadata.apps.messaging.signals.call_backend')
    def test_messaging_backends_handler(self, call_backend_mock):
        """
        Test messaging backends handler function.
        """
        messaging_backends_handler(Action, instance=Action(id=9), created=True)
        self.assertTrue(call_backend_mock.called)
        call_backend_mock.assert_called_with(
            'onadata.apps.messaging.backends.base.BaseBackend', 9, None)
