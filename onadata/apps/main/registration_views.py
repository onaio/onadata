# -*- coding: utf-8 -*-
"""
FHRegistrationView class module.
"""

from django.contrib.auth.views import PasswordResetConfirmView

from registration.backends.default.views import RegistrationView

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
