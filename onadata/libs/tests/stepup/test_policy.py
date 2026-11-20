# -*- coding: utf-8 -*-
"""Tests for which actions are gated, and how this deployment proves a factor."""

from django.test import TestCase, override_settings

from onadata.libs.stepup.policy import (
    eu_consent_path,
    is_gated,
    mode,
    no_factor_policy,
)


@override_settings(STEP_UP={"ACTIONS": {"require-auth-toggle"}})
class TestPolicy(TestCase):
    def test_only_listed_actions_are_gated(self):
        self.assertTrue(is_gated("require-auth-toggle"))
        self.assertFalse(is_gated("something-else"))

    @override_settings(STEP_UP={})
    def test_an_unconfigured_deployment_behaves_as_before(self):
        """A deployment that has not opted in gates nothing, uses the local
        dialect and lets users without a factor through."""
        self.assertFalse(is_gated("require-auth-toggle"))
        self.assertEqual(mode(), "local")
        self.assertEqual(no_factor_policy(), "skip_gate")

    @override_settings(
        STEP_UP={"ACTIONS": "change-email"},
        EU_CONSENT_METADATA_PATH="eu_citizen_consent",
    )
    def test_a_string_setting_is_one_entry_not_its_characters(self):
        self.assertTrue(is_gated("change-email"))
        self.assertFalse(is_gated("c"))
        self.assertEqual(eu_consent_path(), ("eu_citizen_consent",))

    @override_settings(STEP_UP={"ACTIONS": None})
    def test_actions_that_are_not_a_collection_gate_nothing(self):
        """The policy reads it as empty instead of raising, so the startup
        check can report it."""
        self.assertFalse(is_gated("change-email"))

    @override_settings(STEP_UP=["change-email"])
    def test_a_setting_that_is_not_a_dict_gates_nothing(self):
        """The policy reads it as unconfigured, and stepup.E001 reports it."""
        self.assertFalse(is_gated("change-email"))
        self.assertEqual(mode(), "local")

    @override_settings(STEP_UP={"ACTIONS": ["change-email", ["publish-data"]]})
    def test_entries_that_are_not_strings_are_skipped(self):
        """An unhashable entry would otherwise crash every gate."""
        self.assertTrue(is_gated("change-email"))
        self.assertFalse(is_gated("publish-data"))
