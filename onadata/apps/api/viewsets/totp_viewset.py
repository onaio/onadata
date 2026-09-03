"""
Manage a user's second factor: enrol, disable, verify, recovery codes.

Every endpoint acts on the authenticated caller; none accepts a username, so
none can be pointed at another user's second factor. Token auth is accepted
alongside the SSO cookie wherever a current code is demanded -- that demand is
what makes a stolen token insufficient. Enrolment has no incumbent code to
demand, so it takes the login session alone.
"""

import base64
import io
import secrets
from contextlib import suppress

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

import qrcode
from django_otp import devices_for_user
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from two_factor.utils import default_device

from onadata.apps.api.models.encrypted_recovery_device import (
    RECOVERY_CODE_COUNT,
    EncryptedRecoveryCode,
    EncryptedRecoveryDevice,
    generate_recovery_code,
)
from onadata.apps.api.models.encrypted_totp_device import EncryptedTOTPDevice
from onadata.libs.authentication import (
    SSOHeaderAuthentication,
    add_login_attempt,
    assert_not_locked_out,
    get_client_ip,
)
from onadata.libs.utils.field_encryption import encrypt
from onadata.libs.utils.log import Actions, audit_log
from onadata.libs.utils.two_factor import (
    clear_verification_failures,
    notify_owner,
    record_verification_failure,
)

#: Not free-form labels. two_factor matches "default" to decide whether to
#: ask for a second factor at all; "backup" is this module's own, and only has
#: to agree between the code that writes the recovery set and the code that
#: reads it.
TOTP_DEVICE_NAME = "default"
RECOVERY_DEVICE_NAME = "backup"

STEP_UP_GRANT_TTL = 5 * 60


def _grant_key(user, audience: str, grant: str) -> str:
    return f"totp-step-up:{user.pk}:{audience}:{grant}"


def _issue_grant(user, audience: str) -> str:
    """Proof that this user showed a second factor a moment ago.

    django-otp records the counter a code was used at, so a caller that
    verifies first and acts second has nothing to resend.
    """
    grant = secrets.token_urlsafe(32)
    cache.set(_grant_key(user, audience, grant), True, STEP_UP_GRANT_TTL)
    return grant


def _spend_grant(user, audience: str, grant: str) -> bool:
    """Redeem a grant, once. False if minted for a different operation.

    The delete is the check: ``cache.delete`` reports whether it removed
    anything, so two requests racing on one grant cannot both be told yes.
    """
    if not grant:
        return False
    return bool(cache.delete(_grant_key(user, audience, grant)))


def _known_audiences() -> frozenset[str]:
    """The operations a grant may be minted for.

    Read per call rather than at import so a deployment's override -- and a
    test's -- takes effect.
    """
    return frozenset(getattr(settings, "TWO_FACTOR_STEP_UP_AUDIENCES", ()))


def _str_field(request, name: str) -> str:
    """A stripped string field, treating an absent value and JSON null alike as
    the empty string -- so an explicit null does not arrive as the text "None".
    """
    return str(request.data.get(name) or "").strip()


def _method_entries(device) -> list[dict]:
    """The account's second-factor methods, as the status payload lists them.

    A list, not a single "authenticator": another factor kind (a security key,
    say) appends here instead of reshaping the payload under every consumer.
    """
    if device is None:
        return []
    created_at = getattr(device, "created_at", None)
    return [
        {
            "kind": "totp" if isinstance(device, EncryptedTOTPDevice) else "unknown",
            "label": device.name,
            "createdAt": created_at.isoformat() if created_at else None,
        }
    ]


def _totp_device(user, confirmed=True, lock=False):
    """The user's authenticator, or None.

    Newest first, so the answer cannot depend on the order Postgres returns
    rows in should a second confirmed device ever survive.

    ``lock`` holds the row until the transaction ends, for callers that go on
    to spend the code or change the device.
    """
    devices = (
        EncryptedTOTPDevice.objects.select_for_update()
        if lock
        else EncryptedTOTPDevice.objects
    )
    return (
        devices.filter(user=user, name=TOTP_DEVICE_NAME, confirmed=confirmed)
        .order_by("-id")
        .first()
    )


