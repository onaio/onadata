"""
Module containing test for the MessagingStatsViewset (api/v1/stats/messaging)
"""

import json
from datetime import datetime, timedelta, timezone

from django.test import RequestFactory

from onadata.apps.api.viewsets.messaging_stats_viewset import MessagingStatsViewSet
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.messaging.constants import (
    EXPORT_CREATED,
    SUBMISSION_CREATED,
    SUBMISSION_DELETED,
    XFORM,
)
from onadata.apps.messaging.serializers import send_message


class TestMessagingStatsViewSet(TestBase):
    """Test /api/v1/stats/messaging endpoint"""

    def setUp(self):
        super().setUp()
        self._create_user_and_login()
        self.factory = RequestFactory()
        self.extra = {"HTTP_AUTHORIZATION": f"Token {self.user.auth_token}"}
        self.view = MessagingStatsViewSet.as_view({"get": "list"})

    def test_filters(self):
        """
        Test to ensure that the `verb` and `timestamp` filters
        work as expected
        """
        self._publish_transportation_form()
        self._make_submissions()

        request = self.factory.get(
            "/",
            data={
                "target_type": "xform",
                "target_id": self.xform.id,
                "group_by": "day",
                "timestamp__day": datetime.now().day,  # .astimezone(timezone.utc).day,
            },
            **self.extra,
        )
        response = self.view(request)

        # Expect streaming response
        self.assertEqual(response.status_code, 200)
        returned_data = json.loads(
            "".join([i.decode("utf-8") for i in response.streaming_content])
        )
        self.assertEqual(
            returned_data,
            [
                {
                    "group": str(datetime.now().astimezone(timezone.utc).date()),
                    "submission_created": self.xform.instances.count(),
                }
            ],
        )

        request = self.factory.get(
            "/",
            data={
                "target_type": "xform",
                "target_id": self.xform.id,
                "group_by": "day",
                "timestamp__day": datetime.now().astimezone(timezone.utc).day + 1,
            },
            **self.extra,
        )
        response = self.view(request)

        # Expect streaming response
        self.assertEqual(response.status_code, 200)
        returned_data = json.loads(
            "".join([i.decode("utf-8") for i in response.streaming_content])
        )
        self.assertEqual(
            returned_data,
            [],
        )

        request = self.factory.get(
            "/",
            data={
                "target_type": "xform",
                "target_id": self.xform.id,
                "group_by": "day",
                "verb": SUBMISSION_CREATED,
            },
            **self.extra,
        )
        response = self.view(request)

        # Expect streaming response
        self.assertEqual(response.status_code, 200)
        returned_data = json.loads(
            "".join([i.decode("utf-8") for i in response.streaming_content])
        )
        self.assertEqual(
            returned_data,
            [
                {
                    "group": str(datetime.now().astimezone(timezone.utc).date()),
                    "submission_created": self.xform.instances.count(),
                }
            ],
        )

        request = self.factory.get(
            "/",
            data={
                "target_type": "xform",
                "target_id": self.xform.id,
                "group_by": "day",
                "verb": SUBMISSION_DELETED,
            },
            **self.extra,
        )
        response = self.view(request)

        # Expect streaming response
        self.assertEqual(response.status_code, 200)
        returned_data = json.loads(
            "".join([i.decode("utf-8") for i in response.streaming_content])
        )
        self.assertEqual(
            returned_data,
            [],
        )

    def test_expected_responses(self):
        """
        Test to ensure that the expected responses are returned
        """
        self._publish_transportation_form()
        self._make_submissions()

        request = self.factory.get(
            "/",
            data={
                "target_type": "xform",
                "target_id": self.xform.id,
                "group_by": "day",
            },
            **self.extra,
        )
        response = self.view(request)

        # Expect streaming response
        self.assertEqual(response.status_code, 200)
        returned_data = json.loads(
            "".join([i.decode("utf-8") for i in response.streaming_content])
        )
        self.assertEqual(
            returned_data,
            [
                {
                    "group": str(datetime.now().astimezone(timezone.utc).date()),
                    "submission_created": self.xform.instances.count(),
                }
            ],
        )

    def test_required_fields(self):
        """
        Test that errors are raised when required fields are not passed
        """
        self._publish_transportation_form()
        self._make_submissions()

        # Bad request response when `target_type` is missing
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {"detail": "Parameter 'target_type' is missing."}
        )

        # Bad request response when `target_id` is missing
        request = self.factory.get("/", data={"target_type": "xform"}, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"detail": "Parameter 'target_id' is missing."})

        # Bad request response when `group_by` is missing or invalid
        request = self.factory.get(
            "/", data={"target_type": "xform", "target_id": self.xform.id}, **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data["detail"]),
            "Parameter 'group_by' is missing.",
        )

        request = self.factory.get(
            "/",
            data={
                "target_type": "xform",
                "target_id": self.xform.id,
                "group_by": "_submission_time",
            },
            **self.extra,
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            str(response.data["detail"]),
            "Parameter 'group_by' is not valid.",
        )

    def test_export_created_differentiation_by_type(self):
        """
        Test that export_created events are differentiated by export type
        (csv, xlsx, etc.) in the response
        """
        self._publish_transportation_form()

        # Calculate dates
        today = datetime.now(timezone.utc)
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        # Create export_created messages with different export types on today
        # CSV exports
        send_message(
            instance_id=2,
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=EXPORT_CREATED,
            message_description="csv",
        )

        # XLSX exports
        send_message(
            instance_id=3,
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=EXPORT_CREATED,
            message_description="xlsx",
        )

        # SAV export
        send_message(
            instance_id=6,
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=EXPORT_CREATED,
            message_description="sav",
        )

        # Create submission_created events on the same day as exports
        send_message(
            instance_id=[7, 8],
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=SUBMISSION_CREATED,
        )

        # Create submission_created events on yesterday
        m = send_message(
            instance_id=[9, 10, 11],
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=SUBMISSION_CREATED,
        )
        m.timestamp = yesterday
        m.save()

        # Create another CSV export from two days ago
        m = send_message(
            instance_id=12,
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=EXPORT_CREATED,
            message_description="csv",
        )
        # Update timestamp to two days ago
        m.timestamp = two_days_ago
        m.save()

        request = self.factory.get(
            "/",
            data={
                "target_type": "xform",
                "target_id": self.xform.id,
                "group_by": "day",
            },
            **self.extra,
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        returned_data = json.loads(
            "".join([i.decode("utf-8") for i in response.streaming_content])
        )

        # Expected data with multiple days
        expected = [
            {
                "group": str(today.date()),
                "export_created_csv": 1,
                "export_created_xlsx": 1,
                "export_created_sav": 1,
                "submission_created": 2,
            },
            {
                "group": str(yesterday.date()),
                "submission_created": 3,
            },
            {
                "group": str(two_days_ago.date()),
                "export_created_csv": 1,
            },
        ]

        self.assertEqual(returned_data, expected)

    def test_export_created_with_include_user(self):
        """
        Test that export_created events are differentiated by both export type
        and user when include_user=true
        """
        self._publish_transportation_form()
        # Create another user
        self._create_user_and_login(username="bob", password="bob")

        # Calculate dates
        today = datetime.now(timezone.utc)
        yesterday = today - timedelta(days=1)

        # Bob creates SAV export on today
        send_message(
            instance_id=2,
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=EXPORT_CREATED,
            message_description="sav",
        )

        # Bob creates CSV export on today
        send_message(
            instance_id=3,
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=EXPORT_CREATED,
            message_description="csv",
        )

        # Bob creates XLSX export on today
        send_message(
            instance_id=7,
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=EXPORT_CREATED,
            message_description="xlsx",
        )

        # Bob creates submissions on today
        send_message(
            instance_id=[8, 9],
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=SUBMISSION_CREATED,
        )

        # Bob creates submissions on yesterday
        m = send_message(
            instance_id=[10, 11, 12, 13],
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=SUBMISSION_CREATED,
        )
        # Update timestamp to yesterday
        m.timestamp = yesterday
        m.save()

        request = self.factory.get(
            "/",
            data={
                "target_type": "xform",
                "target_id": self.xform.id,
                "group_by": "day",
                "include_user": "true",
            },
            **self.extra,
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        returned_data = json.loads(
            "".join([i.decode("utf-8") for i in response.streaming_content])
        )

        # Expected data with user grouping and multiple days
        expected = [
            {
                "group": str(today.date()),
                "username": "bob",
                "export_created_csv": 1,
                "export_created_xlsx": 1,
                "export_created_sav": 1,
                "submission_created": 2,
            },
            {
                "group": str(yesterday.date()),
                "username": "bob",
                "submission_created": 4,
            },
        ]

        self.assertEqual(returned_data, expected)

    def test_export_created_accurate_count(self):
        """
        Test that export_created events show accurate count of exports
        (not number of action records)
        """
        self._publish_transportation_form()

        # Create multiple export messages with different batch sizes
        send_message(
            instance_id=[1, 2, 3],
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=EXPORT_CREATED,
            message_description="csv",
        )

        send_message(
            instance_id=[4, 5],
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=EXPORT_CREATED,
            message_description="csv",
        )

        request = self.factory.get(
            "/",
            data={
                "target_type": "xform",
                "target_id": self.xform.id,
                "group_by": "day",
            },
            **self.extra,
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        returned_data = json.loads(
            "".join([i.decode("utf-8") for i in response.streaming_content])
        )

        # Should show total count of 5 (3 + 2), not 2 action records
        self.assertEqual(len(returned_data), 1)
        result = returned_data[0]
        self.assertEqual(result["export_created_csv"], 5)

    def test_export_created_without_description(self):
        """
        Test that export_created events without descriptions are handled gracefully
        """
        self._publish_transportation_form()

        # Create export message without description
        send_message(
            instance_id=[1, 2],
            target_id=self.xform.id,
            target_type=XFORM,
            user=self.user,
            message_verb=EXPORT_CREATED,
            message_description=None,
        )

        request = self.factory.get(
            "/",
            data={
                "target_type": "xform",
                "target_id": self.xform.id,
                "group_by": "day",
            },
            **self.extra,
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        returned_data = json.loads(
            "".join([i.decode("utf-8") for i in response.streaming_content])
        )

        # Should fall back to plain "export_created" without type suffix
        self.assertEqual(len(returned_data), 1)
        result = returned_data[0]
        self.assertIn("export_created", result)
        self.assertEqual(result["export_created"], 2)
