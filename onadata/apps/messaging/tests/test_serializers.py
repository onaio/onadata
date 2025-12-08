# -*- coding: utf-8 -*-
"""
Tests for messaging serializers.
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from actstream.models import Action
from rest_framework.test import APIRequestFactory

from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.messaging.constants import EXPORT_CREATED, SUBMISSION_CREATED, XFORM
from onadata.apps.messaging.serializers import MessageSerializer, send_message

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
                    message_verb=SUBMISSION_CREATED,
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


class TestMessageFolding(TestBase):
    """
    Test message folding functionality for imported_via_csv submissions.
    """

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self._create_user_and_login()
        self._publish_transportation_form()
        self.xform_content_type = ContentType.objects.get_for_model(self.xform)

    def test_message_folding_when_ids_below_limit(self):
        """
        Test that messages are folded into an existing action when:
        - An existing Action exists for the XForm
        - The action's verb is SUBMISSION_CREATED
        - The description is 'imported_via_csv'
        - The number of IDs is less than 100 (NOTIFICATION_ID_LIMIT)
        """
        # Create an initial action with the right conditions (50 IDs, below limit)
        ids_list = list(range(1, 51))
        initial_description = json.dumps(
            {"id": ids_list, "description": "imported_via_csv"}
        )
        initial_action = Action.objects.create(
            actor_content_type=self.xform_content_type,
            actor_object_id=self.user.id,
            actor=self.user,
            verb=SUBMISSION_CREATED,
            target_content_type=self.xform_content_type,
            target_object_id=self.xform.pk,
            description=initial_description,
        )

        # Create a new message that should be folded into the existing one
        view_data = {
            "message": json.dumps({"id": 51, "description": "imported_via_csv"}),
            "target_id": self.xform.pk,
            "target_type": XFORM,
            "verb": SUBMISSION_CREATED,
        }
        request = self.factory.post("/messaging", view_data)
        request.user = self.user

        serializer = MessageSerializer(data=view_data, context={"request": request})
        self.assertTrue(serializer.is_valid())
        result = serializer.save()

        # Verify that the same action was returned (folded)
        self.assertEqual(result.id, initial_action.id)

        # Verify that the new submission ID was added to the existing action
        updated_action = Action.objects.get(id=initial_action.id)
        updated_description = json.loads(updated_action.description)
        self.assertEqual(updated_description["description"], "imported_via_csv")
        self.assertIn(51, updated_description["id"])
        self.assertEqual(len(updated_description["id"]), 51)

        # Verify that only one action exists for this xform
        self.assertEqual(
            Action.objects.filter(
                target_content_type=self.xform_content_type,
                target_object_id=self.xform.pk,
            ).count(),
            1,
        )

    def test_no_folding_when_conditions_not_met(self):
        """
        Test that a new action is created (no folding) when conditions are not met:
        - ID count at or above limit (100)
        - Wrong verb (not SUBMISSION_CREATED)
        - Wrong description (not 'imported_via_csv')
        - No existing action
        """
        # Test 1: ID count at limit - should NOT fold
        ids_list = list(range(1, 101))  # 100 IDs at the limit
        initial_description = json.dumps(
            {"id": ids_list, "description": "imported_via_csv"}
        )
        Action.objects.create(
            actor_content_type=self.xform_content_type,
            actor_object_id=self.xform.pk,
            verb=SUBMISSION_CREATED,
            target_content_type=self.xform_content_type,
            target_object_id=self.xform.pk,
            description=initial_description,
        )

        view_data = {
            "message": json.dumps({"id": 101, "description": "imported_via_csv"}),
            "target_id": self.xform.pk,
            "target_type": XFORM,
            "verb": SUBMISSION_CREATED,
        }
        request = self.factory.post("/messaging", view_data)
        request.user = self.user

        serializer = MessageSerializer(data=view_data, context={"request": request})
        self.assertTrue(serializer.is_valid())
        serializer.save()

        # Verify that a new action was created (not folded)
        self.assertEqual(
            Action.objects.filter(
                target_content_type=self.xform_content_type,
                target_object_id=self.xform.pk,
            ).count(),
            2,
        )
