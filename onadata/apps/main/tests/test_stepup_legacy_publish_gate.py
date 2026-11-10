# -*- coding: utf-8 -*-
"""
Tests for the step-up gate on making a form or its data public from the
legacy form edit page.
"""

from django.test.utils import override_settings
from django.urls import reverse

from django_otp.plugins.otp_totp.models import TOTPDevice
from oidc.stepup_grants import issue_grant, spend_grant

from onadata.apps.logger.models import XForm
from onadata.apps.main.tests.test_base import TestBase
from onadata.apps.main.views import edit

PUBLISH_DATA = "publish-data"
SHARED_FLAGS = {"data": "shared_data", "form": "shared"}


@override_settings(
    STEP_UP={
        "MODE": "local",
        "ACTIONS": [PUBLISH_DATA],
        "NO_FACTOR_POLICY": "skip_gate",
    }
)
class TestLegacyPublishDataGate(TestBase):
    """Sharing a form or its data opens it to anyone, so a stolen session
    alone must not be able to."""

    def setUp(self):
        super().setUp()
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self._publish_transportation_form()
        self.edit_url = reverse(
            edit,
            kwargs={"username": self.user.username, "id_string": self.xform.id_string},
        )

    def _toggle(self, target, **extra):
        return self.client.post(
            self.edit_url,
            {"toggle_shared": target, **extra},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def _flag(self, target):
        return getattr(XForm.objects.get(pk=self.xform.pk), SHARED_FLAGS[target])

    def _set_flag(self, target, value):
        XForm.objects.filter(pk=self.xform.pk).update(**{SHARED_FLAGS[target]: value})
        self.assertEqual(self._flag(target), value)

    def test_sharing_without_a_grant_is_refused(self):
        for target in SHARED_FLAGS:
            with self.subTest(target=target):
                self._set_flag(target, False)

                response = self._toggle(target)

                self.assertEqual(response.status_code, 403)
                self.assertFalse(self._flag(target))

    def test_a_grant_lets_the_sharing_through(self):
        for target in SHARED_FLAGS:
            with self.subTest(target=target):
                self._set_flag(target, False)
                grant = issue_grant(self.user.pk, PUBLISH_DATA)

                response = self._toggle(target, grant=grant)

                self.assertEqual(response.status_code, 200)
                self.assertTrue(self._flag(target))
                self.assertFalse(spend_grant(self.user.pk, PUBLISH_DATA, grant))

    def test_unsharing_is_not_challenged(self):
        for target in SHARED_FLAGS:
            with self.subTest(target=target):
                self._set_flag(target, True)

                response = self._toggle(target)

                self.assertEqual(response.status_code, 200)
                self.assertFalse(self._flag(target))
