"""Tests for the public OAuth application registration command."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections
from django.test import (
    TestCase,
    TransactionTestCase,
    override_settings,
    skipUnlessDBFeature,
)
from django.utils import timezone

from oauth2_provider.models import get_application_model


class RegisterOAuthPublicApplicationTestCase(TestCase):
    """Exercise safe creation, verification, and conflict handling."""

    client_id = "public-client"
    owner_username = "public-client-owner"
    application_name = "Public client"
    redirect_uris = [
        "https://client.example.test/oauth/callback",
        "https://client.example.test/oauth/secondary-callback",
    ]

    def _command_arguments(self, **overrides):
        values = {
            "client_id": self.client_id,
            "owner_username": self.owner_username,
            "application_name": self.application_name,
            "redirect_uris": self.redirect_uris,
        }
        values.update(overrides)
        arguments = [
            "register_oauth_public_application",
            "--client-id",
            values["client_id"],
            "--owner-username",
            values["owner_username"],
            "--application-name",
            values["application_name"],
        ]
        for redirect_uri in values["redirect_uris"]:
            arguments.extend(["--redirect-uri", redirect_uri])
        return arguments

    def _call_command(self, **overrides):
        output = StringIO()
        call_command(*self._command_arguments(**overrides), stdout=output)
        return output.getvalue()

    def _secure_owner(self, username=None):
        owner = get_user_model().objects.create(
            username=username or self.owner_username,
            is_active=False,
            is_staff=False,
            is_superuser=False,
        )
        owner.set_unusable_password()
        owner.save(update_fields=["password"])
        owner.groups.clear()
        owner.user_permissions.clear()
        return owner

    def _application(self, owner=None, **overrides):
        application_model = get_application_model()
        values = {
            "user": owner or self._secure_owner(),
            "name": self.application_name,
            "client_id": self.client_id,
            "client_type": application_model.CLIENT_PUBLIC,
            "authorization_grant_type": (application_model.GRANT_AUTHORIZATION_CODE),
            "redirect_uris": " ".join(self.redirect_uris),
            "skip_authorization": False,
            "algorithm": application_model.NO_ALGORITHM,
        }
        values.update(overrides)
        return application_model.objects.create(**values)

    def test_creates_secure_owner_and_public_application(self):
        output = self._call_command()

        owner = get_user_model().objects.get(username=self.owner_username)
        application = get_application_model().objects.get(client_id=self.client_id)
        self.assertFalse(owner.is_active)
        self.assertFalse(owner.has_usable_password())
        self.assertFalse(owner.is_staff)
        self.assertFalse(owner.is_superuser)
        self.assertFalse(owner.groups.exists())
        self.assertFalse(owner.user_permissions.exists())
        self.assertIsNone(
            authenticate(username=self.owner_username, password="anything")
        )
        self.assertEqual(application.user, owner)
        self.assertEqual(application.client_type, application.CLIENT_PUBLIC)
        self.assertEqual(
            application.authorization_grant_type,
            application.GRANT_AUTHORIZATION_CODE,
        )
        self.assertEqual(
            set(application.redirect_uris.split()), set(self.redirect_uris)
        )
        self.assertFalse(application.skip_authorization)
        self.assertEqual(application.algorithm, application.NO_ALGORITHM)
        self.assertEqual(output, "Created OAuth registration.\n")
        self.assertNotIn(application.client_secret, output)

    def test_second_identical_invocation_does_not_change_records(self):
        self._call_command()
        application = get_application_model().objects.get(client_id=self.client_id)
        original_values = (
            get_user_model().objects.count(),
            get_application_model().objects.count(),
            application.updated,
        )

        output = self._call_command()

        application.refresh_from_db()
        current_values = (
            get_user_model().objects.count(),
            get_application_model().objects.count(),
            application.updated,
        )
        self.assertEqual(current_values, original_values)
        self.assertEqual(output, "Verified OAuth registration.\n")

    def test_reuses_only_an_already_secure_dedicated_owner(self):
        owner = self._secure_owner()

        self.assertEqual(self._call_command(), "Created OAuth registration.\n")

        owner.refresh_from_db()
        self.assertFalse(owner.is_active)
        self.assertFalse(owner.has_usable_password())
        self.assertEqual(
            get_application_model().objects.get(client_id=self.client_id).user,
            owner,
        )

    @override_settings(OAUTH2_PKCE_S256_MODE="observe")
    def test_observe_mode_fails_before_creating_owner_or_application(self):
        with self.assertRaisesRegex(CommandError, "S256 is not effective"):
            self._call_command()

        self.assertFalse(
            get_user_model().objects.filter(username=self.owner_username).exists()
        )
        self.assertFalse(
            get_application_model().objects.filter(client_id=self.client_id).exists()
        )

    def test_active_legacy_window_prevents_verification(self):
        application = self._application()
        now = timezone.now()
        get_application_model().objects.filter(pk=application.pk).update(
            created=now - timedelta(days=2)
        )
        application.refresh_from_db()
        with override_settings(
            OAUTH2_PKCE_S256_MODE="enforce",
            OAUTH2_PKCE_S256_MIGRATION_CUTOFF=now - timedelta(days=1),
            OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT=now + timedelta(days=1),
        ):
            with self.assertRaisesRegex(CommandError, "S256 is not effective"):
                self._call_command()

    def test_active_legacy_window_does_not_exempt_new_registration(self):
        now = timezone.now()
        with override_settings(
            OAUTH2_PKCE_S256_MODE="enforce",
            OAUTH2_PKCE_S256_MIGRATION_CUTOFF=now - timedelta(days=1),
            OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT=now + timedelta(days=1),
        ):
            self.assertEqual(self._call_command(), "Created OAuth registration.\n")

    def test_verifies_existing_compliant_application(self):
        self._application()

        output = self._call_command()

        self.assertEqual(output, "Verified OAuth registration.\n")

    def test_rejects_owner_that_can_sign_in_without_repairing_it(self):
        owner = get_user_model().objects.create_user(
            username=self.owner_username,
            password="existing-password",
            is_active=True,
        )
        password = owner.password

        with self.assertRaisesRegex(CommandError, "owner can sign in"):
            self._call_command()

        owner.refresh_from_db()
        self.assertTrue(owner.is_active)
        self.assertEqual(owner.password, password)
        self.assertFalse(
            get_application_model().objects.filter(client_id=self.client_id).exists()
        )

    def test_rejects_inactive_owner_with_usable_password(self):
        owner = get_user_model().objects.create_user(
            username=self.owner_username,
            password="existing-password",
            is_active=False,
        )

        with self.assertRaisesRegex(CommandError, "owner can sign in"):
            self._call_command()

        owner.refresh_from_db()
        self.assertTrue(owner.has_usable_password())

    def test_rejects_staff_superuser_group_and_direct_permission_owners(self):
        permission = Permission.objects.order_by("pk").first()
        cases = ("staff", "superuser", "group", "permission")
        for case in cases:
            with self.subTest(case=case):
                owner = self._secure_owner(f"{self.owner_username}-{case}")
                if case == "staff":
                    owner.is_staff = True
                    owner.save(update_fields=["is_staff"])
                elif case == "superuser":
                    owner.is_superuser = True
                    owner.save(update_fields=["is_superuser"])
                elif case == "group":
                    owner.groups.add(Group.objects.create(name=f"group-{case}"))
                else:
                    owner.user_permissions.add(permission)

                with self.assertRaisesRegex(CommandError, "privileges"):
                    self._call_command(owner_username=owner.username)

                self.assertFalse(
                    get_application_model()
                    .objects.filter(client_id=self.client_id)
                    .exists()
                )

    def test_rejects_owner_of_an_unrelated_application(self):
        owner = self._secure_owner()
        application_model = get_application_model()
        application_model.objects.create(
            user=owner,
            name="Unrelated",
            client_id="unrelated-client",
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_CLIENT_CREDENTIALS,
        )

        with self.assertRaisesRegex(CommandError, "unrelated OAuth application"):
            self._call_command()

        self.assertFalse(
            application_model.objects.filter(client_id=self.client_id).exists()
        )

    def test_rejects_client_id_owned_by_another_user(self):
        application = self._application(owner=self._secure_owner("different-owner"))
        original_updated = application.updated

        with self.assertRaisesRegex(CommandError, "different owner"):
            self._call_command()

        application.refresh_from_db()
        self.assertEqual(application.updated, original_updated)

    def test_rejects_existing_application_contract_conflicts(self):
        application_model = get_application_model()
        cases = {
            "confidential": {
                "client_type": application_model.CLIENT_CONFIDENTIAL,
            },
            "another grant": {
                "authorization_grant_type": application_model.GRANT_PASSWORD,
            },
            "callback URL": {
                "redirect_uris": "https://unexpected.example.test/callback",
            },
            "name": {"name": "Unexpected name"},
            "skips": {"skip_authorization": True},
            "OIDC": {"algorithm": application_model.RS256_ALGORITHM},
        }
        for label, updates in cases.items():
            with self.subTest(conflict=label):
                application = self._application()
                application_model.objects.filter(pk=application.pk).update(**updates)

                with self.assertRaises(CommandError):
                    self._call_command()

                application.delete()
                application.user.delete()

    def test_rejects_duplicate_or_empty_redirect_uri(self):
        for redirect_uris in (
            [self.redirect_uris[0], self.redirect_uris[0]],
            [""],
        ):
            with self.subTest(redirect_uris=redirect_uris):
                with self.assertRaises(CommandError):
                    self._call_command(redirect_uris=redirect_uris)

        self.assertFalse(
            get_user_model().objects.filter(username=self.owner_username).exists()
        )


@skipUnlessDBFeature("has_select_for_update")
class RegisterOAuthPublicApplicationConcurrencyTestCase(TransactionTestCase):
    """Concurrent command runs must converge on one registration."""

    def _invoke_command(self):
        output = StringIO()
        try:
            call_command(
                "register_oauth_public_application",
                "--client-id",
                "concurrent-public-client",
                "--owner-username",
                "concurrent-public-owner",
                "--application-name",
                "Concurrent public client",
                "--redirect-uri",
                "https://client.example.test/oauth/callback",
                stdout=output,
            )
        except CommandError:
            result = "conflict"
        else:
            result = output.getvalue().strip()
        finally:
            close_old_connections()
        return result

    def test_concurrent_invocations_do_not_create_duplicate_records(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(lambda _index: self._invoke_command(), range(2))
            )

        self.assertTrue(any(result != "conflict" for result in results))
        self.assertEqual(
            get_user_model().objects.filter(username="concurrent-public-owner").count(),
            1,
        )
        application_model = get_application_model()
        application = application_model.objects.get(
            client_id="concurrent-public-client"
        )
        self.assertEqual(
            application_model.objects.filter(pk=application.pk).count(),
            1,
        )
