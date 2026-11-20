# -*- coding: utf-8 -*-
"""
Tests for the step-up gates on the team endpoints.
"""

import json

from guardian.shortcuts import get_perms
from oidc.stepup_grants import issue_grant, spend_grant

from onadata.apps.api.models.organization_profile import create_organization_team
from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import (
    StepUpGateTestCase,
    gating,
)
from onadata.apps.api.tools import add_user_to_team
from onadata.apps.api.viewsets.team_viewset import TeamViewSet
from onadata.libs.models.share_team_project import ShareTeamProject
from onadata.libs.permissions import (
    ROLES,
    EditorRole,
    ManagerRole,
    OwnerRole,
    ReadOnlyRole,
)


class TeamGateTestCase(StepUpGateTestCase):
    """An organisation with a team, and a user who belongs to neither."""

    def setUp(self):
        super().setUp()
        self._team_create()
        self.alice = self._create_user("alice", "alice", create_profile=True)

    @staticmethod
    def _in_team(team, user):
        return team.user_set.filter(pk=user.pk).exists()

    def _members(self, method, team, username="alice", headers=None):
        view = TeamViewSet.as_view({"post": "members", "delete": "members"})
        request = getattr(self.factory, method)(
            "/",
            data=json.dumps({"username": username}),
            content_type="application/json",
            **{**self.extra, **(headers or {})},
        )
        return view(request, pk=team.pk)


@gating("grant-org-admin")
class TestOwnersTeamGate(TeamGateTestCase):
    """Joining the Owners team makes someone an organisation owner, so it
    needs the same proof as the organisation's members route."""

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
        self.assertEqual(self._members("post", self.owner_team).status_code, 401)

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


@gating("share-team-admin")
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
        self.assertEqual(self._share("manager").status_code, 401)

        response = self._share("editor")

        self.assertEqual(response.status_code, 204)
        self.assertTrue(EditorRole.user_has_role(self.alice, self.project))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))

    def test_a_role_the_team_holds_is_not_challenged(self):
        self.assertEqual(self._share("manager").status_code, 401)
        self._give_the_team("manager")

        response = self._share("manager")

        self.assertEqual(response.status_code, 204)
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))

    def test_removing_the_team_is_not_challenged(self):
        """Removal takes away whatever the team holds, whichever role it
        names, so naming one the team lacks still removes it."""
        self.assertEqual(self._share("manager").status_code, 401)
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


