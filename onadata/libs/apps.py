# -*- coding: utf-8 -*-
"""AppConfig for onadata.libs."""

from django.apps import AppConfig


class LibsConfig(AppConfig):
    """Registers the checks that live under ``onadata.libs``."""

    name = "onadata.libs"
    verbose_name = "Ona libs"

    def ready(self):
        # pylint: disable=import-outside-toplevel
        from django.core.checks import register

        from onadata.libs.stepup.checks import (
            check_step_up_actions_are_mintable,
            check_step_up_mode_is_known,
            check_step_up_not_silently_bypassable,
        )

        # ona-oidc registers its own MAX_AGE check (oidc.W001) from its
        # AppConfig, so there is nothing to wire up for it here.
        register(check_step_up_not_silently_bypassable)
        register(check_step_up_actions_are_mintable)
        register(check_step_up_mode_is_known)
