# -*- coding: utf-8 -*-
"""
Test onadata.libs.utils.cache_tools module.
"""

from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

import onadata.libs.utils.analytics
from onadata.libs.utils.analytics import get_user_id


class TestAnalytics(TestCase):
    def test_get_user_id(self):
        """Test get_user_id()"""
        self.assertEqual(get_user_id(None), 'anonymous')

        # user1 has no email set
        user1 = User(username='abc')
        self.assertEqual(get_user_id(user1), user1.username)

        # user2 has email set
        user2 = User(username='abc', email='abc@example.com')
        self.assertTrue(len(user2.email) > 0)
        self.assertEqual(get_user_id(user1), user2.email)

    @override_settings(SEGMENT_WRITE_KEY='123', HOSTNAME='test-server')
    def test_track(self):
        """Test analytics.track() function.
        """
        segment_mock = MagicMock()
        onadata.libs.utils.analytics.segment_analytics = segment_mock
        onadata.libs.utils.analytics.init_analytics()
        self.assertEqual(segment_mock.write_key, '123')

        user1 = User(username='abc')
        onadata.libs.utils.analytics.track(user1, 'testing track function')
        segment_mock.track.assert_called_with(
            user1.username,
            'test track function',
            {'value': 1},
            {'source': 'test-server'})