@gating("share-team-admin")
class TestJoinAdminTeamGate(TeamGateTestCase):
    """A new member takes on every role the team holds, so adding someone to
    a team that owns or manages a project or form appoints an admin of it."""

    def setUp(self):
        super().setUp()
        self._project_create()
        ShareTeamProject(self.team, self.project, ManagerRole.name).save()
        self.assertFalse(self._in_team(self.team, self.alice))

    def _readers(self):
        readers = create_organization_team(self.organization, "readers")
        ShareTeamProject(readers, self.project, EditorRole.name).save()
        return readers

    def test_joining_a_team_that_manages_a_project_is_challenged(self):
        """The 401 names the audience and leaves the user out of the team."""
        response = self._members("post", self.team)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "share-team-admin")
        self.assertFalse(self._in_team(self.team, self.alice))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))

    def test_joining_a_team_that_manages_only_a_form_is_challenged(self):
        """A role on a single form counts as much as one on a project."""
        self._publish_xls_form_to_project()
        form_team = create_organization_team(self.organization, "form admins")
        ManagerRole.add(form_team, self.xform)

        response = self._members("post", form_team)

        self.assertEqual(response.status_code, 401)
        self.assertFalse(self._in_team(form_team, self.alice))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.xform))

    def test_a_grant_lets_the_member_join(self):
        """With a grant the user joins and takes on the team's role."""
        grant = issue_grant(self.user.pk, "share-team-admin")

        response = self._members(
            "post", self.team, headers={"HTTP_X_STEP_UP_GRANT": grant}
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(self._in_team(self.team, self.alice))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.project))
        self.assertFalse(spend_grant(self.user.pk, "share-team-admin", grant))

    def test_joining_a_team_without_an_admin_role_is_not_challenged(self):
        """An editor team appoints no admin."""
        self.assertEqual(self._members("post", self.team).status_code, 401)
        readers = self._readers()

        response = self._members("post", readers)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(self._in_team(readers, self.alice))
        self.assertTrue(EditorRole.user_has_role(self.alice, self.project))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.project))

    def test_joining_a_team_meta_perms_make_admin_is_challenged(self):
        """An editor team counts as an admin one where a form's meta
        permissions make its editors owners."""
        self._publish_xls_form_to_project()
        readers = self._readers()
        self._set_meta_perms("owner|dataentry-only|readonly")

        response = self._members("post", readers)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "share-team-admin")
        self.assertFalse(self._in_team(readers, self.alice))

    def test_joining_a_team_meta_perms_keep_below_admin_is_not_challenged(self):
        """The default meta permissions leave an editor team's members
        editors."""
        self._publish_xls_form_to_project()
        readers = self._readers()
        self.assertEqual(self._members("post", self.team).status_code, 401)

        response = self._members("post", readers)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(self._in_team(readers, self.alice))
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.xform))

    def test_re_adding_a_member_is_not_challenged(self):
        """Someone already in the team gains nothing by joining again."""
        self.assertEqual(self._members("post", self.team).status_code, 401)
        add_user_to_team(self.team, self.alice)

        response = self._members("post", self.team)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(self._in_team(self.team, self.alice))

    def test_removing_a_member_is_not_challenged(self):
        """Taking a role away is never gated."""
        self.assertEqual(self._members("post", self.team).status_code, 401)
        add_user_to_team(self.team, self.alice)

        response = self._members("delete", self.team)

        self.assertEqual(response.status_code, 201)
        self.assertFalse(self._in_team(self.team, self.alice))

    def test_an_unknown_user_keeps_the_grant(self):
        """The username is checked first, so a typo does not spend it."""
        grant = issue_grant(self.user.pk, "share-team-admin")

        response = self._members(
            "post", self.team, "nobody", headers={"HTTP_X_STEP_UP_GRANT": grant}
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(spend_grant(self.user.pk, "share-team-admin", grant))


@gating("grant-org-admin", "share-team-admin")
class TestJoinOwnersTeamWithBothGates(TeamGateTestCase):
    """Joining the Owners team both appoints an organisation owner and joins
    a team that owns projects. One grant for the first gated audience covers
    both, so the request is not refused as two gated changes."""

    def setUp(self):
        super().setUp()
        self._project_create()
        OwnerRole.add(self.owner_team, self.project)
        self.assertTrue(
            OwnerRole.has_role(get_perms(self.owner_team, self.project), self.project)
        )

    def test_joining_the_owners_team_asks_for_the_org_admin_grant(self):
        """Challenged once, for ``grant-org-admin``."""
        response = self._members("post", self.owner_team)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "grant-org-admin")
        self.assertFalse(self._in_team(self.owner_team, self.alice))

    def test_the_org_admin_grant_lets_the_owner_join(self):
        """That one grant is enough."""
        grant = issue_grant(self.user.pk, "grant-org-admin")

        response = self._members(
            "post", self.owner_team, headers={"HTTP_X_STEP_UP_GRANT": grant}
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.organization.is_organization_owner(self.alice))


