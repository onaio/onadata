# -*- coding: utf-8 -*-
"""
FHRegistrationView class module.
"""

from django.contrib.auth.views import PasswordChangeView, PasswordResetConfirmView

from registration.backends.default.views import RegistrationView

from onadata.libs.stepup.pages import refuse_page_action
from onadata.libs.stepup.policy import GATE_CHANGE_PASSWORD
from onadata.libs.utils.user_auth import invalidate_and_regen_tokens


class FHRegistrationView(RegistrationView):
    """A custom RegistrationView."""

    def register(self, form):
        new_user = super().register(form)
        form.save_user_profile(new_user)

        return new_user


class TokenRotatingPasswordResetConfirmView(PasswordResetConfirmView):
    """PasswordResetConfirmView that rotates API/temp tokens on a successful reset.

    Django's stock view only changes the password. Since the API's own
    reset-confirm endpoint (which used to call ``invalidate_and_regen_tokens``)
    has been removed, this is now the only place a reset completes, so it must
    invalidate the user's existing DRF/temp tokens itself; otherwise they'd
    keep working after a password reset.
    """

    def form_valid(self, form):
        response = super().form_valid(form)
        invalidate_and_regen_tokens(user=self.user)

        return response


class StepUpPasswordChangeView(PasswordChangeView):
    """PasswordChangeView behind the same step-up gate as the API's
    ``change_password``.

    Checked once the old password is confirmed, so a mistyped one does not
    spend the grant.
    """

    def form_valid(self, form):
        refusal = refuse_page_action(self.request, GATE_CHANGE_PASSWORD)
        if refusal is not None:
            return refusal

        return super().form_valid(form)
