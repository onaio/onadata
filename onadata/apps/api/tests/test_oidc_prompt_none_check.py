"""Startup check for OpenID Connect ``prompt=none`` support."""

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from oauth2_provider.oauth2_validators import OAuth2Validator

from onadata.apps.api.checks import oidc_prompt_none_check
from onadata.libs.authentication import OIDCPromptNoneMixin


class DeploymentValidator(OIDCPromptNoneMixin, OAuth2Validator):
    """A deployment-specific validator that includes the mixin."""


def _provider(validator_class, oidc_enabled=True):
    return {
        **settings.OAUTH2_PROVIDER,
        "OIDC_ENABLED": oidc_enabled,
        "OAUTH2_VALIDATOR_CLASS": validator_class,
    }


class OIDCPromptNoneCheckTestCase(SimpleTestCase):
    """The check fails startup only for a validator that would raise a 500."""

    @override_settings(
        OAUTH2_PROVIDER=_provider(
            "oauth2_provider.oauth2_validators.OAuth2Validator", oidc_enabled=False
        )
    )
    def test_passes_when_oidc_is_disabled(self):
        self.assertEqual(oidc_prompt_none_check(None), [])

    @override_settings(
        OAUTH2_PROVIDER=_provider(
            "onadata.libs.authentication.MasterReplicaOAuth2Validator"
        )
    )
    def test_passes_for_the_default_validator(self):
        self.assertEqual(oidc_prompt_none_check(None), [])

    @override_settings(
        OAUTH2_PROVIDER=_provider(
            "onadata.apps.api.tests.test_oidc_prompt_none_check.DeploymentValidator"
        )
    )
    def test_passes_for_any_validator_that_includes_the_mixin(self):
        self.assertEqual(oidc_prompt_none_check(None), [])

    @override_settings(
        OAUTH2_PROVIDER=_provider("oauth2_provider.oauth2_validators.OAuth2Validator")
    )
    def test_fails_for_a_validator_without_the_hooks(self):
        errors = oidc_prompt_none_check(None)

        self.assertEqual([error.id for error in errors], ["api.E005"])
        self.assertIn("validate_silent_authorization", errors[0].msg)
        self.assertIn("validate_silent_login", errors[0].msg)
