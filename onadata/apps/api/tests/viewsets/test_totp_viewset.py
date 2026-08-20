"""
Tests for the two-factor management endpoints.
"""

import hashlib
import hmac
import struct
import time
from contextlib import contextmanager
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import override_settings

import jwt
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.authtoken.models import Token
from two_factor.utils import default_device

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.viewsets.totp_viewset import (
    RECOVERY_CODE_COUNT,
    RECOVERY_DEVICE_NAME,
    TOTP_DEVICE_NAME,
    TOTPViewSet,
)

#: Any test spending two codes must move between windows: django-otp records
#: the counter a code was used at and refuses it again.
_clock_offset = 0.0


@contextmanager
def next_totp_window(step=30):
    """Advance far enough that the previous code is spent and a new one valid."""
    global _clock_offset
    _clock_offset += step
    offset = _clock_offset
    real_time = time.time
    with patch("time.time", lambda: real_time() + offset):
        yield


def current_code(hex_key, step=30, digits=6):
    """The code an authenticator app would be showing right now.

    Derived rather than mocked: patching verify_token would pass against a
    device generating codes no phone agrees with.

    Not ``django_otp.oath.totp``: that module binds ``time`` at import, so
    ``next_totp_window`` cannot move it. ``TOTPDevice.verify_token`` reads
    ``time.time()`` through the module and does follow the patch, so the two
    sides would drift apart.
    """
    counter = int(time.time()) // step
    mac = hmac.new(bytes.fromhex(hex_key), struct.pack(">Q", counter), hashlib.sha1)
    digest = mac.digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % (10**digits)).zfill(digits)


