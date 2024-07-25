# -*- coding: utf-8 -*-
"""
Tests Messaging app viewsets.
"""
from __future__ import unicode_literals

from builtins import str as text

from actstream.models import Action
from django.test import TestCase
from django.test.utils import override_settings
from guardian.shortcuts import assign_perm
from rest_framework.test import APIRequestFactory, force_authenticate

from onadata.apps.messaging.tests.test_base import _create_user
from onadata.apps.messaging.viewsets import MessagingViewSet


class TestMessagingViewSet(TestCase):
    """
    Test MessagingViewSet class.
    """

    def setUp(self):
        self.factory = APIRequestFactory()

    @override_settings(FULL_MESSAGE_PAYLOAD=True)
    def _create_message(self, user=None):
        """
        Helper to create a single message
        """
        if not user:
            user = _create_user()
        assign_perm("auth.change_user", user, user)
        view = MessagingViewSet.as_view({"post": "create"})
        data = {
            "message": "Hello World!",
            "target_id": user.pk,
            "target_type": "user",
        }  # yapf: disable
        request = self.factory.post("/messaging", data)
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertDictContainsSubset(data, response.data)
        # ensure that id and timestamp are returned
        self.assertTrue("id" and "timestamp" in [text(x) for x in list(response.data)])
        return response.data

    def test_create_message(self):
        """
        Test POST /messaging adding a new message for a specific form.
        """
        self._create_message()

    def test_target_does_not_exist(self):
        """
        Test POST /messaging adding a new message for a specific form with a
        target that does not exist.
        """
        user = _create_user()
        view = MessagingViewSet.as_view({"post": "create"})
        data = {
            "message": "Hello World!",
            "target_id": 1000000000,
            "target_type": "user",
        }  # yapf: disable
        request = self.factory.post("/messaging", data)
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data["target_id"], "target_id not found")

    def test_delete_message(self):
        """
        Test DELETE /messaging/[pk] deleting a message.
        """
        user = _create_user()
        message_data = self._create_message(user)
        view = MessagingViewSet.as_view({"delete": "destroy"})
        request = self.factory.delete("/messaging/%s" % message_data["id"])
        force_authenticate(request, user=user)
        response = view(request=request, pk=message_data["id"])
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Action.objects.filter(pk=message_data["id"]).exists())

    def test_list_messages(self):
        """
        Test GET /messaging listing of messages for specific forms.
        """
        user = _create_user()
        message_data = self._create_message(user)
        target_id = message_data["target_id"]
        view = MessagingViewSet.as_view({"get": "list"})

        # return data only when a target_type is provided
        request = self.factory.get(
            "/messaging", {"target_type": "user", "target_id": target_id}
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        message_data.pop("target_id")
        message_data.pop("target_type")
        self.assertEqual(len(response.data), 1)
        self.assertEqual(dict(response.data[0]), message_data)

        # returns empty list when a target type does not have any records
        request = self.factory.get(
            "/messaging", {"target_type": "xform", "target_id": target_id}
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        # return status 400 if both target_type and target_id are misssing
        request = self.factory.get("/messaging")
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 400)

        # returns 400 status when a target_id is missing
        request = self.factory.get("/messaging", {"target_type": "user"})
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"detail": "Parameter 'target_id' is missing."})

        # returns 400 status when a target_type is missing
        request = self.factory.get("/messaging", {"target_id": target_id})
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {"detail": "Parameter 'target_type' is missing."}
        )

        # returns 400 status when a target type is not known
        request = self.factory.get(
            "/messaging", {"target_type": "xyz", "target_id": target_id}
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"detail": "Unknown target_type xyz"})

    def test_retrieve_message(self):
        """
        Test GET /messaging/[pk] return a message matching pk.
        """
        user = _create_user()
        message_data = self._create_message(user)
        view = MessagingViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/messaging/{}".format(message_data["id"]))
        force_authenticate(request, user=user)
        response = view(request=request, pk=message_data["id"])
        self.assertEqual(response.status_code, 200)
        message_data.pop("target_id")
        message_data.pop("target_type")
        self.assertDictEqual(response.data, message_data)

    def test_authentication_required(self):
        """
        Test that authentication is required at all endpoints.
        """
        # Test that the list endpoint requires authentication
        view1 = MessagingViewSet.as_view({"get": "list"})
        request1 = self.factory.get(
            "/messaging", {"target_type": "xform", "target_id": 1}
        )
        response1 = view1(request=request1)
        self.assertEqual(response1.status_code, 401)
        self.assertEqual(
            response1.data, {"detail": "Authentication credentials were not provided."}
        )

        # Test that retrieve requires authentication
        view2 = MessagingViewSet.as_view({"get": "retrieve"})
        request2 = self.factory.get("/messaging/1")
        response2 = view2(request=request2, pk=1)
        self.assertEqual(response2.status_code, 401)
        self.assertEqual(
            response2.data, {"detail": "Authentication credentials were not provided."}
        )

        # Test that delete requires authentication
        view3 = MessagingViewSet.as_view({"delete": "destroy"})
        request3 = self.factory.delete("/messaging/5")
        response3 = view3(request=request3, pk=5)
        self.assertEqual(response3.status_code, 401)
        self.assertEqual(
            response3.data, {"detail": "Authentication credentials were not provided."}
        )

        # Test that create requires authentication
        view4 = MessagingViewSet.as_view({"post": "create"})
        data = {
            "message": "Hello World!",
            "target_id": 1,
            "target_type": "user",
        }  # yapf: disable
        request4 = self.factory.post("/messaging", data)
        response4 = view4(request=request4)
        self.assertEqual(response4.status_code, 401)
        self.assertEqual(
            response4.data, {"detail": "Authentication credentials were not provided."}
        )

    def test_create_permissions(self):
        """
        Test that correct permissions are required to create a message.
        """
        user = _create_user()
        data = {
            "message": "Hello World!",
            "target_id": user.pk,
            "target_type": "user",
        }  # yapf: disable
        view = MessagingViewSet.as_view({"post": "create"})

        request = self.factory.post("/messaging", data)
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 403)
        self.assertIn("You do not have permission", response.data["detail"])

        # assign add_user permissions
        assign_perm("auth.change_user", user, user)
        request = self.factory.post("/messaging", data)
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 201)

    def test_retrieve_permissions(self):
        """
        Test that correct permissions are required when retrieving a message
        """
        user = _create_user()
        other_user = _create_user("anotheruser")
        message_data = self._create_message(user)
        view = MessagingViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/messaging/{}".format(message_data["id"]))
        force_authenticate(request, user=other_user)
        response = view(request=request, pk=message_data["id"])
        self.assertEqual(response.status_code, 403)

        request = self.factory.get("/messaging/{}".format(message_data["id"]))
        force_authenticate(request, user=user)
        response = view(request=request, pk=message_data["id"])
        self.assertEqual(response.status_code, 200)

    def test_retrieve_pagination(self):
        user = _create_user()
        count = 0
        while count < 4:
            self._create_message(user)
            count += 1

        view = MessagingViewSet.as_view({"get": "list"})
        request = self.factory.get(
            "/messaging", data={"target_type": "user", "target_id": user.pk}
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data), 4)

        # Test that the pagination query params paginate the responses
        request = self.factory.get(
            "/messaging",
            data={"target_type": "user", "target_id": user.pk, "page_size": 2},
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data), 2)
        self.assertIn("Link", response)
        self.assertEqual(
            response["Link"],
            (
                f"<http://testserver/messaging?page=2&page_size=2&"
                f'target_id={user.pk}&target_type=user>; rel="next",'
                " <http://testserver/messaging?page=2&page_size=2&"
                f'target_id={user.pk}&target_type=user>; rel="last"'
            ),
        )

        # Test the retrieval threshold is respected
        with override_settings(MESSAGE_RETRIEVAL_THRESHOLD=2):
            request = self.factory.get(
                "/messaging", data={"target_type": "user", "target_id": user.pk}
            )
            force_authenticate(request, user=user)
            response = view(request=request)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(len(response.data), 2)
            self.assertIn("Link", response)
            self.assertEqual(
                response["Link"],
                (
                    f"<http://testserver/messaging?page=2&"
                    f'target_id={user.pk}&target_type=user>; rel="next",'
                    " <http://testserver/messaging?page=2&"
                    f'target_id={user.pk}&target_type=user>; rel="last"'
                ),
            )

    @override_settings(USE_TZ=False)
    def test_messaging_timestamp_filter(self):
        """
        Test that a user is able to filter messages using the timestamp
        """
        user = _create_user()
        message_one = self._create_message(user)
        message_two = self._create_message(user)

        view = MessagingViewSet.as_view({"get": "list"})
        message_one_timestamp = message_one["timestamp"]
        target_id = user.id
        request = self.factory.get(
            f"/messaging?timestamp={message_one_timestamp}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0].get("id"), message_one["id"])

        # Test able to filter using gt & gte lookups
        request = self.factory.get(
            f"/messaging?timestamp__gt={message_one_timestamp}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0].get("id"), message_two["id"])

        request = self.factory.get(
            f"/messaging?timestamp__gte={message_one_timestamp}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # Test able to filter using lt & lte lookups
        message_two_timestamp = message_two["timestamp"]
        request = self.factory.get(
            f"/messaging?timestamp__lt={message_two_timestamp}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0].get("id"), message_one["id"])

        message_two_timestamp = message_two["timestamp"]
        request = self.factory.get(
            f"/messaging?timestamp__lte={message_two_timestamp}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # Test able to use day filters
        day = Action.objects.get(id=message_one["id"]).timestamp.day

        request = self.factory.get(
            f"/messaging?timestamp__day={day}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        request = self.factory.get(
            f"/messaging?timestamp__day__gt={day}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get(
            f"/messaging?timestamp__day__gte={day}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        request = self.factory.get(
            f"/messaging?timestamp__day__lt={day}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get(
            f"/messaging?timestamp__day__lte={day}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # Test able to use month filters
        month = Action.objects.get(id=message_one["id"]).timestamp.month

        request = self.factory.get(
            f"/messaging?timestamp__month={month}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        request = self.factory.get(
            f"/messaging?timestamp__month__gt={month}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get(
            f"/messaging?timestamp__month__gte={month}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        request = self.factory.get(
            f"/messaging?timestamp__month__lt={month}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get(
            f"/messaging?timestamp__month__lte={month}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # Test able to use year filters
        year = Action.objects.get(id=message_one["id"]).timestamp.year

        request = self.factory.get(
            f"/messaging?timestamp__year={year}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        request = self.factory.get(
            f"/messaging?timestamp__year__gt={year}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get(
            f"/messaging?timestamp__year__gte={year}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        request = self.factory.get(
            f"/messaging?timestamp__year__lt={year}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get(
            f"/messaging?timestamp__year__lte={year}&"
            f"target_type=user&target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # Test able to use hour & minute filters
        hour = Action.objects.get(id=message_one["id"]).timestamp.hour
        minute = Action.objects.get(id=message_one["id"]).timestamp.minute

        request = self.factory.get(
            f"/messaging?timestamp__hour={hour}&target_type=user&"
            f"target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        request = self.factory.get(
            f"/messaging?timestamp__hour__lt={hour}&target_type=user&"
            f"target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get(
            f"/messaging?timestamp__hour__gt={hour}&target_type=user&"
            f"target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get(
            f"/messaging?timestamp__hour__lte={hour}&target_type=user&"
            f"target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        request = self.factory.get(
            f"/messaging?timestamp__hour__gte={hour}&target_type=user&"
            f"target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        request = self.factory.get(
            f"/messaging?timestamp__minute__gt={minute}&target_type=user&"
            f"target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get(
            f"/messaging?timestamp__minute__lt={minute}&target_type=user&"
            f"target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get(
            f"/messaging?timestamp__minute__gte={minute}&target_type=user&"
            f"target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        request = self.factory.get(
            f"/messaging?timestamp__minute__lte={minute}&target_type=user&"
            f"target_id={target_id}"
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
