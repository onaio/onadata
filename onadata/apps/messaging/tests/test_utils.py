"""
Tests messaging app utils
"""

from unittest.mock import MagicMock, patch

from django.test.utils import override_settings

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.messaging.constants import SUBMISSION_DELETED
from onadata.apps.messaging.tasks import send_message


class TestMessagingUtils(TestBase):
    """
    Test messaging utils
    """

    @override_settings(NOTIFICATION_ID_LIMIT=10)
    @patch("onadata.apps.messaging.tasks.MessageSerializer")
    def test_send_message_payload_chunking(self, message_serializer_mock):
        """
        Test that the send_message function chunks the message
        payload if list of IDs goes over limit
        """

        mock_instance = MagicMock()
        mock_instance.is_valid.return_value = True
        message_serializer_mock.return_value = mock_instance

        self._create_user_and_login()
        self._publish_transportation_form()
        instance_ids = [num for num in range(0, 20)]
        send_message(
            instance_ids, self.xform.id, "xform", self.user.id, SUBMISSION_DELETED
        )
        self.assertTrue(message_serializer_mock.called)
        self.assertEqual(message_serializer_mock.call_count, 2)
