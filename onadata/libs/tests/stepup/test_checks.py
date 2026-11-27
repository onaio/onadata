"""Tests for module onadata.libs.stepup.checks"""

from django.test import SimpleTestCase, override_settings

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

ALL_CHECKS = (
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


class TestTwoFactorEnabled(SimpleTestCase):
    """Local step-up needs the two-factor endpoints that mint its grants."""

    @override_settings(
        ENABLE_TWO_FACTOR=False,
        STEP_UP={"ACTIONS": {"require-auth-toggle"}, "MODE": "local"},
    )
    def test_gating_with_two_factor_off_is_reported(self):
        warnings = check_step_up_has_two_factor_enabled()

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].id, "stepup.W004")

    @override_settings(
        ENABLE_TWO_FACTOR=True,
        STEP_UP={"ACTIONS": {"require-auth-toggle"}, "MODE": "local"},
    )
    def test_two_factor_on_is_silent(self):
        self.assertEqual(check_step_up_has_two_factor_enabled(), [])

    @override_settings(
        ENABLE_TWO_FACTOR=False,
        STEP_UP={"ACTIONS": {"require-auth-toggle"}, "MODE": "federated"},
    )
    def test_federated_mode_is_not_reported(self):
        """Federated grants come from the provider, not /api/v1/totp."""
        self.assertEqual(check_step_up_has_two_factor_enabled(), [])

    @override_settings(
        ENABLE_TWO_FACTOR=False,
        STEP_UP={"ACTIONS": set(), "MODE": "local"},
    )
    def test_gating_nothing_is_silent(self):
        self.assertEqual(check_step_up_has_two_factor_enabled(), [])


class TestModeIsKnown(SimpleTestCase):
    """MODE must name a topology, not a typo that silently picks federated."""

    @override_settings(STEP_UP={"MODE": "fedarated"})
    def test_an_unknown_mode_is_reported(self):
        warnings = check_step_up_mode_is_known()

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].id, "stepup.W003")
        self.assertIn("fedarated", warnings[0].msg)

    @override_settings(STEP_UP={"MODE": "local"})
    def test_local_is_silent(self):
        self.assertEqual(check_step_up_mode_is_known(), [])

    @override_settings(STEP_UP={"MODE": "federated"})
    def test_federated_is_silent(self):
        self.assertEqual(check_step_up_mode_is_known(), [])

    @override_settings(STEP_UP={"ACTIONS": set()})
    def test_the_default_mode_is_silent(self):
        """No MODE set falls back to 'local', which must not warn."""
        self.assertEqual(check_step_up_mode_is_known(), [])


class TestNotSilentlyBypassable(SimpleTestCase):
    """skip_gate with gated actions lets users with no factor through. That
    is a valid rollout choice, but it must not be silent."""

    @override_settings(
        STEP_UP={
            "ACTIONS": {"require-auth-toggle"},
            "NO_FACTOR_POLICY": "skip_gate",
        }
    )
    def test_skip_gate_with_actions_is_reported(self):
        warnings = check_step_up_not_silently_bypassable()

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].id, "stepup.W001")
        self.assertIn("require-auth-toggle", warnings[0].msg)

    @override_settings(
        STEP_UP={
            "ACTIONS": {"require-auth-toggle"},
            "NO_FACTOR_POLICY": "deny_prompt_enrol",
        }
    )
    def test_deny_prompt_enrol_is_silent(self):
        self.assertEqual(check_step_up_not_silently_bypassable(), [])

    @override_settings(STEP_UP={"ACTIONS": set(), "NO_FACTOR_POLICY": "skip_gate"})
    def test_gating_nothing_is_silent(self):
        self.assertEqual(check_step_up_not_silently_bypassable(), [])

    @override_settings(
        STEP_UP={
            "ACTIONS": {"require-auth-toggle"},
            "MODE": "federated",
            "NO_FACTOR_POLICY": "skip_gate",
        }
    )
    def test_federated_mode_is_silent(self):
        """Federated mode always challenges, so skip_gate bypasses nothing."""
        self.assertEqual(check_step_up_not_silently_bypassable(), [])


