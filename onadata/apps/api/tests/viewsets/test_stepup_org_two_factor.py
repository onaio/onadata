# -*- coding: utf-8 -*-
"""
Tests for an organisation requiring two-factor for protected actions on what
it owns: the setting, the gate on changing it, and its enforcement.

Every test refusing a user with no factor runs under ``skip_gate``, so the
organisation setting is the only reason for the refusal. Each also shows the
same request going through once the setting is cleared.
"""

from django.core.cache import cache

from django_otp.plugins.otp_totp.models import TOTPDevice
from oidc.stepup_grants import spend_grant

from onadata.apps.api.models.organization_profile import OrganizationProfile
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import (
    StepUpGateTestCase,
    gating,
)
from onadata.apps.api.viewsets.organization_profile_viewset import (
    OrganizationProfileViewSet,
)
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.v2.organization_profile_viewset import (
    OrganizationProfileViewSet as OrganizationProfileViewSetV2,
)
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.libs.permissions import ManagerRole
from onadata.libs.stepup.policy import GATE_ORG_TWO_FACTOR_POLICY

ENROL_REQUIRED = {"error": "enrol_required"}


class OrgTwoFactorTestCase(TestAbstractViewSet):
    """``self.user`` owns the ``denoinc`` organisation and has no factor."""

    def setUp(self):
        super().setUp()
        self._org_create()
        username = self.organization.user.username
        self.org_url = f"http://testserver/api/v1/users/{username}"

    def tearDown(self):
        super().tearDown()
        cache.clear()

    def _patch_org(self, data, headers=None, viewset=OrganizationProfileViewSet):
        view = viewset.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/", data=data, format="json", **{**self.extra, **(headers or {})}
        )
        return view(request, user="denoinc")

    def _get_org(self, extra=None, viewset=OrganizationProfileViewSet):
        view = viewset.as_view({"get": "retrieve"})
        request = self.factory.get("/", **(self.extra if extra is None else extra))
        return view(request, user="denoinc")

    def _required(self):
        return OrganizationProfile.objects.get(
            pk=self.organization.pk
        ).two_factor_required_actions

    def _require(self, actions):
        OrganizationProfile.objects.filter(pk=self.organization.pk).update(
            two_factor_required_actions=actions
        )
        self.assertEqual(self._required(), actions)

    def assert_enrol_required(self, response):
        self.assertEqual(response.status_code, 403, response.data)
        self.assertEqual(response.data, ENROL_REQUIRED)


