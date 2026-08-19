# -*- coding: utf-8 -*-
"""Tests for what a deployment reports it can manage about credentials."""

from django.test import TestCase, override_settings

from onadata.libs.stepup.capabilities import account_capabilities

SERVERS = {"kc": {"STEP_UP": {"CLAIM": "acr"}}}

FEDERATED = {
    "STEP_UP": {"MODE": "federated"},
    "OPENID_CONNECT_AUTH_SERVERS": SERVERS,
    "STEP_UP_IDP_NAME": "",
}


@override_settings(STEP_UP={"MODE": "local"}, ENABLE_TWO_FACTOR=False)
class TestTwoFactorDisabled(TestCase):
    """A deployment that never enabled two-factor manages none of it.

    /api/v1/totp/* answers 404 there, and this endpoint exists so a client can
    avoid offering a control the server refuses -- reporting the controls as
    available would make it the cause of exactly that.
    """

    def test_the_two_factor_controls_are_all_unavailable(self):
        capabilities = account_capabilities()["twoFactor"]

        for control in ("enroll", "disable", "recoveryCodes", "verify"):
            with self.subTest(control=control):
                self.assertFalse(capabilities[control])

    def test_changing_a_password_is_unaffected(self):
        """Only the second factor is gated; OnaData still owns the password."""
        self.assertTrue(account_capabilities()["password"]["change"])


class TestAccountCapabilities(TestCase):
    @override_settings(STEP_UP={"MODE": "local"})
    def test_onadata_owning_identity_can_manage_everything(self):
        caps = account_capabilities()

        self.assertTrue(caps["password"]["change"])
        self.assertEqual(caps["twoFactor"]["managedBy"], "onadata")
        self.assertTrue(caps["twoFactor"]["enroll"])
        self.assertEqual(caps["identityProvider"], "")

    @override_settings(**FEDERATED)
    def test_a_federated_deployment_manages_no_credentials(self):
        """There is no OnaData password to change and no factor to enrol --
        offering either sends the user at a control the server refuses.

        The provider is reported unnamed rather than guessed: auth-server keys
        are internal slugs, and title-casing one invents a name users do not
        recognise, so clients render generic copy instead.
        """
        caps = account_capabilities()

        self.assertFalse(caps["password"]["change"])
        self.assertEqual(caps["twoFactor"]["managedBy"], "idp")
        self.assertFalse(caps["twoFactor"]["enroll"])
        self.assertFalse(caps["twoFactor"]["disable"])
        self.assertFalse(caps["twoFactor"]["recoveryCodes"])
        self.assertEqual(caps["identityProvider"], "")

    @override_settings(**{**FEDERATED, "STEP_UP_IDP_NAME": "Acme SSO"})
    def test_a_deployment_fronts_a_name_its_users_recognise(self):
        self.assertEqual(account_capabilities()["identityProvider"], "Acme SSO")
