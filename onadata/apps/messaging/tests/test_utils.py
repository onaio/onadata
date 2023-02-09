"""
Tests messaging app utils
"""
import json
from django.http.request import HttpRequest
from django.test.utils import override_settings
from unittest.mock import patch

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.messaging.serializers import send_message
from onadata.apps.messaging.constants import (
    SUBMISSION_DELETED, FORM_RENAMED
)


class TestMessagingUtils(TestBase):
    """
    Test messaging utils
    """

    @override_settings(NOTIFICATION_ID_LIMIT=10)
    @patch('onadata.apps.messaging.serializers.MessageSerializer')
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
            instance_ids,
            self.xform.id, 'xform', self.user, SUBMISSION_DELETED)
        self.assertTrue(message_serializer_mock.called)
        self.assertEqual(message_serializer_mock.call_count, 2)

    @patch('onadata.apps.messaging.serializers.MessageSerializer')
    def test_custom_message(self, message_serializer_mock):
        def is_valid():
            return True
        message_serializer_mock.is_valid.side_effect = is_valid
        self._create_user_and_login()
        self._publish_transportation_form()
        instance_id = [1]
        custom_message = {
            "old_title": "first title",
            "new_title": "second title"
        }
        send_message(
            instance_id,
            self.xform.id,
            'xform',
            self.user,
            FORM_RENAMED,
            custom_message
        )
        self.assertTrue(message_serializer_mock.called)
        self.assertEqual(message_serializer_mock.call_count, 1)
        request = HttpRequest()
        data = {
                "target_id": self.xform.id,
                "target_type": 'xform',
                "verb": FORM_RENAMED,
                "message": json.dumps({
                    "id": [self.xform.id],
                    "old_title": "first title",
                    "new_title": "second title"
                })
            }
        message_serializer_mock.called_with(
            data=data, context={"request": request}
        )
        
