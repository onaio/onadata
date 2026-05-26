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

    def test_organization_account_does_not_block_human_with_shared_email(self):
        """
        An organization account that shares an email (and password) with a
        human account must not block the human from logging in by email; the
        org candidate is skipped, not used to abort the whole lookup.
        """
        org = User.objects.create_user(
            username="acme-org",
            email="team@example.com",
            password="shared-pass",  # nosec B106
        )
        alice = User.objects.create_user(
            username="alice",
            email="team@example.com",
            password="shared-pass",  # nosec B106
        )
        with patch(
            "onadata.apps.main.backends.is_organization_user",
            side_effect=lambda user: user == org,
        ):
            self.assertEqual(
                self.backend.authenticate(
                    None,
                    username="team@example.com",
                    password="shared-pass",  # nosec B106
                ),
                alice,
            )

    def test_user_with_unusable_password_cannot_log_in(self):
        """
        A ``User`` created without a usable password -- as organization rows
        are (see ``create_organization_object``) -- never matches and never
        authenticates. No ``is_organization_user`` patch here: the rejection
        must rest on the unusable password itself, not the org guard.
        """
        user = User.objects.create(username="beta-org", email="beta@example.com")
        user.set_unusable_password()
        user.save()
        self.assertIsNone(
            self.backend.authenticate(
                None, username="beta-org", password="anything"  # nosec B106
            )
        )

    def test_inactive_user_cannot_authenticate(self):
        """
        An ``is_active=False`` account is rejected even with a valid password,
        matching Django ``ModelBackend.user_can_authenticate`` enforcement.
        """
        User.objects.create_user(
            username="frozen",
            email="frozen@example.com",
            password="secret",  # nosec B106
            is_active=False,
        )
        self.assertIsNone(
            self.backend.authenticate(
                None, username="frozen", password="secret"  # nosec B106
            )
        )

    def test_value_matching_one_username_and_another_email(self):
        """
        When the supplied value is one account's username and another
        account's email, the unique username match takes precedence when its
        password verifies; otherwise the email-matched account is resolved.
        """
        alice = User.objects.create_user(
            username="user@example.com",
            email="alice@example.com",
            password="alice-pass",  # nosec B106
        )
        bob = User.objects.create_user(
            username="bob",
            email="user@example.com",
            password="bob-pass",  # nosec B106
        )
        # Username match wins when its password is supplied...
        self.assertEqual(
            self.backend.authenticate(
                None, username="user@example.com", password="alice-pass"  # nosec B106
            ),
            alice,
        )
        # ...otherwise the email-matched account is resolved by password.
        self.assertEqual(
            self.backend.authenticate(
                None, username="user@example.com", password="bob-pass"  # nosec B106
            ),
            bob,
        )

    def test_username_case_variants_resolve_to_own_account(self):
        """
        Distinct username case-variants each authenticate with their own
        password instead of the lowest-PK match shadowing the others.
        """
        upper = User.objects.create_user(
            username="Casey",
            email="casey1@example.com",
            password="upper-pass",  # nosec B106
        )
        lower = User.objects.create_user(
            username="casey",
            email="casey2@example.com",
            password="lower-pass",  # nosec B106
        )
        self.assertEqual(
            self.backend.authenticate(
                None, username="casey", password="lower-pass"  # nosec B106
            ),
            lower,
        )
        self.assertEqual(
            self.backend.authenticate(
                None, username="Casey", password="upper-pass"  # nosec B106
            ),
            upper,
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
