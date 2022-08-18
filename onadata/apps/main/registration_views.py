# -*- coding=utf-8 -*-
"""
FHRegistrationView class module.
"""
from registration.backends.default.views import RegistrationView


class FHRegistrationView(RegistrationView):
    """A custom RegistrationView."""

    def register(self, form):
        new_user = super().register(form)
        form.save_user_profile(new_user)

        return new_user