class TestFederatedStepUpGatesEmail(SimpleTestCase):
    """Federated step-up matches the provider's token to the account's email,
    so an ungated email change is a way around every gate."""

    @override_settings(STEP_UP={"MODE": "federated", "ACTIONS": ["regenerate-api-key"]})
    def test_an_ungated_email_change_is_reported(self):
        warnings = check_federated_step_up_gates_email()

        self.assertEqual([w.id for w in warnings], ["stepup.W006"])

    @override_settings(
        STEP_UP={
            "MODE": "federated",
            "ACTIONS": ["regenerate-api-key", "change-email"],
        }
    )
    def test_a_gated_email_change_is_silent(self):
        self.assertEqual(check_federated_step_up_gates_email(), [])

    @override_settings(STEP_UP={"MODE": "local", "ACTIONS": ["regenerate-api-key"]})
    def test_local_mode_is_silent(self):
        self.assertEqual(check_federated_step_up_gates_email(), [])


def _servers(**step_up):
    return {"idp": {"STEP_UP": {"REDIRECT_URI": "https://app.test/cb", **step_up}}}


class TestFederatedStepUpBindsByEmail(SimpleTestCase):
    """Of the fields step-up can identify the user by, only the email is
    gated against change."""

    @override_settings(
        STEP_UP={"MODE": "federated", "ACTIONS": ["change-email"]},
        OPENID_CONNECT_AUTH_SERVERS=_servers(SUBJECT_FIELD="username"),
    )
    def test_a_username_binding_is_reported(self):
        warnings = check_federated_step_up_binds_by_email()

        self.assertEqual([w.id for w in warnings], ["stepup.W007"])

    @override_settings(
        STEP_UP={"MODE": "federated", "ACTIONS": ["change-email"]},
        OPENID_CONNECT_AUTH_SERVERS=_servers(),
    )
    def test_the_default_email_binding_is_silent(self):
        self.assertEqual(check_federated_step_up_binds_by_email(), [])

    @override_settings(
        STEP_UP={"MODE": "local", "ACTIONS": ["change-email"]},
        OPENID_CONNECT_AUTH_SERVERS=_servers(SUBJECT_FIELD="username"),
    )
    def test_local_mode_is_silent(self):
        self.assertEqual(check_federated_step_up_binds_by_email(), [])


class TestRemovedEnrolmentPasswordSetting(SimpleTestCase):
    """The removed opt-out does nothing. Enrolment always needs the password,
    so users without one cannot enrol."""

    @override_settings(TWO_FACTOR_ENROLMENT_REQUIRES_PASSWORD=False)
    def test_a_leftover_opt_out_is_reported(self):
        warnings = check_removed_enrolment_password_setting()

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].id, "stepup.W005")

    def test_an_absent_setting_is_silent(self):
        self.assertEqual(check_removed_enrolment_password_setting(), [])


class TestStepUpIsWellFormed(SimpleTestCase):
    """A STEP_UP the policy cannot read gates nothing, so it is an error."""

    def _ids(self):
        return [message.id for message in check_step_up_is_well_formed()]

    def _every_check_runs(self):
        """No check may crash on the setting it exists to report."""
        return [message.id for check in ALL_CHECKS for message in check()]

    @override_settings(STEP_UP=["change-email"])
    def test_a_setting_that_is_not_a_dict_is_reported(self):
        """A list where the dict belongs reads as gating nothing."""
        self.assertEqual(self._ids(), ["stepup.E001"])
        self.assertIn("stepup.E001", self._every_check_runs())

    @override_settings(STEP_UP={"ACTIONS": None})
    def test_actions_that_are_not_a_collection_are_reported(self):
        """The checks report None instead of raising TypeError."""
        self.assertEqual(self._ids(), ["stepup.E001"])
        self.assertIn("stepup.E001", self._every_check_runs())

    @override_settings(STEP_UP={"ACTIONS": ["change-email", ["change-password"]]})
    def test_actions_that_are_not_strings_are_reported(self):
        """The policy skips a nested list because it is unhashable."""
        self.assertEqual(self._ids(), ["stepup.E001"])
        self.assertIn("stepup.E001", self._every_check_runs())

    @override_settings(STEP_UP={"ACTIONS": {"change-email": True}})
    def test_actions_given_as_a_dict_are_reported(self):
        """A dict would gate its keys, which is unlikely to be what was meant."""
        self.assertEqual(self._ids(), ["stepup.E001"])

    @override_settings(STEP_UP={"MODE": ["local"]})
    def test_an_unhashable_mode_is_reported_rather_than_raised(self):
        """Membership of a list in a frozenset raises TypeError."""
        self.assertEqual(
            [message.id for message in check_step_up_mode_is_known()],
            ["stepup.W003"],
        )

    @override_settings(STEP_UP={"ACTIONS": ["change-email"], "MODE": "local"})
    def test_a_list_of_actions_is_silent(self):
        """A well-formed setting is not reported."""
        self.assertEqual(self._ids(), [])

    @override_settings(STEP_UP={"ACTIONS": "change-email"})
    def test_a_single_action_as_a_string_is_silent(self):
        """The policy reads a bare string as one action."""
        self.assertEqual(self._ids(), [])

    @override_settings(STEP_UP=None)
    def test_an_unset_setting_is_silent(self):
        """A deployment that never configured step-up is not reported."""
        self.assertEqual(self._ids(), [])