def _recovery_device(user, lock=False):
    """The user's recovery-code set, or None.

    ``lock`` as in ``_totp_device``.
    """
    devices = (
        EncryptedRecoveryDevice.objects.select_for_update()
        if lock
        else EncryptedRecoveryDevice.objects
    )
    return devices.filter(user=user, name=RECOVERY_DEVICE_NAME).first()


def _has_second_factor(user) -> bool:
    """Whether the login view would challenge this user for a second factor.

    Through ``default_device``, not an EncryptedTOTPDevice lookup: two_factor challenges
    on any confirmed device named ``"default"`` whatever its class.
    ``_verify_code`` understands only TOTP and recovery codes -- teach it any
    new device type in the same change.
    """
    return default_device(user) is not None


def _verify_totp(user, code: str) -> bool:
    """Check ``code`` against the authenticator, spending it once.

    Locked because ``verify_token`` reads ``last_t`` and saves it in separate
    statements. Workers are separate processes with their own connections, so
    ``--threads 1`` does not serialise them.
    """
    with transaction.atomic():
        device = _totp_device(user, lock=True)
        return device is not None and device.verify_token(code)


def _verify_recovery(user, code: str) -> bool:
    """Check ``code`` against the recovery set, spending it once.

    Locked for the same reason as ``_verify_totp``, and a worse outcome here:
    unlocked, one single-use code is honoured once per racing caller. The
    device decrypts and case-folds the codes itself, so the wizard's backup
    step and this path compare the same way.
    """
    with transaction.atomic():
        recovery = _recovery_device(user, lock=True)
        return recovery is not None and recovery.verify_token(code)


VERIFY_METHODS = {
    "totp": _verify_totp,
    "recovery": _verify_recovery,
}


def _method_for_code(code: str) -> str:
    """The one factor a code could belong to, by shape.

    A TOTP code is six digits; a recovery code is base32 and never is. Routing
    on that keeps a recovery attempt off the TOTP device's throttle (and a TOTP
    attempt off the recovery set), so one factor's failures never lock the
    other -- ``EncryptedTOTPDevice.verify_token`` counts a non-numeric code as a failed
    attempt against the authenticator the user never touched.
    """
    return "totp" if code.isdigit() and len(code) == 6 else "recovery"


def _verify_code(user, code: str, method: str = "") -> bool:
    """Whether ``code`` proves the named factor -- or, unnamed, the one it fits.

    Recovery codes count: someone who lost their authenticator still has to be
    able to turn it off. A caller that names a ``method`` is checked against
    that factor alone; unnamed, the code is routed to the single factor its
    shape allows, never tried against both.
    """
    if not code:
        return False
    # Unknown method is "not verified", never a KeyError, for callers that
    # forward one; verify() rejects it with a 400 before reaching here.
    check = VERIFY_METHODS.get(method or _method_for_code(code))
    return check is not None and check(user, code)


@sensitive_variables()
def _regenerate_recovery_codes(user) -> list[str]:
    """Replace the recovery set and return the new codes.

    Replace rather than append -- codes are single-use, so keeping spent ones
    would make the remaining count a lie. The codes are stored encrypted, so
    the owner can view the unspent ones again through ``recovery_view``.
    """
    with transaction.atomic():
        # Serialise on the user row: locking the recovery device would not
        # cover two callers who both find none yet and each create one, whom
        # delete-then-create under READ COMMITTED leaves with two live sets.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        EncryptedRecoveryDevice.objects.filter(
            user=user, name=RECOVERY_DEVICE_NAME
        ).delete()
        device = EncryptedRecoveryDevice.objects.create(
            user=user, name=RECOVERY_DEVICE_NAME, confirmed=True
        )
        codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        EncryptedRecoveryCode.objects.bulk_create(
            EncryptedRecoveryCode(device=device, encrypted_code=encrypt(code))
            for code in codes
        )
        return codes


