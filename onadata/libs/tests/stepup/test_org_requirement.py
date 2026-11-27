# -*- coding: utf-8 -*-
"""Tests for an organisation requiring two-factor for its protected actions."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from django_otp.plugins.otp_totp.models import TOTPDevice

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.viewsets.totp_viewset import _known_audiences
from onadata.libs.stepup.gate import (
    ENROL_REQUIRED,
    STEP_UP_REQUIRED,
    change_refusal,
    refusal_reason,
)
from onadata.libs.stepup.organizations import requiring_organization
from onadata.libs.stepup.policy import (
    GATE_ORG_TWO_FACTOR_POLICY,
    KNOWN_ACTIONS,
    ORG_SCOPED_ACTIONS,
    requires_two_factor,
)
from onadata.libs.tests.stepup.test_drf import _GateHarness

SKIP_GATE = {
    "MODE": "local",
    "NO_FACTOR_POLICY": "skip_gate",
    "ACTIONS": ["publish-data", "share-project-admin", "change-password"],
}

ACCOUNT_ONLY_ACTIONS = {
    "privacy-consent",
    "regenerate-api-key",
    "regenerate-odk-token",
    "change-email",
    "change-password",
    "change-username",
    "authorize-oauth-app",
}


class TestOrgScopedActions(TestCase):
    def test_the_new_action_is_known_and_org_scoped(self):
        self.assertIn(GATE_ORG_TWO_FACTOR_POLICY, KNOWN_ACTIONS)
        self.assertIn(GATE_ORG_TWO_FACTOR_POLICY, ORG_SCOPED_ACTIONS)

    def test_a_grant_can_be_minted_for_the_new_action(self):
        self.assertIn(GATE_ORG_TWO_FACTOR_POLICY, _known_audiences())

    def test_account_only_actions_are_not_org_scoped(self):
        self.assertTrue(ACCOUNT_ONLY_ACTIONS <= KNOWN_ACTIONS)
        self.assertFalse(ACCOUNT_ONLY_ACTIONS & ORG_SCOPED_ACTIONS)
        self.assertEqual(ORG_SCOPED_ACTIONS, KNOWN_ACTIONS - ACCOUNT_ONLY_ACTIONS)


class TestRequiresTwoFactor(TestCase):
    def test_a_listed_action_is_covered(self):
        self.assertTrue(requires_two_factor(["publish-data"], "publish-data"))
        self.assertFalse(requires_two_factor(["publish-data"], "transfer-project"))

    def test_all_covers_every_org_scoped_action(self):
        for action in ORG_SCOPED_ACTIONS:
            self.assertTrue(requires_two_factor(["all"], action), action)

    def test_all_does_not_cover_account_actions(self):
        self.assertTrue(requires_two_factor(["all"], "publish-data"))
        for action in ACCOUNT_ONLY_ACTIONS:
            self.assertFalse(requires_two_factor(["all"], action), action)

    def test_any_requirement_covers_changing_itself(self):
        self.assertFalse(requires_two_factor([], GATE_ORG_TWO_FACTOR_POLICY))

        self.assertTrue(
            requires_two_factor(["publish-data"], GATE_ORG_TWO_FACTOR_POLICY)
        )

    def test_a_malformed_value_covers_nothing(self):
        """The field is validated on write, but a value set elsewhere must
        not crash every gate."""
        self.assertTrue(requires_two_factor(["publish-data"], "publish-data"))
        for value in (None, "publish-data", "all", {"publish-data": True}, 3):
            self.assertFalse(requires_two_factor(value, "publish-data"), value)


class OrgHarness(_GateHarness):
    def setUp(self):
        super().setUp()
        self.org_user = get_user_model().objects.create(username="denoinc")
        self.organization = OrganizationProfile.objects.create(
            user=self.org_user, name="Dennis", creator=self.user
        )
        self.person = get_user_model().objects.create(username="tom")

    def _require(self, actions):
        OrganizationProfile.objects.filter(pk=self.organization.pk).update(
            two_factor_required_actions=actions
        )


class TestRequiringOrganization(OrgHarness):
    def test_returns_the_organisation_that_requires_the_action(self):
        self.assertIsNone(requiring_organization((self.org_user,), "publish-data"))
        self._require(["publish-data"])

        self.assertEqual(
            requiring_organization((self.org_user,), "publish-data"), "denoinc"
        )

    def test_any_of_several_actions_counts(self):
        self._require(["share-team-admin"])
        self.assertIsNone(requiring_organization((self.org_user,), "grant-org-admin"))

        self.assertEqual(
            requiring_organization(
                (self.org_user,), ("grant-org-admin", "share-team-admin")
            ),
            "denoinc",
        )

    def test_accepts_primary_keys(self):
        self._require(["publish-data"])

        self.assertEqual(
            requiring_organization((self.org_user.pk,), "publish-data"), "denoinc"
        )

    def test_owners_that_are_not_organisations_are_skipped(self):
        self._require(["publish-data"])
        self.assertEqual(
            requiring_organization((self.org_user,), "publish-data"), "denoinc"
        )

        self.assertIsNone(requiring_organization((self.person,), "publish-data"))
        self.assertIsNone(requiring_organization((None,), "publish-data"))

    def test_looks_up_every_owner_in_one_query(self):
        self._require(["publish-data"])
        owners = (self.person, self.org_user, self.user.pk, None)

        with self.assertNumQueries(1):
            found = requiring_organization(owners, "publish-data")

        self.assertEqual(found, "denoinc")

    def test_no_query_for_an_account_action_or_no_owners(self):
        self._require(["all"])

        with self.assertNumQueries(0):
            self.assertIsNone(requiring_organization((self.org_user,), "change-email"))
            self.assertIsNone(requiring_organization((), "publish-data"))

    def test_owners_are_read_lazily(self):
        """A generator of owners is not consumed for an account action."""
        consumed = []

        def owners():
            consumed.append(True)
            yield self.org_user

        requiring_organization(owners(), "change-email")

        self.assertEqual(consumed, [])
        self.assertIsNone(requiring_organization(owners(), "publish-data"))
        self.assertEqual(consumed, [True])


@override_settings(STEP_UP=SKIP_GATE)
class TestRefusalReasonWithOwners(OrgHarness):
    """``skip_gate`` lets a user with no factor through, unless an
    organisation owning the target requires two-factor for the action."""

    def test_a_requiring_organisation_refuses_a_user_with_no_factor(self):
        self.assertIsNone(
            refusal_reason(self._request(), "publish-data", (self.org_user,))
        )
        self._require(["publish-data"])

        reason = refusal_reason(self._request(), "publish-data", (self.org_user,))

        self.assertEqual(reason, ENROL_REQUIRED)

    def test_the_refusal_is_audited(self):
        self._require(["publish-data"])

        with self.assertLogs("audit_logger", level="DEBUG") as captured:
            reason = refusal_reason(self._request(), "publish-data", (self.org_user,))

        self.assertEqual(reason, ENROL_REQUIRED)
        records = [
            r
            for r in captured.records
            if getattr(r, "formhub_action", None) == "step-up-enrol-required"
        ]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].audit, {"audience": "publish-data"})
        self.assertIn("denoinc", records[0].getMessage())

    def test_an_action_the_organisation_does_not_list_proceeds(self):
        self._require(["share-project-admin"])
        self.assertEqual(
            refusal_reason(self._request(), "share-project-admin", (self.org_user,)),
            ENROL_REQUIRED,
        )

        self.assertIsNone(
            refusal_reason(self._request(), "publish-data", (self.org_user,))
        )

    def test_a_covered_change_the_organisation_requires_refuses(self):
        # One grant covers every gated change in such a request, but the
        # organisation's rule applies to each of them.
        self._require(["share-project-admin"])
        self.assertIsNone(
            refusal_reason(self._request(), "publish-data", (self.org_user,))
        )

        reason = refusal_reason(
            self._request(),
            "publish-data",
            (self.org_user,),
            covers=(("share-project-admin", True),),
        )

        self.assertEqual(reason, ENROL_REQUIRED)

    def test_a_covered_change_that_does_not_happen_is_ignored(self):
        self._require(["share-project-admin"])

        reason = refusal_reason(
            self._request(),
            "publish-data",
            (self.org_user,),
            covers=(("share-project-admin", False),),
        )

        self.assertIsNone(reason)

    def test_without_owners_nothing_changes(self):
        self._require(["all"])
        self.assertEqual(
            refusal_reason(self._request(), "publish-data", (self.org_user,)),
            ENROL_REQUIRED,
        )

        self.assertIsNone(refusal_reason(self._request(), "publish-data"))

    def test_all_leaves_account_actions_alone(self):
        self._require(["all"])
        self.assertEqual(
            refusal_reason(self._request(), "publish-data", (self.org_user,)),
            ENROL_REQUIRED,
        )

        self.assertIsNone(
            refusal_reason(self._request(), "change-password", (self.org_user,))
        )

    def test_an_action_the_deployment_does_not_gate_proceeds(self):
        """The organisation setting applies only to actions the deployment
        gates."""
        self._require(["all"])
        self.assertEqual(
            refusal_reason(self._request(), "publish-data", (self.org_user,)),
            ENROL_REQUIRED,
        )

        self.assertIsNone(
            refusal_reason(self._request(), "transfer-project", (self.org_user,))
        )

    def test_a_user_with_a_factor_is_challenged_as_before(self):
        self._require(["publish-data"])
        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)

        reason = refusal_reason(self._request(), "publish-data", (self.org_user,))

        self.assertEqual(reason, STEP_UP_REQUIRED)

    def test_change_refusal_passes_owners_on(self):
        self._require(["publish-data"])
        changes = (("publish-data", True), ("share-project-admin", False))
        self.assertEqual(
            change_refusal(self._request(), changes), (None, ["publish-data"])
        )

        reason, audiences = change_refusal(
            self._request(), changes, owners=(self.org_user,)
        )

        self.assertEqual(reason, ENROL_REQUIRED)
        self.assertEqual(audiences, ["publish-data"])

    @override_settings(STEP_UP={**SKIP_GATE, "NO_FACTOR_POLICY": "deny_prompt_enrol"})
    def test_deny_prompt_enrol_still_refuses_without_a_requirement(self):
        self.assertIsNone(requiring_organization((self.org_user,), "publish-data"))

        reason = refusal_reason(self._request(), "publish-data", (self.org_user,))

        self.assertEqual(reason, ENROL_REQUIRED)


@override_settings(STEP_UP={**SKIP_GATE, "MODE": "federated"})
class TestFederatedModeIgnoresTheOrganisation(OrgHarness):
    """A federated deployment challenges every user and lets the identity
    provider decide, so the organisation setting does not change the
    answer."""

    def test_a_user_with_no_local_factor_is_challenged_not_refused(self):
        self.assertEqual(
            refusal_reason(self._request(), "publish-data"), STEP_UP_REQUIRED
        )
        self._require(["all"])

        reason = refusal_reason(self._request(), "publish-data", (self.org_user,))

        self.assertEqual(reason, STEP_UP_REQUIRED)
