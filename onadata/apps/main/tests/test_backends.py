# -*- coding: utf-8 -*-
"""
Tests for the custom authentication backend in onadata.apps.main.backends.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from onadata.apps.main.backends import ModelBackend

User = get_user_model()


class TestModelBackend(TestCase):
    """Tests for the email/username authentication backend."""

    def setUp(self):
        self.backend = ModelBackend()

    def test_authenticate_with_username(self):
        user = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="secret",  # nosec B106
        )
        self.assertEqual(
            self.backend.authenticate(
                None, username="alice", password="secret"  # nosec B106
            ),
            user,
        )

    def test_username_is_case_insensitive(self):
        user = User.objects.create_user(
            username="Alice",
            email="alice@example.com",
            password="secret",  # nosec B106
        )
        self.assertEqual(
            self.backend.authenticate(
                None, username="alice", password="secret"  # nosec B106
            ),
            user,
        )

    def test_authenticate_with_email(self):
        user = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="secret",  # nosec B106
        )
        self.assertEqual(
            self.backend.authenticate(
                None, username="bob@example.com", password="secret"  # nosec B106
            ),
            user,
        )

    def test_wrong_password_returns_none(self):
        User.objects.create_user(
            username="carol",
            email="carol@example.com",
            password="secret",  # nosec B106
        )
        self.assertIsNone(
            self.backend.authenticate(
                None, username="carol", password="nope"  # nosec B106
            )
        )

    def test_shared_email_resolves_to_account_matching_password(self):
        """
        When two accounts share an email, logging in by email returns the
        account whose password verifies rather than an arbitrary ``.first()``.
        """
        User.objects.create_user(
            username="john",
            email="team@example.com",
            password="john-pass",  # nosec B106
        )
        jane = User.objects.create_user(
            username="jane",
            email="team@example.com",
            password="jane-pass",  # nosec B106
        )
        self.assertEqual(
            self.backend.authenticate(
                None, username="team@example.com", password="jane-pass"  # nosec B106
            ),
            jane,
        )

    def test_shared_email_does_not_block_valid_credentials(self):
        """
        A user with valid credentials for the *first* duplicate must still
        authenticate by email.
        """
        john = User.objects.create_user(
            username="john",
            email="team@example.com",
            password="john-pass",  # nosec B106
        )
        User.objects.create_user(
            username="jane",
            email="team@example.com",
            password="jane-pass",  # nosec B106
        )
        self.assertEqual(
            self.backend.authenticate(
                None, username="team@example.com", password="john-pass"  # nosec B106
            ),
            john,
        )

    def test_username_resolves_to_own_account(self):
        """A unique username always resolves to its own account."""
        dave = User.objects.create_user(
            username="dave",
            email="dave@example.com",
            password="dave-pass",  # nosec B106
        )
        self.assertEqual(
            self.backend.authenticate(
                None, username="dave", password="dave-pass"  # nosec B106
            ),
            dave,
        )

    def test_organization_account_cannot_log_in(self):
        """
        An organization account is never loginnable, even when the supplied
        credentials match it.
        """
        User.objects.create_user(
            username="acme-org",
            email="acme@example.com",
            password="secret",  # nosec B106
        )
        with patch(
            "onadata.apps.main.backends.is_organization_user", return_value=True
        ):
            self.assertIsNone(
                self.backend.authenticate(
                    None, username="acme-org", password="secret"  # nosec B106
                )
            )

    def test_returns_none_when_no_match(self):
        self.assertIsNone(
            self.backend.authenticate(
                None, username="ghost", password="x"  # nosec B106
            )
        )

    def test_returns_none_without_credentials(self):
        self.assertIsNone(self.backend.authenticate(None))
        self.assertIsNone(self.backend.authenticate(None, username="alice"))
