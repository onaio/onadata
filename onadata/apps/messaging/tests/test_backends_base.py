# -*- coding: utf-8 -*-
"""
Tests Messaging backends base module.
"""
from __future__ import unicode_literals

from django.test import TestCase

from onadata.apps.messaging.backends.base import call_backend
from onadata.apps.messaging.tests.test_base import (_create_message,
                                                    _create_user)


class TestBackendsBase(TestCase):
    """
    Test messaging backends base functions.
    """

    def test_call_backend(self):
        """
        Test messaging call_backend task.
        """
        from_user = _create_user('Bob')
        to_user = _create_user('Alice')
        instance = _create_message(from_user, to_user, 'I love oov')

        with self.assertRaises(NotImplementedError):
            call_backend('onadata.apps.messaging.backends.base.BaseBackend',
                         instance.id, {'HOST': 'localhost'})