class TestStepUpActionsAreKnown(SimpleTestCase):
    """An action name no gate checks protects nothing, in either mode."""

    @override_settings(STEP_UP={"ACTIONS": ["change-emial"], "MODE": "local"})
    def test_an_unknown_action_is_reported_in_local_mode(self):
        """A typo leaves the intended action ungated."""
        errors = check_step_up_actions_are_known()

        self.assertEqual([e.id for e in errors], ["stepup.E002"])
        self.assertTrue(errors[0].is_serious())
        self.assertIn("change-emial", errors[0].msg)

    @override_settings(STEP_UP={"ACTIONS": ["change-emial"], "MODE": "federated"})
    def test_an_unknown_action_is_reported_in_federated_mode(self):
        """Federated mode has no other check that would catch it."""
        errors = check_step_up_actions_are_known()

        self.assertEqual([e.id for e in errors], ["stepup.E002"])

    @override_settings(
        STEP_UP={"ACTIONS": ["change-email", "publish-data"], "MODE": "federated"}
    )
    def test_known_actions_are_silent(self):
        """Real action names are not reported."""
        self.assertEqual(check_step_up_actions_are_known(), [])


class TestNoFactorPolicyIsKnown(SimpleTestCase):
    """An unrecognised NO_FACTOR_POLICY refuses users with no factor for a
    reason no one chose."""

    @override_settings(STEP_UP={"NO_FACTOR_POLICY": "deny"})
    def test_an_unknown_policy_is_reported(self):
        """A misspelt policy refuses users with no factor."""
        warnings = check_step_up_no_factor_policy_is_known()

        self.assertEqual([w.id for w in warnings], ["stepup.W008"])
        self.assertIn("deny", warnings[0].msg)

    @override_settings(STEP_UP={"NO_FACTOR_POLICY": "deny_prompt_enrol"})
    def test_deny_prompt_enrol_is_silent(self):
        """A known policy is not reported."""
        self.assertEqual(check_step_up_no_factor_policy_is_known(), [])

    @override_settings(STEP_UP={})
    def test_the_default_policy_is_silent(self):
        """An unset policy falls back to skip_gate, which is known."""
        self.assertEqual(check_step_up_no_factor_policy_is_known(), [])


class TestOAuthApprovalCanStepUp(SimpleTestCase):
    """The OAuth pages cannot run a challenge, so gating them refuses every
    approval the gate challenges."""

    @override_settings(STEP_UP={"ACTIONS": ["authorize-oauth-app"], "MODE": "local"})
    def test_gating_oauth_approval_is_reported(self):
        warnings = check_oauth_approval_can_step_up()

        self.assertEqual([w.id for w in warnings], ["stepup.W009"])

    @override_settings(
        STEP_UP={"ACTIONS": ["authorize-oauth-app"], "MODE": "federated"}
    )
    def test_federated_mode_is_reported_too(self):
        self.assertEqual(
            [w.id for w in check_oauth_approval_can_step_up()], ["stepup.W009"]
        )

    @override_settings(STEP_UP={"ACTIONS": ["change-email"], "MODE": "local"})
    def test_other_gates_are_silent(self):
        self.assertEqual(check_oauth_approval_can_step_up(), [])