@sensitive_variables()
def _enrollment_payload(device) -> dict[str, str]:
    """One secret in three renderings: QR, URI, and base32 to type by hand.

    django-otp stores the key as hex, which no authenticator app accepts.
    """
    image = qrcode.make(device.config_url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return {
        "qrDataUrl": f"data:image/png;base64,{encoded}",
        "otpauthUri": device.config_url,
        "secretBase32": base64.b32encode(bytes.fromhex(device.key))
        .decode()
        .rstrip("="),
    }


class TOTPViewSet(ViewSet):
    """Enroll, disable and verify the authenticator for the calling user."""

    # Three credentials, two of them cookie-borne. SessionAuthentication
    # enforces CSRF for the Django login session it authenticates. The SSO
    # credential can arrive the same ambient way -- authenticate_sso reads the
    # HTTP_SSO header or the SSO cookie -- and SSOHeaderAuthentication runs
    # first, so SessionAuthentication never sees that request; initial() guards
    # the cookie-borne SSO path instead. A token or a header-borne SSO is not
    # ambient, so a cross-site page cannot send it and it needs no CSRF token.
    authentication_classes = (
        SSOHeaderAuthentication,
        SessionAuthentication,
        TokenAuthentication,
    )
    permission_classes = (IsAuthenticated,)
    renderer_classes = (JSONRenderer,)

    @method_decorator(sensitive_post_parameters())
    def dispatch(self, request, *args, **kwargs):
        """Keep submitted secrets out of error reports.

        On ``dispatch`` rather than the action: the decorator marks the
        underlying ``HttpRequest``, which is what the exception reporter
        reads. Marking DRF's ``Request`` leaves the body in the traceback.
        """
        return super().dispatch(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        """Forbid storing any answer from here.

        Viewset-wide rather than per action, so a route added later cannot
        forget it -- every route here carries a secret.
        """
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def initial(self, request, *args, **kwargs):
        """Refuse every action unless two-factor is enabled, and demand a CSRF
        token when the credential is the ambient SSO cookie.

        The enable gate is here rather than per action so a route added later
        cannot forget it, and ahead of authentication so the answer does not
        vary by caller. The CSRF guard runs after, once the credential is known.
        """
        if not getattr(settings, "ENABLE_TWO_FACTOR", False):
            raise NotFound("Two-factor authentication is not enabled.")
        super().initial(request, *args, **kwargs)
        self._enforce_cookie_sso_csrf(request)

    def _enforce_cookie_sso_csrf(self, request):
        """Demand a CSRF token when the SSO credential rode in on the cookie.

        ``authenticate_sso`` accepts the token from the ``HTTP_SSO`` header or
        the ``SSO`` cookie. A cross-site page cannot set the header but does
        send the cookie, so the cookie -- and only it -- needs a CSRF token.
        SessionAuthentication guards the Django session cookie the same way but
        never runs here, because SSOHeaderAuthentication authenticates first.
        """
        if not isinstance(request.successful_authenticator, SSOHeaderAuthentication):
            return
        if request.META.get("HTTP_SSO"):
            return
        SessionAuthentication().enforce_csrf(request)

    def _locked_out_response(self, request):
        """A locked-out Response if failed codes have spent the login
        allowance, else None.

        Caps the shared login-form allowance across the code-checking routes,
        so a run of wrong codes on one ``(IP, username)`` meets a defined
        lockout. This is keyed on the client IP -- which ``get_client_ip``
        takes from a proxy-supplied header -- so it is a secondary layer that
        does not bound an attacker rotating source addresses (deployments must
        have the edge strip a client-set ``X-Real-Ip``). The IP-independent
        backstop is django-otp's per-device exponential throttle, which holds
        regardless of address and is what keeps 6-digit TOTP and 112-bit
        recovery codes infeasible to brute-force. Keyed on the same username as
        the login form, so the two share one allowance.
        """
        try:
            assert_not_locked_out(get_client_ip(request), request.user.username)
        except AuthenticationFailed as lockout:
            return Response(
                {"error": str(lockout.detail), "reason": "locked_out"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def _spend_code_attempt(self, request):
        """Count a failed code against the bounded login allowance.

        A threshold hit raises, which the next request sees as ``locked_out``;
        the current response stays the standard invalid-code message.
        """
        # The threshold-crossing lockout is swallowed here so this response
        # stays the standard invalid-code message; the next request re-checks
        # the lockout and answers ``locked_out``.
        with suppress(AuthenticationFailed):
            add_login_attempt(get_client_ip(request), request.user.username)

    def _require_code(self, request, audience: str):
        """Reject unless the request carries a current second factor.

        Applied to every operation that weakens or replaces it -- otherwise a
        stolen session could switch 2FA off. A grant from a recent ``verify``
        counts, but only one earned for this same ``audience``.
        """
        locked = self._locked_out_response(request)
        if locked is not None:
            return locked
        if _spend_grant(request.user, audience, _str_field(request, "grant")):
            return None
        if _verify_code(request.user, _str_field(request, "code")):
            return None
        record_verification_failure(request, request.user, {"audience": audience})
        self._spend_code_attempt(request)
        return Response(
            {
                "error": "That code is not valid. Enter a current code from your "
                "authenticator app, or one of your recovery codes."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    @sensitive_variables()
    def _require_password(self, request):
        """Refuse unless the account's own password is supplied.

        The only proof available at first enrolment: with no factor yet,
        ``_require_code`` has nothing to demand.

        An account with no password is refused rather than let through, or
        having no password would itself be the way past it. Its own reason, so
        a caller can say what is wrong instead of prompting for one that
        cannot exist. The stored value is tested directly: Django reports the
        empty string ``objects.create`` leaves behind as *usable*.
        """
        if not getattr(settings, "TWO_FACTOR_ENROLMENT_REQUIRES_PASSWORD", True):
            return None
        user = request.user
        if not user.password or not user.has_usable_password():
            return Response(
                {
                    "error": "This account has no password, so it cannot "
                    "confirm an enrolment. Set one first.",
                    "reason": "no_password_set",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        # Guesses here spend the login form's allowance, or this endpoint
        # would be a way around the lockout instead of a second lock on the
        # same password.
        password = str(request.data.get("password") or "")
        ip_address, username = get_client_ip(request), user.username
        try:
            assert_not_locked_out(ip_address, username)
            if user.check_password(password):
                return None
            # An absent password is an incomplete request, not a wrong guess;
            # the login form draws the same line, so a client probing for the
            # required ``reason`` does not burn the shared allowance.
            if password:
                add_login_attempt(ip_address, username)
        except AuthenticationFailed as lockout:
            return Response(
                {"error": str(lockout.detail), "reason": "locked_out"},
                status=status.HTTP_403_FORBIDDEN,
            )
        # ``reason`` so a client can tell this refusal from the step-up one
        # above it: both are 403, but one is answered by typing a password and
        # the other by a code, and offering the wrong prompt strands the user.
        return Response(
            {
                "error": "Enter your account password to set up an authenticator.",
                "reason": "password_required",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    def _require_login_session(self, request):
        """``None`` for the SSO sign-in credential, else a Response refusing it.

        Enrolment is the one pair of routes ``_require_code`` cannot protect:
        an account with no second factor has no code to demand. An allow-list,
        not a deny-list -- only the SSO credential the signed-in app carries is
        accepted, so an API key (which could otherwise enrol its own
        authenticator and lock the owner out) and any credential added later
        are refused by default. The SSO credential is replayable, but a first
        enrolment must still pass ``_require_password`` below: the credential
        type is not the security boundary, the account password is.
        """
        if not isinstance(request.successful_authenticator, SSOHeaderAuthentication):
            return Response(
                {
                    "error": "Sign in to set up an authenticator. This "
                    "credential cannot be used to change how you sign in."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    @action(detail=False, methods=["get"], url_path="status")
    def totp_status(self, request):
        """The account's second factor and recovery-code state."""
        device = default_device(request.user)
        recovery = _recovery_device(request.user)
        return Response(
            {
                "methods": _method_entries(device),
                "recoveryCodes": {
                    "generated": recovery is not None,
                    "remaining": 0 if recovery is None else recovery.remaining,
                },
            }
        )

    @action(detail=False, methods=["post"], url_path="enroll/start")
    def enroll_start(self, request):
        """Mint an unconfirmed device and hand back its provisioning URI.

        Unconfirmed until the user proves they can read a code from it.
        Re-starting replaces the previous attempt rather than accumulating
        dead devices.
        """
        refusal = self._require_login_session(request)
        if refusal is not None:
            return refusal
        if _has_second_factor(request.user):
            # Swapping in a new authenticator weakens the old one just as
            # removing it does, so it needs the same proof.
            refusal = self._require_code(request, "enroll-start")
        else:
            refusal = self._require_password(request)
        if refusal is not None:
            return refusal
        with transaction.atomic():
            # Serialise on the user row, as _regenerate_recovery_codes does:
            # two racing starts would otherwise each delete-then-create under
            # READ COMMITTED and leave two pending devices, so a later confirm
            # verifies against one while the caller was shown the other.
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            EncryptedTOTPDevice.objects.filter(
                user=request.user, name=TOTP_DEVICE_NAME, confirmed=False
            ).delete()
            device = EncryptedTOTPDevice.objects.create(
                user=request.user, name=TOTP_DEVICE_NAME, confirmed=False
            )
        return Response(_enrollment_payload(device), status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="enroll/confirm")
    def enroll_confirm(self, request):
        """Activate the pending device once the user echoes a code from it."""
        refusal = self._require_login_session(request)
        if refusal is not None:
            return refusal
        code = _str_field(request, "code")
        # One transaction, with the pending row locked before the code is
        # spent: a device that confirmed but whose recovery codes did not is
        # one lost phone from a locked account, and racing callers would each
        # be handed a set of which only the last survives.
        with transaction.atomic():
            device = _totp_device(request.user, confirmed=False, lock=True)
            if device is None:
                return Response(
                    {
                        "error": "Start setting up an authenticator before "
                        "confirming it."
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if not device.verify_token(code):
                # Audited for a complete trail, but not through
                # record_verification_failure: a mistyped confirmation is the
                # enrolling owner fumbling their own new code, so it should not
                # feed the owner-alert counter meant for attempts against a
                # live factor.
                audit_log(
                    Actions.TWO_FACTOR_VERIFICATION_FAILED,
                    request.user,
                    request.user,
                    _("Two-factor verification failed."),
                    {"step": "enroll-confirm"},
                    request,
                )
                return Response(
                    {
                        "error": "That code is not valid. Check the time on your "
                        "device and try the current code."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            # default_device() answers with the first confirmed device named
            # "default", not the newest, so an incumbent left behind stays the
            # device the login wizard challenges on. It is removed by name,
            # the classes this module manages, below.
            for superseded in devices_for_user(request.user, confirmed=True):
                if (
                    superseded.name == TOTP_DEVICE_NAME
                    and superseded.persistent_id != device.persistent_id
                ):
                    superseded.delete()
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            codes = _regenerate_recovery_codes(request.user)
        # After the transaction: neither the log entry nor the email can be
        # rolled back, so neither may describe an enrolment that was.
        audit_log(
            Actions.TWO_FACTOR_ENROLLED,
            request.user,
            request.user,
            _("Two-factor authentication enabled."),
            {},
            request,
        )
        notify_owner(request.user, "enabled")
        return Response({"enrolled": True, "codes": codes})

    @action(detail=False, methods=["post"], url_path="disable")
    def disable(self, request):
        """Remove every device the login view could challenge on."""
        if not _has_second_factor(request.user):
            return Response({"enrolled": False})
        refusal = self._require_code(request, "disable")
        if refusal is not None:
            return refusal
        with transaction.atomic():
            # _has_second_factor asks default_device(), which answers on any
            # device class named "default". Deleting only the classes this
            # module creates would report two-factor off while leaving one
            # standing that nothing here can verify, so never removable.
            for device in devices_for_user(request.user, confirmed=None):
                device.delete()
        audit_log(
            Actions.TWO_FACTOR_DISABLED,
            request.user,
            request.user,
            _("Two-factor authentication disabled."),
            {},
            request,
        )
        notify_owner(request.user, "disabled")
        return Response({"enrolled": False})

    @action(detail=False, methods=["post"], url_path="recovery/generate")
    def recovery_generate(self, request):
        """Replace the recovery set and return the new codes once."""
        if not _has_second_factor(request.user):
            return Response(
                {"error": "Set up an authenticator before generating recovery codes."},
                status=status.HTTP_409_CONFLICT,
            )
        refusal = self._require_code(request, "recovery-generate")
        if refusal is not None:
            return refusal
        codes = _regenerate_recovery_codes(request.user)
        audit_log(
            Actions.TWO_FACTOR_RECOVERY_CODES_GENERATED,
            request.user,
            request.user,
            _("Two-factor recovery codes replaced."),
            {},
            request,
        )
        notify_owner(request.user, "recovery_generated")
        # The only time these are readable.
        return Response({"codes": codes}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="recovery")
    def recovery_view(self, request):
        """Return the account's unspent recovery codes.

        The codes are stored encrypted, so the owner can read them again --
        behind the same step-up every code-weakening route takes (a current
        code or a ``recovery-view`` grant), bounded by the login lockout, with
        ``no-store`` from ``finalize_response`` and an audit entry on each view.
        Disclosing them without a step-up would make a stolen session enough to
        read a durable second factor.
        """
        recovery = _recovery_device(request.user)
        if recovery is None:
            return Response(
                {"error": "No recovery codes have been generated."},
                status=status.HTTP_404_NOT_FOUND,
            )
        refusal = self._require_code(request, "recovery-view")
        if refusal is not None:
            return refusal
        audit_log(
            Actions.TWO_FACTOR_RECOVERY_CODES_VIEWED,
            request.user,
            request.user,
            _("Two-factor recovery codes viewed."),
            {},
            request,
        )
        # Disclosing the whole durable set is as owner-visible a change as
        # regenerating it, so it is notified the same way: one intercepted code
        # otherwise buys the recovery set with no signal to the owner.
        notify_owner(request.user, "recovery_viewed")
        return Response(
            {"codes": recovery.unspent_codes(), "remaining": recovery.remaining}
        )

    @action(detail=False, methods=["post"], url_path="verify")
    def verify(self, request):
        """Check a code without changing anything -- the step-up challenge.

        The caller names what it intends to do with the proof, and the grant is
        spendable on that alone. The name has to be one this deployment
        recognises: minting a grant for an unknown operation would spend the
        user's code on something they can never redeem.
        """
        locked = self._locked_out_response(request)
        if locked is not None:
            return locked
        code = _str_field(request, "code")
        audience = _str_field(request, "audience")
        if audience not in _known_audiences():
            # Static message: audience is unbounded caller input.
            return Response(
                {"error": "Unknown step-up audience."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # An empty method means any-factor; _str_field maps an explicit JSON
        # null to "" so it does not arrive as the string "None".
        method = _str_field(request, "method")
        if method and method not in VERIFY_METHODS:
            return Response(
                {"error": "Unknown verification method."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not _verify_code(request.user, code, method):
            record_verification_failure(
                request, request.user, {"audience": audience, "method": method}
            )
            self._spend_code_attempt(request)
            return Response(
                {"error": "That code is not valid."},
                status=status.HTTP_403_FORBIDDEN,
            )
        clear_verification_failures(request.user)
        return Response(
            {"verified": True, "grant": _issue_grant(request.user, audience)}
        )