@gating("share-team-admin")
class TestTeamShareThroughMetaPermsGate(TeamGateTestCase):
    """A team share applies each form's meta permissions, so an editor share
    on a project whose form makes editors owners needs the same proof as an
    owner share."""

    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()
        add_user_to_team(self.team, self.alice)
        self._set_meta_perms("owner|dataentry-only|readonly")

    def _share(self, role, headers=None):
        view = TeamViewSet.as_view({"post": "share"})
        request = self.factory.post(
            "/",
            data=json.dumps({"role": role, "project": self.project.pk}),
            content_type="application/json",
            **{**self.extra, **(headers or {})},
        )
        return view(request, pk=self.team.pk)

    def test_an_editor_share_made_owner_is_challenged(self):
        """The 401 names the audience and the team gets no role."""
        response = self._share(EditorRole.name)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "share-team-admin")
        self.assertFalse(EditorRole.user_has_role(self.alice, self.project))

    def test_a_grant_lets_the_editor_share_through(self):
        """With a grant the team gets the role."""
        grant = issue_grant(self.user.pk, "share-team-admin")

        response = self._share(EditorRole.name, {"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 204)
        self.assertTrue(EditorRole.user_has_role(self.alice, self.project))
        self.assertFalse(spend_grant(self.user.pk, "share-team-admin", grant))

    def test_an_editor_share_kept_below_admin_is_not_challenged(self):
        """Meta permissions without an admin slot leave an editor an editor."""
        self.assertEqual(self._share(EditorRole.name).status_code, 401)
        self._set_meta_perms("editor-minor|dataentry-only|readonly")

        response = self._share(EditorRole.name)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(EditorRole.user_has_role(self.alice, self.project))

    def _carol_edits_the_form(self):
        """A user the stored meta permissions have not been applied to."""
        carol = self._create_user("carol", "carol", create_profile=True)
        EditorRole.add(carol, self.xform)
        self.assertFalse(OwnerRole.user_has_role(carol, self.xform))
        return carol

    def test_a_share_that_promotes_a_form_editor_is_challenged(self):
        """A share re-applies the meta permissions to every user of the form,
        so even a read-only one makes an editor an owner."""
        carol = self._carol_edits_the_form()

        response = self._share(ReadOnlyRole.name)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "share-team-admin")
        self.assertFalse(OwnerRole.user_has_role(carol, self.xform))

    def test_a_grant_lets_a_promoting_share_through(self):
        """With a grant the share goes through and the editor becomes an
        owner."""
        carol = self._carol_edits_the_form()
        grant = issue_grant(self.user.pk, "share-team-admin")

        response = self._share(ReadOnlyRole.name, {"HTTP_X_STEP_UP_GRANT": grant})

        self.assertEqual(response.status_code, 204)
        self.assertTrue(OwnerRole.user_has_role(carol, self.xform))
        self.assertFalse(spend_grant(self.user.pk, "share-team-admin", grant))

    def test_a_share_that_promotes_nobody_is_not_challenged(self):
        """With no form user left for the meta permissions to promote, a
        read-only share appoints nobody."""
        carol = self._carol_edits_the_form()
        self.assertEqual(self._share(ReadOnlyRole.name).status_code, 401)
        EditorRole.remove_obj_permissions(carol, self.xform)

        response = self._share(ReadOnlyRole.name)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(ReadOnlyRole.user_has_role(self.alice, self.project))


@gating("share-team-admin")
class TestMoveTeamGate(TeamGateTestCase):
    """A moved team keeps its roles on the old organisation's projects and
    forms, so moving it hands them to whoever runs the new organisation."""

    def setUp(self):
        super().setUp()
        home = self.organization
        self._org_create({"org": "otherinc"})
        self.other_org = self.organization
        self.organization = home

    def _update(self, organization, headers=None):
        view = TeamViewSet.as_view({"put": "update"})
        request = self.factory.put(
            "/",
            data=json.dumps({"name": "dreamteam", "organization": organization}),
            content_type="application/json",
            **{**self.extra, **(headers or {})},
        )
        return view(request, pk=self.team.pk)

    def _team_org(self):
        self.team.refresh_from_db()
        return self.team.organization

    def test_moving_a_team_is_challenged(self):
        response = self._update(self.other_org.user.username)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["audience"], "share-team-admin")
        self.assertEqual(self._team_org(), self.organization.user)

    def test_a_grant_lets_the_team_move(self):
        grant = issue_grant(self.user.pk, "share-team-admin")

        response = self._update(
            self.other_org.user.username, {"HTTP_X_STEP_UP_GRANT": grant}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._team_org(), self.other_org.user)
        self.assertFalse(spend_grant(self.user.pk, "share-team-admin", grant))

    def test_keeping_the_organisation_is_not_challenged(self):
        self.assertEqual(self._update(self.other_org.user.username).status_code, 401)

        response = self._update(self.organization.user.username)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._team_org(), self.organization.user)

    def test_renaming_without_an_organisation_is_not_challenged(self):
        view = TeamViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/",
            data=json.dumps({"name": "renamed"}),
            content_type="application/json",
            **self.extra,
        )

        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._team_org(), self.organization.user)
