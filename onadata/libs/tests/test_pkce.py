"""Focused tests for the effective PKCE S256 validator policy."""

from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from oauth2_provider.models import get_application_model
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauthlib.common import Request
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError, InvalidRequestError

from onadata.libs.authentication import (
    MasterReplicaOAuth2Validator,
    is_pkce_s256_enforced,
)


class PKCETestMixin:
    """Build OAuth applications without database writes."""

    @staticmethod
    def application(grant_type=None, pk=None, created=None):
        application_model = get_application_model()
        application = application_model(
            client_id="pkce-test-client",
            client_type=application_model.CLIENT_PUBLIC,
            authorization_grant_type=(
                grant_type or application_model.GRANT_AUTHORIZATION_CODE
            ),
        )
        application.pk = pk
        application.created = created
        return application

    @staticmethod
    def request(application, challenge=None, challenge_method=None):
        request = Request("https://server.example/o/authorize/")
        request.client = application
        request.code_challenge = challenge
        request.code_challenge_method = challenge_method
        return request


class TestPKCES256Settings(PKCETestMixin, SimpleTestCase):
    def test_source_default_is_enforce(self):
        self.assertEqual(settings.OAUTH2_PKCE_S256_MODE, "enforce")
        self.assertIsNone(settings.OAUTH2_PKCE_S256_MIGRATION_CUTOFF)
        self.assertIsNone(settings.OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT)

    def test_unsaved_code_application_is_enforced_before_any_write(self):
        self.assertTrue(is_pkce_s256_enforced(self.application()))

    @override_settings(OAUTH2_PKCE_S256_MODE="observe")
    def test_observe_mode_does_not_enforce_unsaved_code_application(self):
        self.assertFalse(is_pkce_s256_enforced(self.application()))

    def test_non_code_grants_are_not_subject_to_pkce(self):
        application_model = get_application_model()
        for grant_type in (
            application_model.GRANT_CLIENT_CREDENTIALS,
            application_model.GRANT_PASSWORD,
            application_model.GRANT_IMPLICIT,
            application_model.GRANT_DEVICE_CODE,
        ):
            with self.subTest(grant_type=grant_type):
                self.assertFalse(is_pkce_s256_enforced(self.application(grant_type)))

    def test_invalid_modes_fail_closed(self):
        for mode in (None, "", "ENFORCE", "invalid", False, 1, lambda: "observe"):
            with self.subTest(mode=mode), override_settings(OAUTH2_PKCE_S256_MODE=mode):
                with self.assertRaises(ImproperlyConfigured):
                    is_pkce_s256_enforced(self.application())

    def test_invalid_migration_timestamps_fail_closed(self):
        invalid_values = (
            "",
            0,
            timezone.now().replace(tzinfo=None),
            lambda: timezone.now(),
        )
        for setting_name in (
            "OAUTH2_PKCE_S256_MIGRATION_CUTOFF",
            "OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT",
        ):
            for value in invalid_values:
                with self.subTest(
                    setting_name=setting_name, value=value
                ), override_settings(**{setting_name: value}):
                    with self.assertRaises(ImproperlyConfigured):
                        is_pkce_s256_enforced(self.application())

    def test_migration_cutoff_and_expiry_must_be_configured_together(self):
        now = timezone.now()
        incomplete_settings = (
            {
                "OAUTH2_PKCE_S256_MIGRATION_CUTOFF": None,
                "OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT": now,
            },
            {
                "OAUTH2_PKCE_S256_MIGRATION_CUTOFF": now,
                "OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT": None,
            },
        )
        for values in incomplete_settings:
            with self.subTest(values=values), override_settings(**values):
                with self.assertRaises(ImproperlyConfigured):
                    is_pkce_s256_enforced(self.application(pk=1, created=now))

    def test_at_must_be_fixed_and_timezone_aware(self):
        with self.assertRaises(ValueError):
            is_pkce_s256_enforced(
                self.application(), at=timezone.now().replace(tzinfo=None)
            )


class TestEffectivePKCES256Policy(PKCETestMixin, SimpleTestCase):
    def setUp(self):
        self.now = timezone.now()
        self.cutoff = self.now - timedelta(days=1)
        self.application_instance = self.application(
            pk=123, created=self.cutoff - timedelta(microseconds=1)
        )

    def effective(self, **overrides):
        values = {
            "OAUTH2_PKCE_S256_MODE": "enforce",
            "OAUTH2_PKCE_S256_MIGRATION_CUTOFF": self.cutoff,
            "OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT": (self.now + timedelta(days=1)),
        }
        values.update(overrides)
        with override_settings(
            **values,
        ):
            return is_pkce_s256_enforced(self.application_instance, at=self.now)

    def test_old_application_before_expiry_preserves_prior_behavior(self):
        self.assertFalse(self.effective())

    def test_expiry_boundary_enforces(self):
        self.assertTrue(self.effective(OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT=self.now))

    def test_absent_migration_window_enforces(self):
        with override_settings(
            OAUTH2_PKCE_S256_MODE="enforce",
            OAUTH2_PKCE_S256_MIGRATION_CUTOFF=None,
            OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT=None,
        ):
            self.assertTrue(
                is_pkce_s256_enforced(self.application_instance, at=self.now)
            )

    def test_created_time_must_be_strictly_before_cutoff(self):
        for delta, expected in (
            (-timedelta(microseconds=1), False),
            (timedelta(0), True),
            (timedelta(microseconds=1), True),
        ):
            with self.subTest(delta=delta):
                self.application_instance.created = self.cutoff + delta
                self.assertEqual(self.effective(), expected)

    def test_missing_or_naive_created_time_cannot_receive_exemption(self):
        for created in (None, self.now.replace(tzinfo=None)):
            with self.subTest(created=created):
                self.application_instance.created = created
                self.assertTrue(self.effective())


