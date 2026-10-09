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
            check_step_up_has_two_factor_enabled,
            check_step_up_mode_is_known,
            check_step_up_not_silently_bypassable,
        )

        # ona-oidc registers its own checks (oidc.W001, oidc.W002) from its
        # AppConfig, so there is nothing to wire up for them here.
        register(check_step_up_not_silently_bypassable)
        register(check_step_up_actions_are_mintable)
        register(check_step_up_mode_is_known)
        register(check_step_up_has_two_factor_enabled)
