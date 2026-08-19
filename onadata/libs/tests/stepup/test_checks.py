"""Tests for module onadata.libs.stepup.checks"""

from django.test import SimpleTestCase, override_settings

from onadata.libs.stepup.checks import check_step_up_actions_are_mintable

LOCAL_AUDIENCES = frozenset({"enroll-start", "disable", "recovery-generate"})


class TestActionsAreMintable(SimpleTestCase):
    """A gated action must have an audience /api/v1/totp/verify will mint."""

    @override_settings(
        TWO_FACTOR_STEP_UP_AUDIENCES=LOCAL_AUDIENCES,
        STEP_UP={"ACTIONS": {"require-auth-toggle"}, "MODE": "local"},
    )
    def test_an_ungrantable_action_is_reported(self):
        """The failure it catches: the caller is challenged for
        "require-auth-toggle", presents it to verify, and is refused with 400
        because the deployment never declared it -- so the gate can never be
        satisfied."""
        warnings = check_step_up_actions_are_mintable()

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].id, "stepup.W002")
        self.assertIn("require-auth-toggle", warnings[0].msg)

    @override_settings(
        TWO_FACTOR_STEP_UP_AUDIENCES=LOCAL_AUDIENCES | {"require-auth-toggle"},
        STEP_UP={"ACTIONS": {"require-auth-toggle"}, "MODE": "local"},
    )
    def test_a_declared_action_is_silent(self):
        self.assertEqual(check_step_up_actions_are_mintable(), [])

    @override_settings(
        TWO_FACTOR_STEP_UP_AUDIENCES=LOCAL_AUDIENCES,
        STEP_UP={"ACTIONS": set(), "MODE": "local"},
    )
    def test_gating_nothing_is_silent(self):
        """The shipped default gates nothing, so a stock deployment must not
        be warned at every management command."""
        self.assertEqual(check_step_up_actions_are_mintable(), [])

    @override_settings(
        TWO_FACTOR_STEP_UP_AUDIENCES=LOCAL_AUDIENCES,
        STEP_UP={"ACTIONS": {"require-auth-toggle"}, "MODE": "federated"},
    )
    def test_federated_mode_is_not_reported(self):
        """Federated grants are earned at the provider's callback, which never
        consults this list -- warning there would be noise."""
        self.assertEqual(check_step_up_actions_are_mintable(), [])