@override_settings(
    OAUTH2_PKCE_S256_MODE="enforce",
    OAUTH2_PKCE_S256_MIGRATION_CUTOFF=None,
    OAUTH2_PKCE_S256_MIGRATION_EXPIRES_AT=None,
)
class TestPKCES256Validator(PKCETestMixin, SimpleTestCase):
    def setUp(self):
        self.application_instance = self.application()
        self.validator = MasterReplicaOAuth2Validator()

    def validate(self, challenge=None, method=None, response_type="code"):
        request = self.request(
            self.application_instance,
            challenge=challenge,
            challenge_method=method,
        )
        result = self.validator.validate_response_type(
            self.application_instance.client_id,
            response_type,
            self.application_instance,
            request,
        )
        return result, request

    def test_authorization_accepts_exact_s256(self):
        result, _request = self.validate("safe-category-only", "S256")
        self.assertTrue(result)

    def test_authorization_rejects_missing_plain_and_unsupported_methods(self):
        cases = (
            (None, None),
            ("challenge", None),
            ("challenge", "plain"),
            ("challenge", "s256"),
            ("challenge", "unsupported"),
        )
        for challenge, method in cases:
            with self.subTest(challenge=challenge, method=method):
                with self.assertRaises(InvalidRequestError):
                    self.validate(challenge, method)

    def test_openid_hybrid_authorization_requires_s256(self):
        application_model = get_application_model()
        self.application_instance.authorization_grant_type = (
            application_model.GRANT_OPENID_HYBRID
        )
        result, _request = self.validate(
            "safe-category-only", "S256", response_type="code id_token"
        )
        self.assertTrue(result)

        with self.assertRaises(InvalidRequestError):
            self.validate(response_type="code id_token")

    def test_is_pkce_required_uses_effective_application_policy(self):
        request = self.request(self.application_instance)
        self.assertTrue(
            self.validator.is_pkce_required(
                self.application_instance.client_id, request
            )
        )

    @patch.object(OAuth2Validator, "get_code_challenge_method", return_value="plain")
    def test_token_rejects_stored_plain_grant(self, _get_method):
        request = self.request(self.application_instance)
        with self.assertRaises(InvalidGrantError):
            self.validator.get_code_challenge_method("legacy-code", request)

    @patch.object(OAuth2Validator, "get_code_challenge_method", return_value="S256")
    def test_token_accepts_stored_s256_grant(self, _get_method):
        request = self.request(self.application_instance)
        self.assertEqual(
            self.validator.get_code_challenge_method("safe-code", request),
            "S256",
        )

    def test_subclass_inherits_s256_enforcement(self):
        class ClaimsValidator(MasterReplicaOAuth2Validator):
            pass

        request = self.request(self.application_instance)
        with self.assertRaises(InvalidRequestError):
            ClaimsValidator().validate_response_type(
                self.application_instance.client_id,
                "code",
                self.application_instance,
                request,
            )


@override_settings(OAUTH2_PKCE_S256_MODE="observe")
class TestPKCEObservation(PKCETestMixin, SimpleTestCase):
    def test_observation_uses_only_allowlisted_fields(self):
        application = self.application(pk=321)
        request = self.request(
            application,
            challenge="do-not-log-this-challenge",
            challenge_method="unrecognized-do-not-log",
        )

        with patch(
            "onadata.libs.authentication.PKCE_MIGRATION_LOGGER.info"
        ) as log_info:
            self.assertTrue(
                MasterReplicaOAuth2Validator().validate_response_type(
                    application.client_id,
                    "code",
                    application,
                    request,
                )
            )

        log_info.assert_called_once_with(
            "pkce_migration",
            extra={
                "application_pk": 321,
                "client_type": application.CLIENT_PUBLIC,
                "grant_type": application.GRANT_AUTHORIZATION_CODE,
                "challenge_absent": False,
                "challenge_method_category": "unsupported",
            },
        )

    @patch.object(OAuth2Validator, "get_code_challenge_method", return_value="plain")
    def test_observe_mode_retains_stored_grant_behavior(self, _get_method):
        application = self.application()
        request = self.request(application)
        self.assertEqual(
            MasterReplicaOAuth2Validator().get_code_challenge_method(
                "legacy-code", request
            ),
            "plain",
        )