@gating("publish-data", "share-project-admin", "change-password")
class TestTwoFactorRequiredActionsField(OrgTwoFactorTestCase):
    def test_an_owner_sets_the_actions_deduplicated_and_sorted(self):
        response = self._patch_org(
            {
                "two_factor_required_actions": [
                    "share-project-admin",
                    "publish-data",
                    "share-project-admin",
                ]
            }
        )

        self.assertEqual(response.status_code, 200, response.data)
        expected = ["publish-data", "share-project-admin"]
        self.assertEqual(response.data["two_factor_required_actions"], expected)
        self.assertEqual(self._required(), expected)

    def test_an_owner_sets_all(self):
        response = self._patch_org({"two_factor_required_actions": ["all"]})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._required(), ["all"])

    def test_an_owner_clears_the_actions(self):
        self._require(["all"])

        response = self._patch_org({"two_factor_required_actions": []})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._required(), [])

    def test_an_unknown_action_is_rejected(self):
        for actions in (["no-such-action"], ["publish-data", "change-password"]):
            response = self._patch_org({"two_factor_required_actions": actions})

            self.assertEqual(response.status_code, 400, actions)
            self.assertIn("two_factor_required_actions", response.data)
        self.assertEqual(self._required(), [])

    def test_all_mixed_with_other_actions_is_rejected(self):
        response = self._patch_org(
            {"two_factor_required_actions": ["all", "publish-data"]}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("two_factor_required_actions", response.data)
        self.assertEqual(self._required(), [])

    def test_anonymous_users_do_not_see_the_fields(self):
        response = self._get_org()
        self.assertEqual(response.data["two_factor_required_actions"], [])
        self.assertIn("two_factor_action_choices", response.data)

        response = self._get_org(extra={})

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("two_factor_required_actions", response.data)
        self.assertNotIn("two_factor_action_choices", response.data)

    def test_choices_are_the_gated_org_scoped_actions(self):
        """change-password is gated but concerns only the user's account."""
        response = self._get_org()

        self.assertEqual(
            response.data["two_factor_action_choices"],
            ["publish-data", "share-project-admin"],
        )

    @gating()
    def test_choices_are_empty_when_nothing_is_gated(self):
        # setUp cached the profile under the class's settings.
        cache.clear()

        response = self._get_org()

        self.assertEqual(response.data["two_factor_action_choices"], [])


@gating(GATE_ORG_TWO_FACTOR_POLICY, "require-auth-toggle")
class TestTwoFactorPolicyGate(StepUpGateTestCase, OrgTwoFactorTestCase):
    """Changing the setting is itself a protected action. ``self.user`` has a
    factor here."""

    audience = GATE_ORG_TWO_FACTOR_POLICY

    def test_changing_the_actions_is_challenged(self):
        response = self._patch_org({"two_factor_required_actions": ["all"]})

        self.assert_challenged(response)
        self.assertEqual(self._required(), [])

    def test_a_grant_lets_the_change_through(self):
        grant = self._grant()

        response = self._patch_org(
            {"two_factor_required_actions": ["all"]}, self._with_grant(grant)
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._required(), ["all"])
        self.assert_spent(grant)

    def test_writing_back_the_same_actions_is_not_challenged(self):
        self._require(["publish-data", "share-project-admin"])
        self.assert_challenged(
            self._patch_org({"two_factor_required_actions": ["publish-data"]})
        )

        response = self._patch_org(
            {
                "two_factor_required_actions": [
                    "share-project-admin",
                    "publish-data",
                ],
                "name": "Dennis Inc",
            }
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._required(), ["publish-data", "share-project-admin"])

    def test_changing_it_with_require_auth_is_refused_whole(self):
        response = self._patch_org(
            {"two_factor_required_actions": ["all"], "require_auth": True}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "one_gated_change_per_request")
        self.assertEqual(self._required(), [])

    def test_an_owner_with_no_factor_is_refused_once_the_org_requires_it(self):
        TOTPDevice.objects.filter(user=self.user).delete()
        self.assertEqual(
            self._patch_org({"two_factor_required_actions": ["all"]}).status_code,
            200,
        )

        response = self._patch_org({"two_factor_required_actions": []})

        self.assert_enrol_required(response)
        self.assertEqual(self._required(), ["all"])

    def test_a_requirement_that_does_not_list_itself_still_guards_itself(self):
        TOTPDevice.objects.filter(user=self.user).delete()
        self._require(["publish-data"])
        self.assertEqual(self._required(), ["publish-data"])

        response = self._patch_org({"two_factor_required_actions": []})

        self.assert_enrol_required(response)
        self.assertEqual(self._required(), ["publish-data"])


@gating(GATE_ORG_TWO_FACTOR_POLICY, "publish-data", "change-password")
class TestTwoFactorSettingOnV2(StepUpGateTestCase, OrgTwoFactorTestCase):
    """The v2 endpoint exposes and gates the setting as v1 does, and a change
    through it reaches both versions' caches."""

    audience = GATE_ORG_TWO_FACTOR_POLICY

    def _patch_v2(self, data, headers=None):
        return self._patch_org(data, headers, viewset=OrganizationProfileViewSetV2)

    def _get_both(self):
        return (
            self._get_org(viewset=OrganizationProfileViewSet),
            self._get_org(viewset=OrganizationProfileViewSetV2),
        )

    def test_reads_the_fields(self):
        self._require(["publish-data"])

        response = self._get_org(viewset=OrganizationProfileViewSetV2)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["two_factor_required_actions"], ["publish-data"])
        self.assertEqual(
            response.data["two_factor_action_choices"],
            [GATE_ORG_TWO_FACTOR_POLICY, "publish-data"],
        )
        anonymous = self._get_org(extra={}, viewset=OrganizationProfileViewSetV2)
        self.assertNotIn("two_factor_required_actions", anonymous.data)
        self.assertNotIn("two_factor_action_choices", anonymous.data)

    def test_a_grant_lets_the_change_through_and_refreshes_both_caches(self):
        for cached in self._get_both():
            self.assertEqual(cached.data["two_factor_required_actions"], [])
        grant = self._grant()

        response = self._patch_v2(
            {"two_factor_required_actions": ["publish-data", "publish-data"]},
            self._with_grant(grant),
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["two_factor_required_actions"], ["publish-data"])
        self.assertEqual(self._required(), ["publish-data"])
        self.assert_spent(grant)
        for fresh in self._get_both():
            self.assertEqual(
                fresh.data["two_factor_required_actions"], ["publish-data"]
            )

    def test_an_invalid_value_is_rejected_and_keeps_the_grant(self):
        grant = self._grant()

        response = self._patch_v2(
            {"two_factor_required_actions": ["all", "publish-data"]},
            self._with_grant(grant),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("two_factor_required_actions", response.data)
        self.assertEqual(self._required(), [])
        self.assertTrue(spend_grant(self.user.pk, self.audience, grant))


ENFORCED = (
    "share-project-admin",
    "publish-data",
    "transfer-project",
    "regenerate-api-key",
)


@gating(*ENFORCED)
class TestOrgTwoFactorEnforcement(OrgTwoFactorTestCase):
    def setUp(self):
        super().setUp()
        self._project_create({"owner": self.org_url})
        self.assertEqual(self.project.organization, self.organization.user)
        self.alice = self._create_user("alice", "alice", create_profile=True)

    def _share(self, role=ManagerRole.name, headers=None):
        view = ProjectViewSet.as_view({"put": "share"})
        request = self.factory.put(
            "/",
            data={"username": "alice", "role": role},
            **{**self.extra, **(headers or {})},
        )
        return view(request, pk=self.project.pk)

    def _patch_project(self, project, data):
        view = ProjectViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch("/", data=data, **self.extra)
        return view(request, pk=project.pk)

    def _alice_manages(self):
        return ManagerRole.user_has_role(self.alice, self.project)

    def test_a_listed_action_is_refused_to_a_user_with_no_factor(self):
        self._require(["share-project-admin"])

        response = self._share()

        self.assert_enrol_required(response)
        self.assertFalse(self._alice_manages())
        self._require([])
        self.assertEqual(self._share().status_code, 204)
        self.assertTrue(self._alice_manages())

    def test_an_action_the_org_does_not_list_is_allowed(self):
        self._require(["publish-data"])
        self.assert_enrol_required(self._patch_project(self.project, {"public": True}))

        response = self._share()

        self.assertEqual(response.status_code, 204)
        self.assertTrue(self._alice_manages())

    def test_a_transfer_into_a_requiring_org_is_refused(self):
        self._project_create({"name": "personal"})
        personal = self.project
        self.assertEqual(personal.organization, self.user)
        self._require(["transfer-project"])

        response = self._patch_project(personal, {"owner": self.org_url})

        self.assert_enrol_required(response)
        personal.refresh_from_db()
        self.assertEqual(personal.organization, self.user)
        self._require([])
        response = self._patch_project(personal, {"owner": self.org_url})
        self.assertEqual(response.status_code, 200, response.data)
        personal.refresh_from_db()
        self.assertEqual(personal.organization, self.organization.user)

    def test_a_transfer_out_of_a_requiring_org_is_refused(self):
        self._require(["transfer-project"])
        user_url = f"http://testserver/api/v1/users/{self.user.username}"

        response = self._patch_project(self.project, {"owner": user_url})

        self.assert_enrol_required(response)
        self.project.refresh_from_db()
        self.assertEqual(self.project.organization, self.organization.user)
        self._require([])
        response = self._patch_project(self.project, {"owner": user_url})
        self.assertEqual(response.status_code, 200, response.data)

    def test_publishing_an_org_form_is_refused(self):
        self._publish_xls_form_to_project()
        self.assertEqual(self.xform.user, self.organization.user)
        self._require(["publish-data"])
        view = XFormViewSet.as_view({"patch": "partial_update"})

        def make_public():
            request = self.factory.patch("/", data={"shared": True}, **self.extra)
            return view(request, pk=self.xform.pk)

        self.assert_enrol_required(make_public())
        self.xform.refresh_from_db()
        self.assertFalse(self.xform.shared)
        self._require([])
        self.assertEqual(make_public().status_code, 200)
        self.xform.refresh_from_db()
        self.assertTrue(self.xform.shared)
