# -*- coding: utf-8 -*-
"""Tests for the native /accounts/password/reset/ request flow.

The API's email-sending reset endpoint has been removed; this flow is the
only one that sends reset emails. It must keep the account rules the API
path enforced: skip organization accounts and rate limit per email.
"""

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase

from onadata.apps.api.models.organization_profile import OrganizationProfile

User = get_user_model()

RESET_URL = "/accounts/password/reset/"


class TestPasswordResetRequest(TestCase):
    """POST /accounts/password/reset/"""

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(
            username="bob", email="bob@columbia.edu", password="bobbob"
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_sends_email_for_active_user(self):
        """An active user with a usable password gets exactly one reset email."""
        response = self.client.post(RESET_URL, {"email": self.user.email})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn("/accounts/password/reset/confirm/", mail.outbox[0].body)

    def test_excludes_organization_accounts(self):
        """No reset email is sent for an organization account's email.

        Organization ``User`` rows are created without a real password, but
        their empty-string hash passes ``has_usable_password()``, so the
        stock form would email them.
        """
        org_user = User.objects.create(username="testorg", email="org@example.com")
        OrganizationProfile.objects.create(
            creator=self.user, user=org_user, name="Test Organization"
        )

        response = self.client.post(RESET_URL, {"email": org_user.email})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_shared_email_only_regular_user_emailed(self):
        """An email shared by an org and a regular user reaches only the user.

        The org exclusion must drop just the organization account, not every
        account matching the email.
        """
        shared_email = "shared@example.com"
        org_user = User.objects.create(username="sharedorg", email=shared_email)
        OrganizationProfile.objects.create(
            creator=self.user, user=org_user, name="Shared Organization"
        )
        regular_user = User.objects.create_user(
            username="regularuser", email=shared_email, password="testpass123"
        )

        response = self.client.post(RESET_URL, {"email": shared_email})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [regular_user.email])
        self.assertIn(regular_user.username, mail.outbox[0].body)

    def test_excludes_users_with_unusable_password(self):
        """No reset email is sent for an account with an unusable password."""
        no_password = User.objects.create_user(
            username="nopassword", email="nopassword@example.com"
        )
        no_password.set_unusable_password()
        no_password.save()

        response = self.client.post(RESET_URL, {"email": no_password.email})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_excludes_inactive_users(self):
        """No reset email is sent for an inactive account."""
        inactive = User.objects.create_user(
            username="inactive", email="inactive@example.com", password="testpass123"
        )
        inactive.is_active = False
        inactive.save()

        response = self.client.post(RESET_URL, {"email": inactive.email})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_rate_limited_per_email(self):
        """Requests beyond MAX_PASSWORD_RESET_ATTEMPTS send no more emails."""
        for _ in range(3):
            response = self.client.post(RESET_URL, {"email": self.user.email})
            self.assertEqual(response.status_code, 302)

        self.assertEqual(len(mail.outbox), 3)

        # Over the limit; a case-varied email hits the same bucket. The
        # response is still the generic redirect so the limiter can't be
        # used to probe for accounts.
        response = self.client.post(RESET_URL, {"email": self.user.email.upper()})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 3)
