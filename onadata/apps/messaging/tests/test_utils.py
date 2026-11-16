"""
Tests messaging app utils
"""

from unittest.mock import patch

from django.contrib.auth.models import Group
from django.test.utils import override_settings

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.messaging.constants import SUBMISSION_DELETED
from onadata.apps.messaging.serializers import send_message
from onadata.apps.messaging.utils import get_available_targets


class TestMessagingUtils(TestBase):
    """
    Test messaging utils
    """

    def test_unsupported_target_has_no_availability_fallback(self):
        """An unconfigured model cannot silently bypass availability checks."""
        with self.assertRaises(KeyError):
            get_available_targets(Group)

    @override_settings(NOTIFICATION_ID_LIMIT=10)
    @patch("onadata.apps.messaging.serializers.MessageSerializer")
    def test_send_message_payload_chunking(self, message_serializer_mock):
        """
        Test that the send_message function chunks the message
        payload if list of IDs goes over limit
        """

        def is_valid():
            return True

        message_serializer_mock.is_valid.side_effect = is_valid
        self._create_user_and_login()
        self._publish_transportation_form()
        instance_ids = [num for num in range(0, 20)]
        send_message(
            instance_ids, self.xform.id, "xform", self.user, SUBMISSION_DELETED
        )
        self.assertTrue(message_serializer_mock.called)
        self.assertEqual(message_serializer_mock.call_count, 2)
