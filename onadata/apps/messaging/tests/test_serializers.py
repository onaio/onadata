# -*- coding: utf-8 -*-
"""
Tests for messaging serializers.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from onadata.apps.messaging.constants import EXPORT_CREATED, XFORM
from onadata.apps.messaging.serializers import send_message

User = get_user_model()


class TestSendMessage(TestCase):
    """
    Test send_message function.
    """

    def setUp(self):
        self.user = User.objects.create(username="testuser")

    def test_send_message_with_custom_message_large_list(self):
        """
        Test send_message uses custom message for large lists (exceeding limit)
        """
        with patch("onadata.apps.messaging.serializers.settings") as mock_settings:
            mock_settings.NOTIFICATION_ID_LIMIT = 2
            with patch(
                "onadata.apps.messaging.serializers.MessageSerializer"
            ) as mock_serializer:
                mock_instance = MagicMock()
                mock_instance.is_valid.return_value = True
                mock_serializer.return_value = mock_instance

                send_message(
                    instance_id=[1, 2, 3],
                    target_id=100,
                    target_type=XFORM,
                    user=self.user,
                    message_verb=EXPORT_CREATED,
                    message_description="imported_via_csv",
                )

                # Verify MessageSerializer was called with custom message
                # Should be called twice: [1,2] and [3]
                self.assertEqual(mock_serializer.call_count, 2)
                for call in mock_serializer.call_args_list:
                    # call[1] is kwargs dict, data is a key
                    self.assertEqual(
                        call[1]["data"]["message"],
                        '{"id": [3], "description": "imported_via_csv"}',
                    )

    def test_send_message_with_default_message(self):
        """
        Test send_message uses default JSON message when custom message is None
        """
        with patch(
            "onadata.apps.messaging.serializers.MessageSerializer"
        ) as mock_serializer:
            mock_instance = MagicMock()
            mock_instance.is_valid.return_value = True
            mock_serializer.return_value = mock_instance

            send_message(
                instance_id=1,
                target_id=100,
                target_type=XFORM,
                user=self.user,
                message_verb=EXPORT_CREATED,
            )

            # Verify MessageSerializer was called with JSON message
            call_args = mock_serializer.call_args
            self.assertEqual(call_args[1]["data"]["message"], '{"id": [1]}')
            mock_instance.save.assert_called_once()

    def test_send_message_with_list_of_ids(self):
        """
        Test send_message handles list of IDs correctly
        """
        with patch(
            "onadata.apps.messaging.serializers.MessageSerializer"
        ) as mock_serializer:
            mock_instance = MagicMock()
            mock_instance.is_valid.return_value = True
            mock_serializer.return_value = mock_instance
            send_message(
                instance_id=[1, 2, 3],
                target_id=100,
                target_type=XFORM,
                user=self.user,
                message_verb=EXPORT_CREATED,
            )

            # Verify MessageSerializer was called with JSON message containing all IDs
            call_args = mock_serializer.call_args
            self.assertEqual(call_args[1]["data"]["message"], '{"id": [1, 2, 3]}')
            mock_instance.save.assert_called_once()