@override_settings(ENABLE_TWO_FACTOR=True)
class TestTOTPViewSet(TestAbstractViewSet):
    """The endpoints act on the authenticated user and nobody else."""

    def setUp(self):
        super().setUp()
        self.view = TOTPViewSet.as_view(
            {
                "get": "totp_status",
                "post": "enroll_start",
            }
        )

    def _sso(self, user=None):
        """Headers carrying the SSO cookie a signed-in browser would send.

        The real credential, not a stand-in: enrolment turns an API key
        away, so a test that faked the session would not be exercising the
        distinction it depends on.
        """
        config = settings.OPENID_CONNECT_VIEWSET_CONFIG
        token = jwt.encode(
            {"email": (user or self.user).email},
            config["JWT_SECRET_KEY"],
            algorithm=config["JWT_ALGORITHM"],
        )
        return {"HTTP_SSO": token}

    def _post_with_api_key(self, handler, data=None):
        view = TOTPViewSet.as_view({"post": handler})
        request = self.factory.post("/", data=data or {}, **self.extra)
        return view(request)

    def _post_session(self, handler, data=None):
        """Post as a signed-in browser rather than with an API key."""
        view = TOTPViewSet.as_view({"post": handler})
        request = self.factory.post("/", data=data or {}, **self._sso())
        return view(request)

    def _verify(self, data):
        """POST verify with an audience defaulted in.

        Most cases here are about whether a code is accepted at all, not
        about which operation the grant unlocks. The tests that care pass
        their own audience.
        """
        return self._post_with_api_key("verify", {"audience": "disable", **data})

    def _get_status(self):
        view = TOTPViewSet.as_view({"get": "totp_status"})
        return view(self.factory.get("/", **self.extra))

    def _enroll(self):
        """Take a user all the way through to a confirmed authenticator."""
        started = self._post_session("enroll_start")
        self.assertEqual(started.status_code, 201)
        device = TOTPDevice.objects.get(
            user=self.user, name=TOTP_DEVICE_NAME, confirmed=False
        )
        confirmed = self._post_session(
            "enroll_confirm", {"code": current_code(device.key)}
        )
        self.assertEqual(confirmed.status_code, 200)
        device.refresh_from_db()
        return device

    def test_enrolled_authenticator_is_the_login_view_default_device(self):
        """The enrolled device must be the one the login view challenges on.

        Enrolling under any other name leaves an account reporting two-factor
        as on while still logging in with a password alone. Asserted through
        the library's own lookup, so a rename upstream fails here.
        """
        device = self._enroll()

        self.assertEqual(default_device(self.user), device)

    def test_a_second_factor_of_another_kind_is_not_ignored(self):
        """A non-TOTP device named "default" still counts as a second factor.

        StaticDevice stands in for WebAuthn, the only non-TOTP plugin
        installed; what is under test is that the class does not decide.
        """
        device = StaticDevice.objects.create(
            user=self.user, name=TOTP_DEVICE_NAME, confirmed=True
        )
        self.assertEqual(default_device(self.user), device)

        response = self._post_with_api_key("disable")

        # 403 demands proof; a 200 saying enrolled: False would mean the
        # endpoint saw no second factor at all.
        self.assertEqual(response.status_code, 403)

        # The status route must agree with the gate, or it reports two-factor
        # off while every gated action says otherwise.
        status_body = self._get_status().data
        self.assertTrue(status_body["methods"])

    def test_recovery_codes_are_the_set_two_factors_backup_step_reads(self):
        """One recovery set, and it is the one the login wizard reads.

        The wizard's backup step takes ``staticdevice_set.first()`` without
        filtering on the name, so the set this module writes has to be the
        user's only static device or the wizard can verify against the wrong
        one.
        """
        self._enroll()

        self.assertEqual(RECOVERY_DEVICE_NAME, "backup")
        device = self.user.staticdevice_set.first()
        self.assertIsNotNone(device)
        self.assertEqual(device.token_set.count(), RECOVERY_CODE_COUNT)

    def test_status_reports_nothing_before_enrollment(self):
        response = self._get_status()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["methods"], [])
        self.assertEqual(
            response.data["recoveryCodes"], {"generated": False, "remaining": 0}
        )

    def test_enrollment_needs_a_code_from_the_device(self):
        """The pending device must not count as a second factor until the user
        has proved they can read it -- otherwise a misscanned QR locks them
        out of their own account."""
        self._post_session("enroll_start")
        response = self._post_session("enroll_confirm", {"code": "000000"})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            TOTPDevice.objects.filter(user=self.user, confirmed=True).exists()
        )
        self.assertEqual(self._get_status().data["methods"], [])

    def test_a_real_code_completes_enrollment(self):
        device = self._enroll()

        self.assertTrue(device.confirmed)
        methods = self._get_status().data["methods"]
        self.assertEqual(
            [(m["kind"], m["label"]) for m in methods],
            [("totp", TOTP_DEVICE_NAME)],
        )

    def test_enrolment_is_all_or_nothing(self):
        """An authenticator that confirmed while its recovery codes did not is
        one lost phone away from a locked account, so both land in the same
        transaction."""
        self._post_session("enroll_start")
        device = TOTPDevice.objects.get(user=self.user, confirmed=False)

        with (
            patch(
                "onadata.apps.api.viewsets.totp_viewset._regenerate_recovery_codes",
                side_effect=RuntimeError("codes could not be written"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self._post_session("enroll_confirm", {"code": current_code(device.key)})

        device.refresh_from_db()
        self.assertFalse(device.confirmed)

    def test_starting_again_replaces_the_pending_device(self):
        """Re-scanning must not leave the previous attempt behind: two
        unconfirmed devices means the code from either one works."""
        self._post_session("enroll_start")
        self._post_session("enroll_start")

        self.assertEqual(
            TOTPDevice.objects.filter(user=self.user, confirmed=False).count(), 1
        )

    def test_replacing_an_authenticator_needs_step_up(self):
        """Swapping the device is as much a change to the second factor as
        removing it, so a stolen session must not be able to do it quietly."""
        self._enroll()

        self.assertEqual(self._post_session("enroll_start").status_code, 403)

    def _replace_authenticator(self, old_device):
        """Run a full swap: step up with the old device, confirm a new one."""
        with next_totp_window():
            grant = self._verify(
                {"code": current_code(old_device.key), "audience": "enroll-start"},
            ).data["grant"]
        started = self._post_session("enroll_start", {"grant": grant})
        self.assertEqual(started.status_code, 201)
        replacement = TOTPDevice.objects.get(user=self.user, confirmed=False)
        with next_totp_window():
            confirmed = self._post_session(
                "enroll_confirm", {"code": current_code(replacement.key)}
            )
        self.assertEqual(confirmed.status_code, 200)
        replacement.refresh_from_db()
        return replacement

    def test_replacing_an_authenticator_revokes_the_old(self):
        """A swap must leave exactly one authenticator, and it must be the new
        one.

        default_device() answers with the first confirmed device named
        "default", not the newest, so an incumbent left behind stays the one
        the login wizard challenges on -- the rotation would not revoke it and
        the new device would not work.
        """
        old = self._enroll()

        new = self._replace_authenticator(old)

        self.assertEqual(
            list(
                TOTPDevice.objects.filter(user=self.user, confirmed=True).values_list(
                    "pk", flat=True
                )
            ),
            [new.pk],
        )
        self.assertFalse(TOTPDevice.objects.filter(pk=old.pk).exists())
        # Through the library's own lookup, which is what the wizard asks.
        self.assertEqual(default_device(User.objects.get(pk=self.user.pk)), new)

    def test_enrolling_supersedes_a_challengeable_device_of_another_kind(self):
        """Replacing the authenticator must clear whatever else the login view
        would challenge on, not only the TOTP rows this module creates --
        otherwise default_device() can answer with the leftover instead."""
        device = self._enroll()
        superseded = StaticDevice.objects.create(
            user=self.user, name=TOTP_DEVICE_NAME, confirmed=True
        )

        new = self._replace_authenticator(device)

        self.assertFalse(StaticDevice.objects.filter(pk=superseded.pk).exists())
        self.assertEqual(default_device(User.objects.get(pk=self.user.pk)), new)

    def test_disable_demands_a_current_code(self):
        """A stolen session cookie must not be enough to switch 2FA off --
        surviving exactly that is what the second factor is for."""
        self._enroll()

        response = self._post_with_api_key("disable", {"code": "000000"})

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            TOTPDevice.objects.filter(user=self.user, confirmed=True).exists()
        )

    def test_disable_with_a_current_code_removes_everything(self):
        device = self._enroll()
        with next_totp_window():
            self._post_with_api_key(
                "recovery_generate", {"code": current_code(device.key)}
            )
        with next_totp_window():
            response = self._post_with_api_key(
                "disable", {"code": current_code(device.key)}
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())
        self.assertFalse(StaticDevice.objects.filter(user=self.user).exists())

    def test_recovery_codes_need_an_authenticator_first(self):
        response = self._post_with_api_key("recovery_generate", {"code": "000000"})
        self.assertEqual(response.status_code, 409)

    def test_generating_recovery_codes_returns_them_once(self):
        device = self._enroll()

        with next_totp_window():
            response = self._post_with_api_key(
                "recovery_generate", {"code": current_code(device.key)}
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data["codes"]), RECOVERY_CODE_COUNT)
        self.assertEqual(
            self._get_status().data["recoveryCodes"],
            {"generated": True, "remaining": RECOVERY_CODE_COUNT},
        )

    def test_regenerating_replaces_rather_than_appends(self):
        """Spent codes left behind would make the remaining count a lie."""
        device = self._enroll()
        with next_totp_window():
            first = self._post_with_api_key(
                "recovery_generate", {"code": current_code(device.key)}
            )
        with next_totp_window():
            second = self._post_with_api_key(
                "recovery_generate", {"code": current_code(device.key)}
            )

        self.assertEqual(
            StaticToken.objects.filter(device__user=self.user).count(),
            RECOVERY_CODE_COUNT,
        )
        self.assertFalse(set(first.data["codes"]) & set(second.data["codes"]))

    def test_regenerating_recovery_codes_leaves_other_devices_alone(self):
        """Only the set this module manages is replaced. Clearing every static
        device would take an unrelated factor with it."""
        device = self._enroll()
        unrelated = StaticDevice.objects.create(
            user=self.user, name=TOTP_DEVICE_NAME, confirmed=True
        )

        with next_totp_window():
            response = self._post_with_api_key(
                "recovery_generate", {"code": current_code(device.key)}
            )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(StaticDevice.objects.filter(pk=unrelated.pk).exists())

    def test_a_recovery_code_can_stand_in_for_the_authenticator(self):
        """Someone who has lost their phone still has to be able to turn 2FA
        off, or the account is unrecoverable."""
        device = self._enroll()
        with next_totp_window():
            codes = self._post_with_api_key(
                "recovery_generate", {"code": current_code(device.key)}
            ).data["codes"]

        response = self._post_with_api_key("disable", {"code": codes[0]})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())

    def test_a_recovery_code_is_spent_by_use(self):
        device = self._enroll()
        with next_totp_window():
            codes = self._post_with_api_key(
                "recovery_generate", {"code": current_code(device.key)}
            ).data["codes"]

        self.assertEqual(self._verify({"code": codes[0]}).status_code, 200)
        self.assertEqual(self._verify({"code": codes[0]}).status_code, 403)

    def test_verify_accepts_a_current_code_and_changes_nothing(self):
        device = self._enroll()

        with next_totp_window():
            response = self._verify({"code": current_code(device.key)})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["verified"])
        self.assertTrue(
            TOTPDevice.objects.filter(user=self.user, confirmed=True).exists()
        )

    def test_verify_rejects_a_wrong_code(self):
        self._enroll()
        self.assertEqual(self._verify({"code": "000000"}).status_code, 403)

    def test_verify_method_scopes_the_check_to_the_named_factor(self):
        """A caller that names how it is proving itself is checked against
        that factor alone. Without the scope, adding any future method (a
        security key, say) would mean every code path accepts every
        credential kind, and the UI could never say which one failed."""
        device = self._enroll()
        with next_totp_window():
            codes = self._post_with_api_key(
                "recovery_generate", {"code": current_code(device.key)}
            ).data["codes"]

        # The scoped success goes first: a failed TOTP attempt (below) arms
        # django-otp's failure throttle on the device, which would reject even
        # a correct code for a while.
        with next_totp_window():
            scoped_ok = self._verify(
                {"code": current_code(device.key), "method": "totp"}
            )
            totp_as_recovery = self._verify(
                {"code": current_code(device.key), "method": "recovery"}
            )
            recovery_as_totp = self._verify({"code": codes[0], "method": "totp"})

        self.assertEqual(scoped_ok.status_code, 200)
        self.assertTrue(scoped_ok.data["verified"])
        self.assertEqual(totp_as_recovery.status_code, 403)
        self.assertEqual(recovery_as_totp.status_code, 403)

    def test_verify_without_a_method_accepts_any_factor(self):
        """Omitting ``method`` keeps the original contract: an authenticator
        code and a recovery code are both good, so existing callers do not
        have to name one."""
        device = self._enroll()
        with next_totp_window():
            codes = self._post_with_api_key(
                "recovery_generate", {"code": current_code(device.key)}
            ).data["codes"]

        with next_totp_window():
            with_totp = self._verify({"code": current_code(device.key)})
        with_recovery = self._verify({"code": codes[0]})

        self.assertEqual(with_totp.status_code, 200)
        self.assertEqual(with_recovery.status_code, 200)

    def test_verify_treats_an_explicit_null_method_as_any_factor(self):
        """A JSON null method must mean "any factor" (the omitted contract),
        not the string "None" -- otherwise clients sending an explicit null
        get a spurious 400."""
        device = self._enroll()
        view = TOTPViewSet.as_view({"post": "verify"})
        with next_totp_window():
            # JSON (not multipart) so the null survives to the view as None.
            request = self.factory.post(
                "/",
                data={
                    "code": current_code(device.key),
                    "method": None,
                    "audience": "disable",
                },
                format="json",
                **self.extra,
            )
            response = view(request)

        self.assertEqual(response.status_code, 200)

    def test_verify_rejects_a_method_it_does_not_know(self):
        """An unknown method is a caller bug (or a factor this server does
        not support yet) -- refuse loudly rather than fall back to trying
        everything, which would quietly widen the check again."""
        device = self._enroll()
        with next_totp_window():
            response = self._verify(
                {"code": current_code(device.key), "method": "webauthn"}
            )

        self.assertEqual(response.status_code, 400)

    def test_an_anonymous_caller_gets_nothing(self):
        """Identity comes from the forwarded SSO cookie. Without one there is
        no user to act on, and the endpoint must not fall back to anything."""
        view = TOTPViewSet.as_view({"get": "totp_status"})
        response = view(self.factory.get("/"))
        self.assertIn(response.status_code, (401, 403))

    def test_devices_are_named_so_they_can_be_found_again(self):
        device = self._enroll()
        with next_totp_window():
            self._post_with_api_key(
                "recovery_generate", {"code": current_code(device.key)}
            )

        self.assertEqual(device.name, TOTP_DEVICE_NAME)
        self.assertEqual(
            StaticDevice.objects.get(user=self.user).name, RECOVERY_DEVICE_NAME
        )

    def test_verify_issues_a_grant_the_next_call_can_spend(self):
        """
        Challenge first and then act second. djangio-otp records
        the counter a code was used at so the code cannot be resent. The
        grant carries proof to the next request."""
        device = self._enroll()

        with next_totp_window():
            grant = self._verify(
                {"code": current_code(device.key), "audience": "disable"},
            ).data["grant"]
        response = self._post_with_api_key("disable", {"grant": grant})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())

    def test_a_grant_is_spendable_only_on_what_it_was_earned_for(self):
        """Unscoped, a code collected to view recovery codes would switch
        two-factor off instead -- the user proved one thing and authorised
        another."""
        device = self._enroll()
        with next_totp_window():
            grant = self._verify(
                {
                    "code": current_code(device.key),
                    "audience": "recovery-generate",
                },
            ).data["grant"]

        response = self._post_with_api_key("disable", {"grant": grant})

        self.assertEqual(response.status_code, 403)
        self.assertTrue(TOTPDevice.objects.filter(user=self.user).exists())

    def test_verify_refuses_an_audience_the_deployment_does_not_know(self):
        """Omitted and mistyped are the same refusal, and neither costs a code.

        The audience is checked before the code is, so a client mistake is not
        paid for with the user's one-shot token -- they can retry with the
        same code once the caller is fixed.
        """
        device = self._enroll()

        with next_totp_window():
            # _post, not _verify: the helper supplies an audience, which is the
            # very thing these cases are about getting wrong.
            code = current_code(device.key)
            omitted = self._post_with_api_key("verify", {"code": code})
            mistyped = self._post_with_api_key(
                "verify", {"code": code, "audience": "diasble"}
            )
            still_good = self._post_with_api_key(
                "verify", {"code": code, "audience": "disable"}
            )

        self.assertEqual(omitted.status_code, 400)
        self.assertNotIn("grant", omitted.data)
        self.assertEqual(mistyped.status_code, 400)
        self.assertEqual(still_good.status_code, 200)

    def test_the_audience_refusal_does_not_echo_the_audience_back(self):
        """The message is static: this is unbounded caller input."""
        device = self._enroll()
        with next_totp_window():
            response = self._verify(
                {"code": current_code(device.key), "audience": "<script>alert(1)"},
            )

        self.assertNotIn("script", str(response.data))

    def test_enrolment_refuses_an_api_key(self):
        """With no factor enrolled there is no code to demand, so the
        credential is the only thing left to check.

        That state is asserted rather than inherited from setUp: it is the
        condition under test, not a detail of the fixture.
        """
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())

        response = self._post_with_api_key("enroll_start")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())

    def test_confirming_enrolment_refuses_an_api_key(self):
        """The second half of enrolment refuses a key for the same reason --
        and it is the half that hands back the recovery codes."""
        self._post_session("enroll_start")
        device = TOTPDevice.objects.get(user=self.user, confirmed=False)

        response = self._post_with_api_key(
            "enroll_confirm", {"code": current_code(device.key)}
        )

        self.assertEqual(response.status_code, 403)
        device.refresh_from_db()
        self.assertFalse(device.confirmed)

    def test_an_api_key_works_where_a_code_is_demanded(self):
        """Only enrolment is restricted.

        An API key is safe on the routes that demand a current code, which is
        the thing a stolen key does not have.
        """
        device = self._enroll()

        with next_totp_window():
            verified = self._verify({"code": current_code(device.key)})
        self.assertEqual(verified.status_code, 200)

        with next_totp_window():
            disabled = self._post_with_api_key(
                "disable", {"code": current_code(device.key)}
            )
        self.assertEqual(disabled.status_code, 200)

    def test_disable_removes_a_factor_of_another_kind(self):
        """Disable must clear whatever the login view would challenge on.

        _has_second_factor asks default_device(), which answers on a confirmed
        device of any class named "default". Removing only the TOTP and static
        rows would report two-factor as off while leaving such a device
        standing -- and this module cannot verify one, so the account would be
        challenged at login for a factor it could never disable.
        """
        device = self._enroll()
        other = StaticDevice.objects.create(
            user=self.user, name=TOTP_DEVICE_NAME, confirmed=True
        )

        with next_totp_window():
            response = self._post_with_api_key(
                "disable", {"code": current_code(device.key)}
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(StaticDevice.objects.filter(pk=other.pk).exists())
        self.assertIsNone(default_device(User.objects.get(pk=self.user.pk)))

    def test_disable_removes_a_half_finished_enrolment(self):
        """A pending device left behind would be confirmable afterwards."""
        device = self._enroll()
        with next_totp_window():
            grant = self._verify(
                {"code": current_code(device.key), "audience": "enroll-start"}
            ).data["grant"]
        self._post_session("enroll_start", {"grant": grant})
        self.assertTrue(
            TOTPDevice.objects.filter(user=self.user, confirmed=False).exists()
        )

        with next_totp_window():
            self._post_with_api_key("disable", {"code": current_code(device.key)})

        self.assertFalse(TOTPDevice.objects.filter(user=self.user).exists())

    def test_a_grant_is_single_use(self):
        device = self._enroll()
        with next_totp_window():
            grant = self._verify(
                {"code": current_code(device.key), "audience": "recovery-generate"}
            ).data["grant"]

        first = self._post_with_api_key("recovery_generate", {"grant": grant})
        second = self._post_with_api_key("recovery_generate", {"grant": grant})

        # The first spend has to succeed, or the second refusal proves nothing.
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 403)

    def test_a_forged_grant_is_refused(self):
        self._enroll()
        response = self._post_with_api_key("disable", {"grant": "not-a-real-grant"})
        self.assertEqual(response.status_code, 403)

    def test_a_grant_does_not_work_for_another_user(self):
        """Grants are keyed to the user who earned them, or one account's
        step-up would unlock every other."""
        device = self._enroll()
        with next_totp_window():
            grant = self._verify({"code": current_code(device.key)}).data["grant"]

        other = User.objects.create_user("mallory", "mallory@example.com", "pw")
        token, _ = Token.objects.get_or_create(user=other)
        # Mallory needs an authenticator of their own, or disable short-circuits
        # on "nothing to remove" and never consults the grant at all -- the test
        # would pass without the guard it is here to pin.
        TOTPDevice.objects.create(user=other, name=TOTP_DEVICE_NAME, confirmed=True)
        view = TOTPViewSet.as_view({"post": "disable"})
        request = self.factory.post(
            "/", data={"grant": grant}, HTTP_AUTHORIZATION=f"Token {token}"
        )

        self.assertEqual(view(request).status_code, 403)
        self.assertTrue(TOTPDevice.objects.filter(user=other).exists())

    def test_enrollment_payload_carries_the_secret_three_ways(self):
        """Three renderings of one secret: a QR to scan, the URI behind it,
        and base32 to type by hand. django-otp stores hex, which no
        authenticator app accepts."""
        import base64

        response = self._post_session("enroll_start")
        device = TOTPDevice.objects.get(user=self.user, confirmed=False)

        self.assertTrue(response.data["qrDataUrl"].startswith("data:image/png;base64,"))
        self.assertEqual(response.data["otpauthUri"], device.config_url)
        b32 = response.data["secretBase32"]
        padded = b32 + "=" * (-len(b32) % 8)
        self.assertEqual(base64.b32decode(padded).hex(), device.key)

    def test_viewing_returns_the_codes_that_still_work(self):
        """The same set, not a new one -- viewing must not invalidate."""
        device = self._enroll()
        with next_totp_window():
            generated = self._post_with_api_key(
                "recovery_generate", {"code": current_code(device.key)}
            )
        # The comparison below is only meaningful if a set was really issued:
        # two empty lists would match and prove nothing.
        self.assertEqual(generated.status_code, 201)
        with next_totp_window():
            viewed = self._post_with_api_key(
                "recovery_view", {"code": current_code(device.key)}
            )

        self.assertEqual(viewed.status_code, 200)
        self.assertEqual(
            sorted(viewed.data["codes"]), sorted(generated.data["codes"])
        )
        self.assertEqual(
            self._get_status().data["recoveryCodes"],
            {"generated": True, "remaining": RECOVERY_CODE_COUNT},
        )

    def test_viewing_refuses_without_a_current_code(self):
        """Session alone is not enough -- these are the last-resort secret."""
        device = self._enroll()
        with next_totp_window():
            generated = self._post_with_api_key(
                "recovery_generate", {"code": current_code(device.key)}
            )
        # Refusing to show nothing would pass this test for the wrong reason.
        self.assertEqual(generated.status_code, 201)

        response = self._post_with_api_key("recovery_view")

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("codes", response.data)

    def test_viewing_accepts_a_grant_minted_for_it(self):
        """The SPA spends a grant rather than re-prompting for a code."""
        device = self._enroll()
        with next_totp_window():
            generated = self._post_with_api_key(
                "recovery_generate", {"code": current_code(device.key)}
            )
        self.assertEqual(generated.status_code, 201)
        with next_totp_window():
            verified = self._post_with_api_key(
                "verify",
                {"code": current_code(device.key), "audience": "recovery-view"},
            )
        self.assertEqual(verified.status_code, 200)

        response = self._post_with_api_key(
            "recovery_view", {"grant": verified.data["grant"]}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["codes"]), RECOVERY_CODE_COUNT)

    def test_viewing_a_set_that_was_never_generated_is_a_404(self):
        # Enrolment issues a set of its own, so drop it: the case under test
        # is an account whose codes are gone, not one that never enrolled.
        device = self._enroll()
        StaticDevice.objects.filter(user=self.user).delete()

        with next_totp_window():
            response = self._post_with_api_key(
                "recovery_view", {"code": current_code(device.key)}
            )

        self.assertEqual(response.status_code, 404)



