# -*- coding: utf-8 -*-
"""
Tests Messaging app viewsets.
"""

from __future__ import unicode_literals

from builtins import str as text
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.middleware.cache import FetchFromCacheMiddleware, UpdateCacheMiddleware
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from actstream.models import Action
from actstream.signals import action
from guardian.shortcuts import assign_perm, remove_perm
from rest_framework.test import APIRequestFactory, force_authenticate

from onadata.apps.api.viewsets.messaging_stats_viewset import MessagingStatsViewSet
from onadata.apps.logger.models import EntityList, KMSKey
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.messaging.constants import (
    EXPORT_CREATED,
    MESSAGE,
    MESSAGE_VERBS,
    SUBMISSION_CREATED,
)
from onadata.apps.messaging.tests.test_base import _create_user
from onadata.apps.messaging.viewsets import MessagingViewSet
from onadata.libs.permissions import ManagerRole, MemberRole
from onadata.libs.utils.user_auth import get_user_default_project

User = get_user_model()


class TestMessagingViewSet(TestCase):
    """
    Test MessagingViewSet class.
    """

    def setUp(self):
        self.factory = APIRequestFactory()
        # Isolate tests that exercise site-cache middleware.
        cache.clear()

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
        self.assertLessEqual(data.items(), response.data.items())
        # ensure that id and timestamp are returned
        self.assertTrue("id" and "timestamp" in [text(x) for x in list(response.data)])
        return response.data

    def test_create_message(self):
        """
        Test POST /messaging adding a new message for a specific form.
        """
        self._create_message()

    def test_create_message_for_kmskey(self):
        """
        POST /messaging adds a new message for a KMS key.
        """
        user = _create_user()
        kms_key = KMSKey.objects.create(
            key_id="fake-key-id",
            public_key="fake-pub-key",
            content_type=ContentType.objects.get_for_model(User),
            object_id=user.pk,
            provider=KMSKey.KMSProvider.AWS,
        )
        assign_perm("logger.change_kmskey", user, kms_key)
        view = MessagingViewSet.as_view({"post": "create"})
        data = {
            "message": "Hello World!",
            "target_id": kms_key.pk,
            "target_type": "kmskey",
        }
        request = self.factory.post("/messaging", data)
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 201, response.data)
        message = Action.objects.get(
            target_content_type=ContentType.objects.get_for_model(KMSKey),
            target_object_id=kms_key.pk,
        )
        self.assertEqual(message.actor, user)
        self.assertEqual(message.description, "Hello World!")

    def test_create_message_for_entitylist(self):
        """
        POST /messaging adds a new message for an entity list.
        """
        user = _create_user()
        entity_list = EntityList.objects.create(
            name="trees", project=get_user_default_project(user)
        )
        assign_perm("logger.change_entitylist", user, entity_list)
        view = MessagingViewSet.as_view({"post": "create"})
        data = {
            "message": "Hello World!",
            "target_id": entity_list.pk,
            "target_type": "entitylist",
        }
        request = self.factory.post("/messaging", data)
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 201, response.data)
        message = Action.objects.get(
            target_content_type=ContentType.objects.get_for_model(EntityList),
            target_object_id=entity_list.pk,
        )
        self.assertEqual(message.actor, user)
        self.assertEqual(message.description, "Hello World!")

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
            "/messaging",
            {"target_type": "project", "target_id": get_user_default_project(user).pk},
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

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_list_response_is_cached(self):
        """Authorized reads reuse activity until the server cache expires."""
        user = _create_user()
        self._create_message(user)
        view = MessagingViewSet.as_view({"get": "list"})
        params = {"target_type": "user", "target_id": user.pk}

        # Read the initial activity.
        request = self.factory.get("/messaging", params)
        force_authenticate(request, user=user)
        first = view(request=request)
        first.render()
        self.assertEqual(first.status_code, 200)

        # Add activity after the first response.
        self._create_message(user)

        # The same URL reuses the cached activity.
        request = self.factory.get("/messaging", params)
        force_authenticate(request, user=user)
        second = view(request=request)
        if hasattr(second, "render"):
            second.render()
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.content, first.content)
        self.assertIn("no-store", second["Cache-Control"])
        cache.clear()
        request = self.factory.get("/messaging", params)
        force_authenticate(request, user=user)
        fresh = view(request=request)
        self.assertEqual(len(fresh.data), 2)

    def test_list_respects_target_query_params(self):
        """Each user receives activity for their requested target."""
        user = _create_user()
        other = _create_user("otheruser")
        self._create_message(user)  # a single message targeted at `user`
        view = MessagingViewSet.as_view({"get": "list"})

        # Read the first target.
        request = self.factory.get(
            "/messaging", {"target_type": "user", "target_id": user.pk}
        )
        force_authenticate(request, user=user)
        first = view(request=request)
        first.render()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(len(first.data), 1)

        # a request for a different target returns its own data
        request = self.factory.get(
            "/messaging", {"target_type": "user", "target_id": other.pk}
        )
        force_authenticate(request, user=other)
        second = view(request=request)
        second.render()
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.data), 0)

    def test_list_cache_does_not_bypass_authentication(self):
        """An anonymous request is rejected even when the list cache is warm."""
        user = _create_user()
        self._create_message(user)
        view = MessagingViewSet.as_view({"get": "list"})
        params = {"target_type": "user", "target_id": user.pk}

        # warm the cache with an authenticated request
        request = self.factory.get("/messaging", params)
        force_authenticate(request, user=user)
        warm = view(request=request)
        warm.render()
        self.assertEqual(warm.status_code, 200)

        # an anonymous request to the same URL is still rejected
        request = self.factory.get("/messaging", params)
        response = view(request=request)
        self.assertEqual(response.status_code, 401)

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
            f"/messaging?timestamp__day={day}&target_type=user&target_id={target_id}"
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
            f"/messaging?timestamp__year={year}&target_type=user&target_id={target_id}"
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
            f"/messaging?timestamp__hour={hour}&target_type=user&target_id={target_id}"
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

    def test_group_by_user_and_verb_returns_counts(self):
        """
        group_by=user&group_by=verb returns per-(user, verb) counts.
        """
        user = _create_user()
        for _ in range(2):
            action.send(user, verb=EXPORT_CREATED, target=user)
        for _ in range(3):
            action.send(user, verb=SUBMISSION_CREATED, target=user)

        view = MessagingViewSet.as_view({"get": "list"})
        request = self.factory.get(
            "/messaging",
            {
                "target_type": "user",
                "target_id": user.pk,
                "group_by": ["user", "verb"],
            },
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200, response.data)

        counts = {(row["user"], row["verb"]): row["count"] for row in response.data}
        self.assertEqual(counts[(user.username, EXPORT_CREATED)], 2)
        self.assertEqual(counts[(user.username, SUBMISSION_CREATED)], 3)
        for row in response.data:
            self.assertIn("latest_timestamp", row)

    def test_group_by_verb_orders_by_recent_activity(self):
        """
        Grouped rows are ordered most-recent-activity first.
        """
        user = _create_user()
        older = timezone.now() - timedelta(days=2)
        newer = timezone.now()
        action.send(user, verb=EXPORT_CREATED, target=user, timestamp=older)
        action.send(user, verb=SUBMISSION_CREATED, target=user, timestamp=newer)

        view = MessagingViewSet.as_view({"get": "list"})
        request = self.factory.get(
            "/messaging",
            {"target_type": "user", "target_id": user.pk, "group_by": "verb"},
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200, response.data)

        verbs_in_order = [row["verb"] for row in response.data]
        self.assertEqual(verbs_in_order, [SUBMISSION_CREATED, EXPORT_CREATED])

    def test_group_by_verb_latest_timestamp_is_newest(self):
        """
        A group's latest_timestamp equals its newest action's timestamp.
        """
        user = _create_user()
        older = timezone.now() - timedelta(days=1)
        newest = timezone.now()
        action.send(user, verb=EXPORT_CREATED, target=user, timestamp=older)
        action.send(user, verb=EXPORT_CREATED, target=user, timestamp=newest)

        view = MessagingViewSet.as_view({"get": "list"})
        request = self.factory.get(
            "/messaging",
            {"target_type": "user", "target_id": user.pk, "group_by": "verb"},
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200, response.data)

        row = response.data[0]
        self.assertEqual(row["count"], 2)
        self.assertEqual(parse_datetime(row["latest_timestamp"]), newest)

    def test_group_by_verb_null_user_for_unresolvable_actor(self):
        """
        A group whose actor id no longer resolves to a user is returned with
        user null and the row is retained.
        """
        target_user = _create_user("target")
        actor_user = _create_user("ghost")
        action.send(actor_user, verb=SUBMISSION_CREATED, target=target_user)
        # Simulate a dangling actor reference (e.g. data left behind by a raw
        # delete) without triggering actstream's GenericRelation cascade, which
        # deleting the user would otherwise use to remove the action too.
        Action.objects.filter(actor_object_id=actor_user.pk).update(
            actor_object_id=9999999
        )

        view = MessagingViewSet.as_view({"get": "list"})
        request = self.factory.get(
            "/messaging",
            {
                "target_type": "user",
                "target_id": target_user.pk,
                "group_by": ["user", "verb"],
            },
        )
        force_authenticate(request, user=target_user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200, response.data)

        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row["verb"], SUBMISSION_CREATED)
        self.assertEqual(row["count"], 1)
        self.assertIsNone(row["user"])

    def test_group_by_user_only(self):
        """
        group_by=user groups by actor only, aggregating across verbs, and the
        rows carry no verb field.
        """
        target_user = _create_user("target")
        alice = _create_user("alice")
        bob = _create_user("bob")
        action.send(alice, verb=SUBMISSION_CREATED, target=target_user)
        action.send(bob, verb=SUBMISSION_CREATED, target=target_user)
        action.send(bob, verb=EXPORT_CREATED, target=target_user)

        view = MessagingViewSet.as_view({"get": "list"})
        request = self.factory.get(
            "/messaging",
            {"target_type": "user", "target_id": target_user.pk, "group_by": "user"},
        )
        force_authenticate(request, user=target_user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200, response.data)

        counts = {row["user"]: row["count"] for row in response.data}
        self.assertEqual(counts["alice"], 1)
        self.assertEqual(counts["bob"], 2)
        for row in response.data:
            self.assertNotIn("verb", row)

    def test_group_by_validation(self):
        """
        group_by rejects unsupported values and still requires a target.
        """
        user = _create_user()
        action.send(user, verb=SUBMISSION_CREATED, target=user)
        view = MessagingViewSet.as_view({"get": "list"})

        # an unsupported group_by value is rejected
        request = self.factory.get(
            "/messaging",
            {"target_type": "user", "target_id": user.pk, "group_by": "actor"},
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {"detail": "Unsupported group_by value 'actor'"}
        )

        # an unsupported value alongside a valid one is still rejected
        request = self.factory.get(
            "/messaging",
            {
                "target_type": "user",
                "target_id": user.pk,
                "group_by": ["verb", "actor"],
            },
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {"detail": "Unsupported group_by value 'actor'"}
        )

        # grouped mode still requires a target (contract unchanged)
        request = self.factory.get("/messaging", {"group_by": "verb"})
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, {"detail": "Parameter 'target_type' is missing."}
        )

    def test_group_by_verb_only(self):
        """
        group_by=verb groups by verb only, aggregating across actors, and the
        rows carry no user field.
        """
        target_user = _create_user("target")
        alice = _create_user("alice")
        bob = _create_user("bob")
        action.send(alice, verb=SUBMISSION_CREATED, target=target_user)
        action.send(bob, verb=SUBMISSION_CREATED, target=target_user)
        action.send(bob, verb=EXPORT_CREATED, target=target_user)

        view = MessagingViewSet.as_view({"get": "list"})
        request = self.factory.get(
            "/messaging",
            {"target_type": "user", "target_id": target_user.pk, "group_by": "verb"},
        )
        force_authenticate(request, user=target_user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200, response.data)

        counts = {row["verb"]: row["count"] for row in response.data}
        self.assertEqual(counts[SUBMISSION_CREATED], 2)
        self.assertEqual(counts[EXPORT_CREATED], 1)
        for row in response.data:
            self.assertNotIn("user", row)

    def test_group_by_day_returns_period_buckets(self):
        """
        group_by=day returns one row per UTC day carrying period_start,
        earliest_timestamp and latest_timestamp, ordered most-recent day first.
        """
        user = _create_user()
        day_one = datetime(2026, 3, 10, 12, 0, tzinfo=dt_timezone.utc)
        day_two = datetime(2026, 3, 12, 9, 0, tzinfo=dt_timezone.utc)
        action.send(user, verb=SUBMISSION_CREATED, target=user, timestamp=day_one)
        action.send(
            user,
            verb=SUBMISSION_CREATED,
            target=user,
            timestamp=day_one + timedelta(hours=3),
        )
        action.send(user, verb=SUBMISSION_CREATED, target=user, timestamp=day_two)

        view = MessagingViewSet.as_view({"get": "list"})
        request = self.factory.get(
            "/messaging",
            {"target_type": "user", "target_id": user.pk, "group_by": "day"},
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200, response.data)

        self.assertEqual(len(response.data), 2)
        periods = [parse_datetime(row["period_start"]) for row in response.data]
        self.assertEqual(
            periods,
            [
                datetime(2026, 3, 12, tzinfo=dt_timezone.utc),
                datetime(2026, 3, 10, tzinfo=dt_timezone.utc),
            ],
        )

        newest_day = response.data[0]
        self.assertEqual(newest_day["count"], 1)
        self.assertEqual(parse_datetime(newest_day["latest_timestamp"]), day_two)

        oldest_day = response.data[1]
        self.assertEqual(oldest_day["count"], 2)
        self.assertEqual(parse_datetime(oldest_day["earliest_timestamp"]), day_one)
        self.assertEqual(
            parse_datetime(oldest_day["latest_timestamp"]),
            day_one + timedelta(hours=3),
        )

    def test_group_by_day_buckets_boundaries_in_utc(self):
        """
        Day boundaries are computed in UTC, not the server timezone. Two events
        on the same UTC day but different America/New_York days fall in one
        bucket whose period_start is UTC midnight.
        """
        user = _create_user()
        # Both on 2026-03-15 UTC; in America/New_York (EDT, UTC-4) the first is
        # 2026-03-14 21:00 and the second is 2026-03-15 18:00 - different local
        # days that must still collapse into a single UTC-day bucket.
        early = datetime(2026, 3, 15, 1, 0, tzinfo=dt_timezone.utc)
        late = datetime(2026, 3, 15, 22, 0, tzinfo=dt_timezone.utc)
        action.send(user, verb=SUBMISSION_CREATED, target=user, timestamp=early)
        action.send(user, verb=SUBMISSION_CREATED, target=user, timestamp=late)

        view = MessagingViewSet.as_view({"get": "list"})
        request = self.factory.get(
            "/messaging",
            {"target_type": "user", "target_id": user.pk, "group_by": "day"},
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200, response.data)

        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row["count"], 2)
        self.assertEqual(
            parse_datetime(row["period_start"]),
            datetime(2026, 3, 15, tzinfo=dt_timezone.utc),
        )

    def test_group_by_rejects_multiple_time_buckets(self):
        """
        Combining more than one time bucket in a single request is rejected.
        """
        user = _create_user()
        action.send(user, verb=SUBMISSION_CREATED, target=user)

        view = MessagingViewSet.as_view({"get": "list"})
        request = self.factory.get(
            "/messaging",
            {
                "target_type": "user",
                "target_id": user.pk,
                "group_by": ["day", "hour"],
            },
        )
        force_authenticate(request, user=user)
        response = view(request=request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {"detail": "Only one time bucket may be combined per group_by request"},
        )

    def test_group_by_day_user_and_verb_composes(self):
        """
        A time bucket composes with user and verb: rows are per
        (day, user, verb) and carry all requested dimensions.
        """
        target_user = _create_user("target")
        bob = _create_user("bob")
        sunday = datetime(2026, 3, 15, 10, 0, tzinfo=dt_timezone.utc)
        monday = datetime(2026, 3, 16, 10, 0, tzinfo=dt_timezone.utc)
        # Bob: two submissions on Sunday, one on Monday.
        action.send(bob, verb=SUBMISSION_CREATED, target=target_user, timestamp=sunday)
        action.send(
            bob,
            verb=SUBMISSION_CREATED,
            target=target_user,
            timestamp=sunday + timedelta(hours=2),
        )
        action.send(bob, verb=SUBMISSION_CREATED, target=target_user, timestamp=monday)

        view = MessagingViewSet.as_view({"get": "list"})
        request = self.factory.get(
            "/messaging",
            {
                "target_type": "user",
                "target_id": target_user.pk,
                "group_by": ["day", "user", "verb"],
            },
        )
        force_authenticate(request, user=target_user)
        response = view(request=request)
        self.assertEqual(response.status_code, 200, response.data)

        counts = {
            (parse_datetime(row["period_start"]), row["user"], row["verb"]): row[
                "count"
            ]
            for row in response.data
        }
        sunday_bucket = datetime(2026, 3, 15, tzinfo=dt_timezone.utc)
        monday_bucket = datetime(2026, 3, 16, tzinfo=dt_timezone.utc)
        self.assertEqual(counts[(sunday_bucket, "bob", SUBMISSION_CREATED)], 2)
        self.assertEqual(counts[(monday_bucket, "bob", SUBMISSION_CREATED)], 1)


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class TestMessagingAuthorization(TestBase):
    """Activity authorization applies to empty feeds, detail and aggregates."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.factory = APIRequestFactory()
        self.other = _create_user("activity-reader")
        self._publish_transportation_form()
        project = get_user_default_project(self.user)
        key = KMSKey.objects.create(
            key_id="activity-key",
            public_key="public-key",
            content_type=ContentType.objects.get_for_model(User),
            object_id=self.user.pk,
            provider=KMSKey.KMSProvider.AWS,
        )
        entity_list = EntityList.objects.create(name="activity-trees", project=project)
        self.targets = [self.xform, project, key, entity_list]

    def _read(self, target, user, mode="list"):
        viewset = MessagingStatsViewSet if mode == "stats" else MessagingViewSet
        params = {"target_type": target._meta.model_name, "target_id": target.pk}
        if mode in ("grouped", "stats"):
            params["group_by"] = "day"
        request = self.factory.get("/messaging", params)
        force_authenticate(request, user=user)
        if mode == "retrieve":
            event = Action.objects.filter(
                target_content_type=ContentType.objects.get_for_model(target),
                target_object_id=target.pk,
            ).latest("pk")
            response = viewset.as_view({"get": "retrieve"})(request, pk=event.pk)
        else:
            response = viewset.as_view({"get": "list"})(request)
        if response.status_code == 200 and getattr(response, "streaming", False):
            list(response.streaming_content)
        if hasattr(response, "render"):
            response.render()
        return response

    def _assert_read_status(self, target, user, status, populated=False):
        modes = ["list", "grouped", "stats"]
        if populated:
            modes.append("retrieve")
        for mode in modes:
            with self.subTest(target=target._meta.model_name, mode=mode):
                response = self._read(target, user, mode)
                self.assertEqual(
                    response.status_code, status, getattr(response, "data", None)
                )

    def _assert_writes(self, target, user, available):
        """An authorized caller can mutate only available targets."""
        assign_perm(
            f"{target._meta.app_label}.change_{target._meta.model_name}", user, target
        )
        assign_perm(
            f"{target._meta.app_label}.delete_{target._meta.model_name}", user, target
        )
        self.assertTrue(
            user.has_perm(
                f"{target._meta.app_label}.change_{target._meta.model_name}", target
            )
        )
        self.assertTrue(
            user.has_perm(
                f"{target._meta.app_label}.delete_{target._meta.model_name}", target
            )
        )
        action.send(self.user, verb=MESSAGE, target=target)
        event = Action.objects.latest("pk")
        count = Action.objects.count()
        request = self.factory.post(
            "/messaging",
            {
                "target_type": target._meta.model_name,
                "target_id": target.pk,
                "message": "Public message",
            },
        )
        force_authenticate(request, user=user)
        response = MessagingViewSet.as_view({"post": "create"})(request)
        self.assertEqual(response.status_code, 201 if available else 400, response.data)
        if available:
            self.assertEqual(Action.objects.count(), count + 1)
        else:
            self.assertEqual(response.data, {"target_id": "target_id not found"})
            self.assertEqual(Action.objects.count(), count)
        request = self.factory.delete("/messaging")
        force_authenticate(request, user=user)
        response = MessagingViewSet.as_view({"delete": "destroy"})(request, pk=event.pk)
        self.assertEqual(response.status_code, 204 if available else 404)
        self.assertEqual(Action.objects.filter(pk=event.pk).exists(), not available)
        self.assertEqual(Action.objects.count(), count)

    def test_cached_lists_skip_activity_queries(self):
        """Both list formats reuse data after checking current target access."""
        target = self.targets[1]
        assign_perm("logger.view_project", self.other, target)
        for mode in ("list", "grouped"):
            with self.subTest(mode=mode):
                first = self._read(target, self.other, mode)
                self.assertEqual(first.status_code, 200)
                with patch.object(
                    MessagingViewSet, "get_queryset", side_effect=AssertionError
                ):
                    cached = self._read(target, self.other, mode)
                self.assertEqual(cached.status_code, 200)
                self.assertEqual(cached.content, first.content)
                self.assertIn("no-store", cached["Cache-Control"])

    def test_deleted_targets_are_unavailable(self):
        """Retained permissions cannot expose deleted resources or empty feeds."""
        for target in (self.xform, self.targets[1], self.targets[3]):
            assign_perm(f"logger.view_{target._meta.model_name}", self.other, target)
            self._assert_read_status(target, self.other, 200)
            self._assert_writes(target, self.other, available=True)
            queryset = type(target).objects.filter(pk=target.pk)
            queryset.update(deleted_at=timezone.now())
            self._assert_writes(target, self.other, available=False)
            self._assert_read_status(target, self.other, 404)
            action.send(self.user, verb=SUBMISSION_CREATED, target=target)
            self._assert_read_status(target, self.other, 404, populated=True)
            queryset.update(deleted_at=None)
            self._assert_read_status(target, self.other, 200, populated=True)

    def test_deleted_projects_hide_child_activity(self):
        """An undeleted form or entity list in a deleted project is unavailable."""
        for target in (self.xform, self.targets[3]):
            assign_perm(f"logger.view_{target._meta.model_name}", self.other, target)
            action.send(self.user, verb=SUBMISSION_CREATED, target=target)
            self._assert_read_status(target, self.other, 200, populated=True)
            self._assert_writes(target, self.other, available=True)
            project = target.project
            type(project).objects.filter(pk=project.pk).update(
                deleted_at=timezone.now()
            )
            self._assert_read_status(target, self.other, 404, populated=True)
            self._assert_writes(target, self.other, available=False)
            type(project).objects.filter(pk=project.pk).update(deleted_at=None)

    def test_inactive_organization_hides_feeds_and_resources(self):
        """Organization deactivation blocks reads despite retained roles."""
        organization = self._create_organization("inactive-org", "Activity", self.user)
        ManagerRole.add(self.other, organization)
        project = self.targets[1]
        project.organization = organization.user
        project.save()
        targets = (self.xform, project, self.targets[3], organization.user)
        for target in targets:
            if not isinstance(target, User):
                assign_perm(
                    f"logger.view_{target._meta.model_name}", self.other, target
                )
            self._assert_read_status(target, self.other, 200)
            writer = organization.user if isinstance(target, User) else self.other
            self._assert_writes(target, writer, available=True)

        User.objects.filter(pk=organization.user_id).update(is_active=False)
        for target in targets:
            writer = organization.user if isinstance(target, User) else self.other
            self._assert_writes(target, writer, available=False)
            self._assert_read_status(target, self.other, 404)
            action.send(self.user, verb=SUBMISSION_CREATED, target=target)
            self._assert_read_status(target, self.other, 404, populated=True)
        self._assert_read_status(organization.user, self.user, 404, populated=True)

        User.objects.filter(pk=organization.user_id).update(is_active=True)
        for target in targets:
            self._assert_read_status(target, self.other, 200, populated=True)

    def test_kms_owner_activity_controls_access(self):
        """Both owner types must be active, regardless of the key's state."""
        User.objects.create(username="key-owner-id-offset")
        organization = self._create_organization("key-org", "Keys", self.user)
        self.assertNotEqual(organization.pk, organization.user_id)
        key = self.targets[2]
        assign_perm("logger.view_kmskey", self.other, key)
        for owner in (organization, organization.user):
            key.content_type = ContentType.objects.get_for_model(owner)
            key.object_id = owner.pk
            key.is_active = False
            key.disabled_at = timezone.now()
            key.rotated_at = timezone.now()
            key.expiry_date = timezone.now() - timedelta(days=1)
            key.save()
            self._assert_writes(key, self.other, available=True)
            self._assert_read_status(key, self.other, 200, populated=True)
            User.objects.filter(pk=organization.user_id).update(is_active=False)
            self._assert_read_status(key, self.other, 404)
            self._assert_writes(key, self.other, available=False)
            action.send(self.user, verb=SUBMISSION_CREATED, target=key)
            self._assert_read_status(key, self.other, 404, populated=True)
            User.objects.filter(pk=organization.user_id).update(is_active=True)
            self._assert_read_status(key, self.other, 200, populated=True)

    def test_inactive_personal_feed_is_unavailable(self):
        """The self-only exception does not bypass target account activity."""
        action.send(self.user, verb=SUBMISSION_CREATED, target=self.user)
        self._assert_read_status(self.user, self.user, 200, populated=True)
        self._assert_writes(self.user, self.user, available=True)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self._assert_writes(self.user, self.user, available=False)
        self._assert_read_status(self.user, self.user, 404, populated=True)

    def test_kms_invalid_owners_cannot_use_cached_activity(self):
        """Cached feeds do not expose keys with missing or unsupported owners."""
        User.objects.create(username="missing-key-owner-id-offset")
        organization = self._create_organization("missing-key-org", "Keys", self.user)
        self.assertNotEqual(organization.pk, organization.user_id)
        key = self.targets[2]
        assign_perm("logger.view_kmskey", self.other, key)
        action.send(self.user, verb=SUBMISSION_CREATED, target=key)
        owners = (
            (self.user, None),
            (organization, None),
            (self.user, 99999999),
            (organization, 99999999),
            (self.targets[1], self.targets[1].pk),
        )
        for owner, object_id in owners:
            with self.subTest(owner=owner._meta.model_name, object_id=object_id):
                key.content_type = ContentType.objects.get_for_model(self.user)
                key.object_id = self.user.pk
                key.save()
                self._assert_read_status(key, self.other, 200, populated=True)
                key.content_type = ContentType.objects.get_for_model(owner)
                key.object_id = object_id
                key.save()
                for _ in range(2):
                    self._assert_read_status(key, self.other, 404, populated=True)
                self._assert_writes(key, self.other, available=False)

    def test_target_permissions_and_revocation(self):
        """Each resource requires its view permission, even for an empty feed."""
        for target in self.targets:
            permission = f"{target._meta.app_label}.view_{target._meta.model_name}"
            for mode in ("list", "grouped", "stats"):
                with self.subTest(target=target._meta.model_name, mode=mode):
                    self.assertEqual(
                        self._read(target, self.other, mode).status_code, 403
                    )
                    assign_perm(permission, self.other, target)
                    self.assertEqual(
                        self._read(target, self.other, mode).status_code, 200
                    )
                    action.send(self.user, verb=SUBMISSION_CREATED, target=target)
                    self.assertEqual(
                        self._read(target, self.other, mode).status_code, 200
                    )
                    remove_perm(permission, self.other, target)
                    self.assertEqual(
                        self._read(target, self.other, mode).status_code, 403
                    )

    def test_personal_and_organization_feeds(self):
        """Only self or organization administrators can read user feeds."""
        organization = self._create_organization("activity-org", "Activity", self.user)
        manager = _create_user("activity-manager")
        ManagerRole.add(manager, organization)
        MemberRole.add(self.other, organization)
        action.send(self.user, verb=SUBMISSION_CREATED, target=organization.user)
        for mode in ("list", "grouped", "stats"):
            self.assertEqual(self._read(self.user, self.user, mode).status_code, 200)
            self.assertEqual(self._read(self.user, self.other, mode).status_code, 403)
            for reader in (self.user, manager):
                self.assertEqual(
                    self._read(organization.user, reader, mode).status_code, 200
                )
            self.assertEqual(
                self._read(organization.user, self.other, mode).status_code, 403
            )
        event = Action.objects.filter(target_object_id=organization.user.pk).last()
        for reader in (self.user, manager):
            request = self.factory.get("/messaging")
            force_authenticate(request, user=reader)
            response = MessagingViewSet.as_view({"get": "retrieve"})(
                request, pk=event.pk
            )
            self.assertEqual(response.status_code, 200)
            request = self.factory.delete("/messaging")
            force_authenticate(request, user=reader)
            response = MessagingViewSet.as_view({"delete": "destroy"})(
                request, pk=event.pk
            )
            self.assertEqual(response.status_code, 403)
            request = self.factory.post(
                "/messaging",
                {
                    "target_type": "user",
                    "target_id": organization.user.pk,
                    "message": "Hi",
                },
            )
            force_authenticate(request, user=reader)
            self.assertEqual(
                MessagingViewSet.as_view({"post": "create"})(request).status_code, 403
            )

    def test_invalid_targets(self):
        """Malformed and absent targets fail before reading any activity."""
        for viewset in (MessagingViewSet, MessagingStatsViewSet):
            for target_id in ("invalid", "1.5", "99999999"):
                request = self.factory.get(
                    "/messaging",
                    {
                        "target_type": "xform",
                        "target_id": target_id,
                        "group_by": "day",
                    },
                )
                force_authenticate(request, user=self.user)
                response = viewset.as_view({"get": "list"})(request)
                self.assertEqual(response.status_code, 404)

    def test_dangling_action_target_is_denied(self):
        """A missing Action target cannot authorize detail reads or deletion."""
        action.send(self.user, verb=SUBMISSION_CREATED, target=self.user)
        event = Action.objects.latest("pk")
        Action.objects.filter(pk=event.pk).update(target_object_id="99999999")
        count = Action.objects.count()
        for method, operation in (("get", "retrieve"), ("delete", "destroy")):
            request = getattr(self.factory, method)("/messaging")
            force_authenticate(request, user=self.user)
            response = MessagingViewSet.as_view({method: operation})(
                request, pk=event.pk
            )
            self.assertEqual(response.status_code, 404)
            self.assertTrue(Action.objects.filter(pk=event.pk).exists())
            self.assertEqual(Action.objects.count(), count)

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_site_cache_does_not_bypass_permissions(self):
        """Site-cache middleware cannot reuse an authorized activity response."""
        target = self.targets[1]
        outsider = _create_user("cache-outsider")
        for viewset in (MessagingViewSet, MessagingStatsViewSet):
            view = viewset.as_view({"get": "list"})

            def render(request):
                response = view(request)
                if hasattr(response, "render"):
                    response.render()
                return response

            handler = UpdateCacheMiddleware(FetchFromCacheMiddleware(render))
            assign_perm("logger.view_project", self.other, target)
            for reader, expected in (
                (self.other, 200),
                (outsider, 403),
                (self.user, 200),
                (self.other, 403),
            ):
                if reader == self.other and expected == 403:
                    remove_perm("logger.view_project", self.other, target)
                request = self.factory.get(
                    "/messaging",
                    {
                        "target_type": "project",
                        "target_id": target.pk,
                        "group_by": "day",
                    },
                )
                force_authenticate(request, user=reader)
                response = handler(request)
                self.assertEqual(response.status_code, expected)
                self.assertIn("no-store", response["Cache-Control"])
                self.assertIn("private", response["Cache-Control"])
                if getattr(response, "streaming", False):
                    list(response.streaming_content)

    def test_public_post_rejects_every_system_verb(self):
        """Even editors cannot publish system events or notifications."""
        view = MessagingViewSet.as_view({"post": "create"})
        for reader in (self.user, self.other):
            for verb in set(MESSAGE_VERBS) - {MESSAGE}:
                with self.subTest(user=reader.username, verb=verb):
                    before = Action.objects.count()
                    request = self.factory.post(
                        "/messaging",
                        {
                            "target_type": "xform",
                            "target_id": self.xform.pk,
                            "message": "forged",
                            "verb": verb,
                        },
                    )
                    force_authenticate(request, user=reader)
                    with patch(
                        "onadata.apps.messaging.serializers.action.send"
                    ) as send:
                        response = view(request)
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("verb", response.data)
                    self.assertEqual(Action.objects.count(), before)
                    send.assert_not_called()

    def test_message_create_and_system_event_read(self):
        """Default and explicit messages need change permission; GET retains verbs."""
        view = MessagingViewSet.as_view({"post": "create"})
        for extra in ({}, {"verb": MESSAGE}):
            for reader, expected in ((self.user, 201), (self.other, 403)):
                request = self.factory.post(
                    "/messaging",
                    {
                        "target_type": "xform",
                        "target_id": self.xform.pk,
                        "message": "hello",
                        **extra,
                    },
                )
                force_authenticate(request, user=reader)
                self.assertEqual(view(request).status_code, expected)
        action.send(self.user, verb=SUBMISSION_CREATED, target=self.xform)
        response = self._read(self.xform, self.user)
        self.assertIn(SUBMISSION_CREATED, [row["verb"] for row in response.data])
