# -*- coding: utf-8 -*-
"""AppConfig for onadata.libs."""

from django.apps import AppConfig


class LibsConfig(AppConfig):
    """Registers the checks that live under ``onadata.libs``."""

    name = "onadata.libs"
    verbose_name = "Ona libs"

    def ready(self):
        """Register the step-up startup checks."""
        # pylint: disable=import-outside-toplevel
        from django.core.checks import register

        from onadata.libs.stepup.checks import (
            check_federated_step_up_binds_by_email,
            check_federated_step_up_gates_email,
            check_oauth_approval_can_step_up,
            check_removed_enrolment_password_setting,
            check_step_up_actions_are_known,
            check_step_up_has_two_factor_enabled,
            check_step_up_is_well_formed,
            check_step_up_mode_is_known,
            check_step_up_no_factor_policy_is_known,
            check_step_up_not_silently_bypassable,
        )

        register(check_step_up_is_well_formed)
        register(check_step_up_actions_are_known)
        register(check_step_up_no_factor_policy_is_known)
        register(check_step_up_not_silently_bypassable)
        register(check_step_up_mode_is_known)
        register(check_step_up_has_two_factor_enabled)
        register(check_removed_enrolment_password_setting)
        register(check_federated_step_up_gates_email)
        register(check_federated_step_up_binds_by_email)
        register(check_oauth_approval_can_step_up)
