# -*- coding: utf-8 -*-
"""
Tests Messaging app implementation.
"""
from __future__ import unicode_literals

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory, force_authenticate

from onadata.apps.messaging.viewsets import MessagingViewSet


class TestMessagingViewSet(TestCase):
    """
    Test MessagingViewSet class.
    """

    def setUp(self):
        self.factory = APIRequestFactory()

    def _create_user(self):
        self.user = User.objects.create(username='testuser')
        return self.user

    def test_create_message(self):
        """
        Test POST /messaging adding a new message for a specific form.
        """
        self._create_user()
        view = MessagingViewSet.as_view({'post': 'create'})
        data = {
            "message": "Hello World!",
            "target_id": self.user.pk,
            "target_type": 'user',
        }  # yapf: disable
        request = self.factory.post('/messaging', data)
        force_authenticate(request, user=self.user)
        response = view(request=request)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertDictContainsSubset(data, response.data)

    def test_delete_message(self):
        """
        Test DELETE /messaging/[pk] deleting a message.
        """
        self.fail("Implement deleting a message")

    def test_list_messages(self):
        """
        Test GET /messaging listing of messages for specific forms.
        """
        self.fail("Implement listing messages for a single form")

    def test_retrieve_messages(self):
        """
        Test GET /messaging/[pk] return a message matching pk.
        """
        self.fail("Implement listing messages for a single form")

    def test_authentication_required(self):
        """
        Test that authentication is required at all endpoints.
        """
        self.fail('Implement authentication required.')
