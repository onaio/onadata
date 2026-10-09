# -*- coding: utf-8 -*-
"""Tests for which actions are gated, and how this deployment proves a factor."""

from django.test import TestCase, override_settings

from onadata.libs.stepup.policy import is_gated, mode, no_factor_policy


@override_settings(STEP_UP={"ACTIONS": {"require-auth-toggle"}})
class TestPolicy(TestCase):
    def test_only_listed_actions_are_gated(self):
        self.assertTrue(is_gated("require-auth-toggle"))
        self.assertFalse(is_gated("something-else"))

    @override_settings(STEP_UP={})
    def test_an_unconfigured_deployment_behaves_as_before(self):
        """Nothing gated, the local dialect, and no refusal for users without
        a factor -- so installing this package changes no behaviour until a
        deployment opts in."""
        self.assertFalse(is_gated("require-auth-toggle"))
        self.assertEqual(mode(), "local")
        self.assertEqual(no_factor_policy(), "skip_gate")

    @override_settings(STEP_UP={"MODE": "federated"})
    def test_the_topology_is_swappable_by_configuration(self):
        """The whole claim the dialect seam makes."""
        self.assertEqual(mode(), "federated")
