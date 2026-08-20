"""Views overriding django-two-factor-auth's defaults."""

import importlib

from django import forms

from rest_framework.exceptions import AuthenticationFailed
from two_factor.forms import AuthenticationTokenForm
from two_factor.views import LoginView

from onadata.apps.main.forms import (
    LoginLockoutAuthenticationForm,
    RecoveryCodeForm,
    lockout_validation_error,
)


def _default_remember_to_off(form):
    """Make "don't ask again on this device" a choice rather than a default.

    The library ships the field with ``initial=True``.
    """
    remember = form.fields.get("remember")
    if remember is not None:
        remember.initial = False


def _enforce_lockout(form, request):
    """Count token failures against onadata's login lockout.

    Upstream covers the credentials step alone, leaving whoever holds the
    password an unbounded run at a six-digit code: django-otp's per-device
    backoff slows that but tells the account holder nothing.

    Keyed on the same username as the credentials step, so an attacker cannot
    spend one full allowance on passwords and another on codes.
    """
    inner_clean = form.clean

    def clean():
        # Avoid circular import, matching LoginLockoutAuthenticationForm.
        authentication = importlib.import_module("onadata.libs.authentication")
        ip_address = authentication.get_client_ip(request)
        username = authentication.get_lockout_username(form.user.get_username())

        try:
            authentication.assert_not_locked_out(ip_address, username)
        except AuthenticationFailed as exc:
            raise lockout_validation_error() from exc

        try:
            return inner_clean()
        except forms.ValidationError:
            # Re-raised so the user sees the library's wrong-token message,
            # until add_login_attempt raises at the threshold instead.
            try:
                authentication.add_login_attempt(ip_address, username)
            except AuthenticationFailed as exc:
                raise lockout_validation_error() from exc
            raise

    form.clean = clean


# The wizard's own hierarchy, not ours: two_factor's LoginView is already a
# SessionWizardView stack, so subclassing it to swap one form exceeds the
# ancestor limit no matter how thin the subclass is.
# pylint: disable=too-many-ancestors
class LockoutLoginView(LoginView):
    """Two-factor login wizard carrying onadata's failed-login lockout.

    On both steps, so it cannot be sidestepped by attacking the second factor
    instead of the first.
    """

    form_list = (
        (LoginView.AUTH_STEP, LoginLockoutAuthenticationForm),
        (LoginView.TOKEN_STEP, AuthenticationTokenForm),
        (LoginView.BACKUP_STEP, RecoveryCodeForm),
    )

    def get_form(self, step=None, **kwargs):
        """Adjust the token forms after the library has chosen them.

        Not done through ``form_list``: ``LoginView.get_form`` reassigns
        ``form_list[TOKEN_STEP]`` from the method plugin on every call, so a
        class named there is discarded before it is ever instantiated.
        """
        form = super().get_form(step=step, **kwargs)
        if (step or self.steps.current) in (self.TOKEN_STEP, self.BACKUP_STEP):
            _default_remember_to_off(form)
            _enforce_lockout(form, self.request)
        return form
