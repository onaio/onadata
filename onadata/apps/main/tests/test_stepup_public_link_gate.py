# -*- coding: utf-8 -*-
"""
Tests for the step-up gate on turning on a form's public link from the
legacy form permissions page.
"""

from django.test.utils import override_settings
from django.urls import reverse

from django_otp.plugins.otp_totp.models import TOTPDevice
from oidc.stepup_grants import issue_grant, spend_grant

from onadata.apps.main.models import MetaData
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.views import set_perm

PUBLISH_DATA = "publish-data"


@override_settings(
    STEP_UP={
        "MODE": "local",
        "ACTIONS": [PUBLISH_DATA],
        "NO_FACTOR_POLICY": "skip_gate",
    }
)
class TestPublicLinkGate(TestBase):
    """A public link opens the form to anyone holding it, so a stolen session
    alone must not be able to turn it on."""

    def setUp(self):
        super().setUp()
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self._publish_transportation_form()
        self.perm_url = reverse(
            set_perm,
            kwargs={"username": self.user.username, "id_string": self.xform.id_string},
        )

    def _set_link(self, for_user, **extra):
        return self.client.post(
            self.perm_url,
            {"perm_type": "link", "for_user": for_user, **extra},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def _link_is_on(self):
        return bool(MetaData.public_link(self.xform))

    def _turn_link(self, value):
        MetaData.public_link(self.xform, value)
        self.assertEqual(self._link_is_on(), value)

    def test_turning_the_link_on_without_a_grant_is_refused(self):
        for for_user in ("all", "toggle"):
            with self.subTest(for_user=for_user):
                self._turn_link(False)

                response = self._set_link(for_user)

                self.assertEqual(response.status_code, 403)
                self.assertFalse(self._link_is_on())

    def test_a_grant_lets_the_link_on(self):
        for for_user in ("all", "toggle"):
            with self.subTest(for_user=for_user):
                self._turn_link(False)
                grant = issue_grant(self.user.pk, PUBLISH_DATA)

                response = self._set_link(for_user, grant=grant)

                self.assertEqual(response.status_code, 200)
                self.assertTrue(self._link_is_on())
                self.assertFalse(spend_grant(self.user.pk, PUBLISH_DATA, grant))

    def test_turning_the_link_off_is_not_challenged(self):
        for for_user in ("none", "toggle"):
            with self.subTest(for_user=for_user):
                self._turn_link(False)
                self.assertEqual(self._set_link("all").status_code, 403)
                self._turn_link(True)

                response = self._set_link(for_user)

                self.assertEqual(response.status_code, 200)
                self.assertFalse(self._link_is_on())

    def test_an_already_on_link_is_not_challenged(self):
        self._turn_link(True)

        response = self._set_link("all")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._link_is_on())
