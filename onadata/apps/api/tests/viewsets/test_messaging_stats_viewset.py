"""
Module containing test for the MessagingStatsViewset (api/v1/stats/messaging)
"""

import json
from datetime import datetime, timezone

from django.test import RequestFactory
from onadata.apps.api.viewsets.messaging_stats_viewset import MessagingStatsViewSet
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.messaging.constants import SUBMISSION_CREATED, SUBMISSION_DELETED


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
