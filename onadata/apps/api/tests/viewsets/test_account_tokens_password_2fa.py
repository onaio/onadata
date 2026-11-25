"""
Tests that a password alone can't obtain the account's own tokens once the
account has a second factor.
"""

from types import SimpleNamespace

from django.core.cache import cache
from django.test import override_settings

from django_digest.test import BasicAuth, DigestAuth
from django_otp.util import random_hex
from rest_framework.authtoken.models import Token

from onadata.apps.api.models.encrypted_totp_device import EncryptedTOTPDevice
from onadata.apps.api.models.odk_token import ODKToken
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tests.viewsets.test_totp_viewset import TEST_ENCRYPTION_KEY
from onadata.apps.api.viewsets.connect_viewset import ConnectViewSet
from onadata.apps.api.viewsets.totp_viewset import TOTP_DEVICE_NAME
from onadata.apps.api.viewsets.user_profile_viewset import UserProfileViewSet
from onadata.libs.authentication import (
    DigestAuthentication,
    LockoutBasicAuthentication,
    TempTokenAuthentication,
    account_token_refusal,
)

REFUSED = (
    "Accounts with two-factor authentication cannot obtain API or ODK "
    "tokens with a password alone."
)
BASIC = (LockoutBasicAuthentication,)


@override_settings(TWO_FACTOR_FIELD_ENCRYPTION_KEYS=[TEST_ENCRYPTION_KEY])
class TestAccountTokensWithPasswordAndSecondFactor(TestAbstractViewSet):
    """Basic and Digest still sign the user in, but the account's tokens stay
    out of reach until the second factor is removed."""

    def setUp(self):
        super().setUp()
        # Failed-login lockouts live in the cache, which the test runner does
        # not roll back.
        cache.clear()
        self.addCleanup(cache.clear)
        self.device = EncryptedTOTPDevice(
            user=self.user, name=TOTP_DEVICE_NAME, confirmed=True
        )
        self.device.key = random_hex(20)
        self.device.save()

    def _basic(self, method, handler, view_class=ConnectViewSet, **kwargs):
        view = view_class.as_view({method: handler}, authentication_classes=BASIC)
        request = getattr(self.factory, method)("/", data=kwargs.pop("data", None))
        request.META.update(BasicAuth("bob", "bobbob")(request.META))
        request.session = self.client.session
        return view(request, **kwargs)

    def test_the_profile_carries_no_tokens(self):
        response = self._basic("get", "list")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "bob")
        self.assertNotIn("api_token", response.data)
        self.assertNotIn("temp_token", response.data)

        self.device.delete()
        response = self._basic("get", "list")

        self.assertEqual(response.data["api_token"], self.user.auth_token.key)

    def test_digest_gets_the_same_answer_as_basic(self):
        view = ConnectViewSet.as_view(
            {"get": "list"}, authentication_classes=(DigestAuthentication,)
        )
        challenge = view(self.factory.get("/"))
        request = self.factory.get("/")
        request.META.update(DigestAuth("bob", "bobbob")(request.META, challenge))
        request.session = self.client.session

        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "bob")
        self.assertNotIn("api_token", response.data)

    def test_the_api_token_cannot_be_regenerated(self):
        key = self.user.auth_token.key

        response = self._basic("get", "regenerate_auth_token")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(str(response.data["detail"]), REFUSED)
        self.assertEqual(Token.objects.get(user=self.user).key, key)

        self.device.delete()
        response = self._basic("get", "regenerate_auth_token")

        self.assertEqual(response.status_code, 201)

    def test_no_odk_token_is_handed_out(self):
        for method in ("get", "post"):
            response = self._basic(method, "odk_token")

            self.assertEqual(response.status_code, 403, method)
            self.assertEqual(str(response.data["detail"]), REFUSED)
        self.assertFalse(ODKToken.objects.filter(user=self.user).exists())

        self.device.delete()
        response = self._basic("post", "odk_token")

        self.assertEqual(response.status_code, 201)

    def test_changing_the_password_returns_no_tokens(self):
        old_key = self.user.auth_token.key
        data = {"current_password": "bobbob", "new_password": "bobbob1"}

        response = self._basic(
            "post", "change_password", UserProfileViewSet, data=data, user="bob"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"username": "bob"})
        self.assertNotEqual(Token.objects.get(user=self.user).key, old_key)

    def test_token_sign_ins_are_unaffected(self):
        request = SimpleNamespace(
            successful_authenticator=TempTokenAuthentication(), user=self.user
        )

        self.assertIsNone(account_token_refusal(request))

        request = SimpleNamespace(
            successful_authenticator=LockoutBasicAuthentication(), user=self.user
        )

        self.assertEqual(account_token_refusal(request), REFUSED)
