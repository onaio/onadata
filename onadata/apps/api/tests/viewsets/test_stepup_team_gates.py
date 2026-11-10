# -*- coding: utf-8 -*-
"""
Tests for the step-up gates on the team endpoints.
"""

import json

from django.test.utils import override_settings

from oidc.stepup_grants import issue_grant, spend_grant

from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tools import add_user_to_team
from onadata.apps.api.viewsets.team_viewset import TeamViewSet
from onadata.libs.models.share_team_project import ShareTeamProject
from onadata.libs.permissions import ROLES, EditorRole, ManagerRole, OwnerRole


class TeamGateTestCase(TestAbstractViewSet):
    """An organisation with a team, and a user who belongs to neither."""

    def setUp(self):
        super().setUp()
        from django_otp.plugins.otp_totp.models import TOTPDevice

        TOTPDevice.objects.create(user=self.user, name="default", confirmed=True)
        self._team_create()
        self.alice = self._create_user("alice", "alice", create_profile=True)

    @staticmethod
    def _in_team(team, user):
        return team.user_set.filter(pk=user.pk).exists()


@override_settings(
    STEP_UP={
        "MODE": "local",
        "ACTIONS": ["grant-org-admin"],
        "NO_FACTOR_POLICY": "skip_gate",
    }
)
class TestOwnersTeamGate(TeamGateTestCase):
    """Joining the Owners team makes someone an organisation owner, so it
    needs the same proof as the organisation's members route."""

    def _members(self, method, team, username="alice", headers=None):
        view = TeamViewSet.as_view({"post": "members", "delete": "members"})
        request = getattr(self.factory, method)(
            "/",
            data=json.dumps({"username": username}),
            content_type="application/json",
            **{**self.extra, **(headers or {})},
        )
        return view(request, pk=team.pk)

    def _make_alice_an_owner(self):
        self._add_user_to_organization(self.organization, self.alice, "owner")
        self.assertTrue(self._in_team(self.owner_team, self.alice))

    def test_joining_the_owners_team_is_challenged(self):
        self.assertFalse(self._in_team(self.owner_team, self.alice))

        response = self._members("post", self.owner_team)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "grant-org-admin")
        self.assertFalse(self._in_team(self.owner_team, self.alice))
        self.assertFalse(self.organization.is_organization_owner(self.alice))

    def test_a_grant_lets_the_owner_through(self):
        self.assertFalse(self._in_team(self.owner_team, self.alice))
        grant = issue_grant(self.user.pk, "grant-org-admin")

        response = self._members(
            "post", self.owner_team, headers={"HTTP_X_STEP_UP_GRANT": grant}
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("alice", response.data)
        self.assertTrue(self.organization.is_organization_owner(self.alice))

    def test_joining_another_team_is_not_challenged(self):
        self.assertFalse(self._in_team(self.team, self.alice))

        response = self._members("post", self.team)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(self._in_team(self.team, self.alice))
        self.assertFalse(self.organization.is_organization_owner(self.alice))

    def test_re_adding_an_owner_is_not_challenged(self):
        self._make_alice_an_owner()

        response = self._members("post", self.owner_team)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(self._in_team(self.owner_team, self.alice))

    def test_removing_an_owner_is_not_challenged(self):
        self._make_alice_an_owner()

        response = self._members("delete", self.owner_team)

        self.assertEqual(response.status_code, 201)
        self.assertFalse(self._in_team(self.owner_team, self.alice))

    def test_an_unknown_user_keeps_the_grant(self):
        """The username is checked first, so a typo does not spend it."""
        grant = issue_grant(self.user.pk, "grant-org-admin")

        response = self._members(
            "post",
            self.owner_team,
            username="nobody",
            headers={"HTTP_X_STEP_UP_GRANT": grant},
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(spend_grant(self.user.pk, "grant-org-admin", grant))


@override_settings(
    STEP_UP={
        "MODE": "local",
        "ACTIONS": ["share-team-admin"],
        "NO_FACTOR_POLICY": "skip_gate",
    }
)
class TestTeamShareGate(TeamGateTestCase):
    """An owner or manager of a project can share it onwards, so giving a
    whole team that role needs a second factor."""

    def setUp(self):
        super().setUp()
        self._project_create()
        add_user_to_team(self.team, self.alice)
        self.assertTrue(self._in_team(self.team, self.alice))

    def _share(self, role, headers=None, **extra_data):
        view = TeamViewSet.as_view({"post": "share"})
        request = self.factory.post(
            "/",
            data=json.dumps({"role": role, "project": self.project.pk, **extra_data}),
            content_type="application/json",
            **{**self.extra, **(headers or {})},
        )
        return view(request, pk=self.team.pk)

    def _give_the_team(self, role):
        ShareTeamProject(self.team, self.project, role).save()
        self.assertTrue(ROLES[role].user_has_role(self.alice, self.project))

    def test_sharing_the_manager_role_is_challenged(self):
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))

        response = self._share("manager")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "share-team-admin")
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))

    def test_a_grant_lets_the_owner_role_through(self):
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.project))
        grant = issue_grant(self.user.pk, "share-team-admin")

        response = self._share("owner", {"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 204)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.project))

    def test_other_roles_are_not_challenged(self):
        self.assertFalse(EditorRole.user_has_role(self.alice, self.project))

        response = self._share("editor")

        self.assertEqual(response.status_code, 204)
        self.assertTrue(EditorRole.user_has_role(self.alice, self.project))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))

    def test_a_role_the_team_holds_is_not_challenged(self):
        self._give_the_team("manager")

        response = self._share("manager")

        self.assertEqual(response.status_code, 204)
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))

    def test_removing_the_team_is_not_challenged(self):
        """Removal takes away whatever the team holds, whichever role it
        names, so naming one the team lacks still removes it."""
        self._give_the_team("manager")
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.project))

        response = self._share("owner", remove=True)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))

    def test_an_unknown_project_keeps_the_grant(self):
        """The project is checked first, so a typo does not spend it."""
        grant = issue_grant(self.user.pk, "share-team-admin")

        response = self._share(
            "manager", {"HTTP_X_STEP_UP_GRANT": grant}, project=999999
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(spend_grant(self.user.pk, "share-team-admin", grant))
