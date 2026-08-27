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

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

import qrcode
from django_otp import devices_for_user
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from two_factor.utils import default_device

from onadata.apps.api.models.hashed_recovery_device import (
    RECOVERY_CODE_COUNT,
    HashedRecoveryCode,
    HashedRecoveryDevice,
    generate_recovery_code,
    hash_recovery_code,
)
from onadata.libs.authentication import (
    SSOHeaderAuthentication,
    add_login_attempt,
    assert_not_locked_out,
    get_client_ip,
)
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


def _known_audiences() -> frozenset:
    """The operations a grant may be minted for.

    Read per call rather than at import so a deployment's override -- and a
    test's -- takes effect.
    """
    return frozenset(getattr(settings, "TWO_FACTOR_STEP_UP_AUDIENCES", ()))


def _totp_device(user, confirmed=True, lock=False):
    """The user's authenticator, or None.

    Newest first, so the answer cannot depend on the order Postgres returns
    rows in should a second confirmed device ever survive.

    ``lock`` holds the row until the transaction ends, for callers that go on
    to spend the code or change the device.
    """
    devices = TOTPDevice.objects.select_for_update() if lock else TOTPDevice.objects
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
        HashedRecoveryDevice.objects.select_for_update()
        if lock
        else HashedRecoveryDevice.objects
    )
    return devices.filter(user=user, name=RECOVERY_DEVICE_NAME).first()


def _has_second_factor(user) -> bool:
    """Whether the login view would challenge this user for a second factor.

    Through ``default_device``, not a TOTPDevice lookup: two_factor challenges
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
    device hashes and case-folds the code itself, so the wizard's backup step
    and this path compare the same way.
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
    other -- ``TOTPDevice.verify_token`` counts a non-numeric code as a failed
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


def _regenerate_recovery_codes(user) -> list:
    """Replace the recovery set and return the new plaintext codes once.

    The codes are returned here and never again: only their keyed hashes are
    stored, so this is the one moment they exist in plaintext. Replace rather
    than append -- codes are single-use, so keeping spent ones would make the
    remaining count a lie.
    """
    with transaction.atomic():
        # Serialise on the user row: locking the recovery device would not
        # cover two callers who both find none yet and each create one, whom
        # delete-then-create under READ COMMITTED leaves with two live sets.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        HashedRecoveryDevice.objects.filter(
            user=user, name=RECOVERY_DEVICE_NAME
        ).delete()
        device = HashedRecoveryDevice.objects.create(
            user=user, name=RECOVERY_DEVICE_NAME, confirmed=True
        )
        codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        HashedRecoveryCode.objects.bulk_create(
            HashedRecoveryCode(device=device, code_hash=hash_recovery_code(code))
            for code in codes
        )
        return codes


def _enrollment_payload(device) -> dict:
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

    # SessionAuthentication so a user signed in through the login wizard (which
    # issues a Django session, not the SSO cookie) can manage their own factor;
    # it also re-applies CSRF for that cookie-borne path, which the others,
    # being header/JWT credentials, do not need.
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
        """Refuse every action unless the deployment enabled two-factor.

        Here rather than per action so a route added later cannot forget it,
        and ahead of authentication so the answer does not vary by caller.
        """
        if not getattr(settings, "ENABLE_TWO_FACTOR", False):
            raise NotFound("Two-factor authentication is not enabled.")
        super().initial(request, *args, **kwargs)

    def _locked_out_response(self, request):
        """A locked-out Response if failed codes have spent the login
        allowance, else None.

        Bounds every code-checking route by onadata's ``LOCKOUT_TIME``, so a
        caller spamming wrong codes -- with a stolen token, this endpoint's own
        weakness -- meets a defined lockout rather than django-otp's per-device
        backoff, which is uncapped and effectively permanent. Keyed on the same
        username as the login form, so the two share one allowance.
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
        try:
            add_login_attempt(get_client_ip(request), request.user.username)
        except AuthenticationFailed:
            # This attempt is the one that crossed the threshold. Swallow the
            # lockout here so this response stays the standard invalid-code
            # message; the next request re-checks the lockout and answers
            # ``locked_out``.
            return

    def _require_code(self, request, audience: str):
        """Reject unless the request carries a current second factor.

        Applied to every operation that weakens or replaces it -- otherwise a
        stolen session could switch 2FA off. A grant from a recent ``verify``
        counts, but only one earned for this same ``audience``.
        """
        locked = self._locked_out_response(request)
        if locked is not None:
            return locked
        if _spend_grant(
            request.user, audience, str(request.data.get("grant") or "").strip()
        ):
            return None
        if _verify_code(request.user, str(request.data.get("code") or "").strip()):
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
        if not getattr(settings, "TWO_FACTOR_ENROLMENT_REQUIRES_PASSWORD", False):
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
        """``None`` for a login session, or a Response refusing a bearer token.

        Enrolment is the one pair of routes ``_require_code`` cannot protect:
        an account with no second factor has no code to demand. A leaked API
        key could otherwise enrol its own authenticator and lock the owner out
        of the login they would need in order to revoke that key.
        """
        if isinstance(request.successful_authenticator, TokenAuthentication):
            return Response(
                {
                    "error": "Sign in to set up an authenticator. An API key "
                    "cannot be used to change how you sign in."
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
                # A list, not a single "authenticator": additional factor
                # kinds (a security key, say) append here instead of
                # reshaping the payload under every consumer.
                "methods": (
                    []
                    if device is None
                    else [
                        {
                            "kind": (
                                "totp" if isinstance(device, TOTPDevice) else "unknown"
                            ),
                            "label": device.name,
                            "createdAt": (
                                device.created_at.isoformat()
                                if getattr(device, "created_at", None)
                                else None
                            ),
                        }
                    ]
                ),
                "recoveryCodes": {
                    "generated": recovery is not None,
                    "remaining": 0 if recovery is None else recovery.codes.count(),
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
            TOTPDevice.objects.filter(
                user=request.user, name=TOTP_DEVICE_NAME, confirmed=False
            ).delete()
            device = TOTPDevice.objects.create(
                user=request.user, name=TOTP_DEVICE_NAME, confirmed=False
            )
        return Response(_enrollment_payload(device), status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="enroll/confirm")
    def enroll_confirm(self, request):
        """Activate the pending device once the user echoes a code from it."""
        refusal = self._require_login_session(request)
        if refusal is not None:
            return refusal
        code = str(request.data.get("code") or "").strip()
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
        """Report how many recovery codes remain, never the codes themselves.

        The codes are stored only as keyed hashes, so they cannot be re-read:
        they are shown once, when generated. A caller that has lost them
        generates a fresh set. No code or grant is required because nothing
        secret is disclosed.
        """
        recovery = _recovery_device(request.user)
        if recovery is None:
            return Response(
                {"error": "No recovery codes have been generated."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "remaining": recovery.codes.count(),
                "detail": "Recovery codes are shown only when generated. "
                "Generate a new set if you have lost them.",
            }
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
        code = str(request.data.get("code") or "").strip()
        audience = str(request.data.get("audience", "")).strip()
        if audience not in _known_audiences():
            # Static message: audience is unbounded caller input.
            return Response(
                {"error": "Unknown step-up audience."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # `... or ""` rather than a default, so an explicit JSON null becomes
        # "" (any-factor) instead of the string "None".
        method = str(request.data.get("method") or "").strip()
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
