# -*- coding: utf-8 -*-
"""
Tests Messaging app tasks.
"""
from __future__ import unicode_literals

from django.test import TestCase
from django.test.utils import override_settings

from onadata.apps.messaging.tasks import call_backend_async
from onadata.apps.messaging.tests.test_base import (_create_message,
                                                    _create_user)


class TestTasks(TestCase):
    """
    Test messaging tasks.
    """

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_call_backend_async(self):
        """
        Test messaging call_backend_async task.
        """
        from_user = _create_user('Bob')
        to_user = _create_user('Alice')
        instance = _create_message(from_user, to_user, 'I love oov')

        with self.assertRaises(NotImplementedError):
            call_backend_async.delay(
                backend='onadata.apps.messaging.backends.base.BaseBackend',
                instance_id=instance.id,
                backend_options=None).get()