@override_settings(ENABLE_TWO_FACTOR=False)
class DisabledTOTPViewSetTestCase(TestAbstractViewSet):
    """With ``ENABLE_TWO_FACTOR`` off there is no enrolment.

    Pinned rather than left to the default, which is what it happens to be:
    a settings module that turns two-factor on -- as a deployment's will --
    would otherwise quietly stop these from testing anything.

    Unauthenticated because the gate answers before authentication does: a
    deployment without two-factor says the same thing to everyone.
    """

    def test_every_route_is_absent(self):
        """Enumerated rather than spot-checked: a route added later without
        the gate would still be reachable on a deployment that never asked
        for two-factor."""
        for handler, method in (
            ("enroll_start", "post"),
            ("enroll_confirm", "post"),
            ("disable", "post"),
            ("verify", "post"),
            ("recovery_generate", "post"),
            ("totp_status", "get"),
        ):
            with self.subTest(handler=handler):
                view = TOTPViewSet.as_view({method: handler})

                request = getattr(self.factory, method)("/")

                self.assertEqual(view(request).status_code, 404)

    def test_nothing_is_enrolled(self):
        """The refusal is not a 404 rendered after the work was already done."""
        view = TOTPViewSet.as_view({"post": "enroll_start"})

        self.assertEqual(view(self.factory.post("/")).status_code, 404)
        self.assertFalse(TOTPDevice.objects.exists())
