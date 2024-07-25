# -*- coding: utf-8 -*-
"""
Module containing custom validator classes for the User Model
"""
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class PreviousPasswordValidator:
    """Class validates password was not previously recorded."""

    def __init__(self, history_limt=5):
        self.message = _("You cannot use a previously used password.")
        self.history_limit = history_limt

    def validate(self, password, user=None):
        """Checks password was not used previously."""
        if user and user.pk and user.is_active:
            if user.check_password(password):
                raise ValidationError(self.message)

            pw_history = user.password_history.all()[: self.history_limit]
            for pw_hist in pw_history:
                if check_password(password, pw_hist.hashed_password):
                    raise ValidationError(self.message)

    def get_help_text(self):
        """Returns the help text."""
        return _("Your password cannot be the same as your previous password.")
