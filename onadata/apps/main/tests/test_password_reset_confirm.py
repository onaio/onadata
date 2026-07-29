# -*- coding: utf-8 -*-
"""Tests for the native /accounts/password/reset/confirm/ flow.

The API's own reset-confirm endpoint (which used to call
``invalidate_and_regen_tokens``) has been removed in favour of Django's
native reset flow, so this flow is now the only one that completes a
password reset. It must rotate the user's DRF/temp tokens itself.
"""

import re

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from rest_framework.authtoken.models import Token

from onadata.apps.api.models.temp_token import TempToken

User = get_user_model()


class TestPasswordResetConfirm(TestCase):
    """POST /accounts/password/reset/confirm/<uidb64>/<token>/"""

    def setUp(self):
        # The reset-request flow rate-limits per email in the cache; clear so
        # counters can't leak between tests in the same process.
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(
            username="bob", email="bob@columbia.edu", password="bobbob"
        )
        # Token is auto-created by a post_save signal on User creation.
        self.old_token = Token.objects.get(user=self.user)
        self.old_temp_token = TempToken.objects.create(user=self.user)

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def _get_set_password_url(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        confirm_url = f"/accounts/password/reset/confirm/{uid}/{token}/"

        # First GET swaps the real token for the "set-password" placeholder
        # and stashes it in the session, matching Django's reset-confirm flow.
        response = self.client.get(confirm_url)
        self.assertEqual(response.status_code, 302)

        return response["Location"]

    def test_reset_rotates_api_and_temp_tokens(self):
        """A successful native password reset invalidates old API/temp tokens."""
        set_password_url = self._get_set_password_url()

        response = self.client.post(
            set_password_url,
            {
                "new_password1": "a-new-strong-pass1",
                "new_password2": "a-new-strong-pass1",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("a-new-strong-pass1"))

        self.assertFalse(Token.objects.filter(key=self.old_token.key).exists())
        self.assertFalse(TempToken.objects.filter(key=self.old_temp_token.key).exists())
        self.assertTrue(Token.objects.filter(user=self.user).exists())
        self.assertTrue(TempToken.objects.filter(user=self.user).exists())

    def test_full_reset_flow_via_emailed_link(self):
        """A reset completed through the actual emailed link rotates tokens.

        Splices the request and confirm halves together: the confirm URL is
        extracted from the sent email rather than hand-built.
        """
        response = self.client.post(
            "/accounts/password/reset/", {"email": self.user.email}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(
            r"/accounts/password/reset/confirm/[^/\s]+/[^/\s]+/",
            mail.outbox[0].body,
        )
        self.assertIsNotNone(match, mail.outbox[0].body)

        response = self.client.get(match.group(0))
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            response["Location"],
            {
                "new_password1": "a-new-strong-pass1",
                "new_password2": "a-new-strong-pass1",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("a-new-strong-pass1"))
        self.assertFalse(Token.objects.filter(key=self.old_token.key).exists())
        self.assertFalse(TempToken.objects.filter(key=self.old_temp_token.key).exists())

    def test_failed_reset_does_not_rotate_tokens(self):
        """An invalid submission (e.g. mismatched passwords) changes nothing."""
        set_password_url = self._get_set_password_url()

        response = self.client.post(
            set_password_url,
            {"new_password1": "a-new-strong-pass1", "new_password2": "mismatched"},
        )
        self.assertEqual(response.status_code, 200)

        self.assertTrue(Token.objects.filter(key=self.old_token.key).exists())
        self.assertTrue(TempToken.objects.filter(key=self.old_temp_token.key).exists())
