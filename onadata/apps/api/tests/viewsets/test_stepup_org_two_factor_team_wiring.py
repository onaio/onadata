# -*- coding: utf-8 -*-
"""
Tests that the team, organisation and project gates pass the accounts owning
what they touch, as ``test_stepup_org_two_factor_wiring`` does for the data
paths.

Some requests make more than one gated change. Their tests check that an
organisation requiring any of those actions refuses the request, not only one
requiring the first.
"""


import json
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from guardian.shortcuts import get_perms

from onadata.apps.api.models.organization_profile import (
    OrganizationProfile,
    get_or_create_organization_owners_team,
    get_organization_members_team,
)
from onadata.apps.api.models.team import Team
from onadata.apps.api.tests.viewsets.test_stepup_org_two_factor_wiring import (
    OrgWiringTestCase,
    _url,
)
from onadata.apps.api.tests.viewsets.test_stepup_sharing_gates import (
    EDITOR_BECOMES_OWNER,
    gating,
)
from onadata.apps.api.tools import add_user_to_team
from onadata.apps.api.viewsets.organization_profile_viewset import (
    OrganizationProfileViewSet,
)
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.team_viewset import TeamViewSet
from onadata.apps.logger.models import (
    ProjectInvitation,
    XForm,
)
from onadata.apps.logger.models.kms import KMSKey
from onadata.apps.main.models import MetaData
from onadata.apps.main.views import edit, set_perm
from onadata.libs.models.share_team_project import ShareTeamProject
from onadata.libs.permissions import EditorRole, ManagerRole, OwnerRole
from onadata.libs.stepup.policy import (
    GATE_GRANT_ORG_ADMIN,
    GATE_INVITE_PROJECT_ADMIN,
    GATE_PUBLISH_DATA,
    GATE_ROTATE_ORG_KEY,
    GATE_SHARE_FORM_ADMIN,
    GATE_SHARE_TEAM_ADMIN,
    GATE_TRANSFER_PROJECT,
)
from onadata.libs.stepup.sharing import move_appoints_admins


class TeamWiringTestCase(OrgWiringTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self._create_user("alice", "alice", create_profile=True)
        self.team = self._create_team(self.organization, "dreamteam")

    def _create_team(self, organization, name):
        view = TeamViewSet.as_view({"post": "create"})
        data = {"name": name, "organization": organization.user.username}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        self.assertEqual(view(request).status_code, 201)
        team = Team.objects.get(
            organization=organization.user,
            name=f"{organization.user.username}#{name}",
        )
        self.assert_org_owns(team.organization, organization)
        return team

    def _team_post(self, team, action, data):
        view = TeamViewSet.as_view({"post": action})
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        return view(request, pk=team.pk)

    def _join(self, team):
        return self._team_post(team, "members", {"username": "alice"})

    def _in_team(self, team):
        return team.user_set.filter(pk=self.alice.pk).exists()


@gating(GATE_SHARE_TEAM_ADMIN)
class TestTeamShareOwners(TeamWiringTestCase):
    def setUp(self):
        super().setUp()
        add_user_to_team(self.team, self.alice)
        self.assertTrue(self._in_team(self.team))

    def _share(self, project):
        return self._team_post(
            self.team, "share", {"role": ManagerRole.name, "project": project.pk}
        )

    def _alice_manages(self, project):
        return ManagerRole.user_has_role(self.alice, project)

    def test_sharing_an_admin_role_is_refused_when_the_org_requires_it(self):
        self._require([GATE_SHARE_TEAM_ADMIN])

        self.assert_enrol_required(self._share(self.org_project))
        self.assertFalse(self._alice_manages(self.org_project))

    def test_sharing_an_admin_role_goes_through_when_not_required(self):
        self._require([])

        response = self._share(self.org_project)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(self._alice_manages(self.org_project))

    def test_the_projects_org_counts_when_it_is_not_the_teams(self):
        other = self._other_org()
        self._project_create(
            {"name": "other project", "owner": _url("users", other.user.username)}
        )
        other_project = self.project
        self.assert_org_owns(other_project.organization, other)
        self._require([])
        self._require_of(other, [GATE_SHARE_TEAM_ADMIN])

        self.assert_enrol_required(self._share(other_project))
        self.assertFalse(self._alice_manages(other_project))
        self._require_of(other, [])
        self.assertEqual(self._share(other_project).status_code, 204)
        self.assertTrue(self._alice_manages(other_project))


@gating(GATE_SHARE_TEAM_ADMIN)
class TestTeamMoveOwners(TeamWiringTestCase):
    def setUp(self):
        super().setUp()
        self.other = self._other_org()

    def _move(self, organization):
        view = TeamViewSet.as_view({"put": "update"})
        data = {"name": "dreamteam", "organization": organization.user.username}
        request = self.factory.put(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        return view(request, pk=self.team.pk)

    def _team_org(self):
        self.team.refresh_from_db()
        return self.team.organization

    def test_moving_a_team_out_is_refused_when_its_org_requires_it(self):
        self._require([GATE_SHARE_TEAM_ADMIN])
        self._require_of(self.other, [])

        self.assert_enrol_required(self._move(self.other))
        self.assert_org_owns(self._team_org())

    def test_moving_a_team_in_is_refused_when_the_new_org_requires_it(self):
        self._require([])
        self._require_of(self.other, [GATE_SHARE_TEAM_ADMIN])

        self.assert_enrol_required(self._move(self.other))
        self.assert_org_owns(self._team_org())

    def test_moving_a_team_goes_through_when_neither_org_requires_it(self):
        self._require([])
        self._require_of(self.other, [])

        response = self._move(self.other)

        self.assertEqual(response.status_code, 200, response.data)
        self.assert_org_owns(self._team_org(), self.other)


@gating(GATE_SHARE_TEAM_ADMIN)
class TestTeamJoinOwners(TeamWiringTestCase):
    def setUp(self):
        super().setUp()
        ShareTeamProject(self.team, self.org_project, ManagerRole.name).save()
        self.assertFalse(self._in_team(self.team))
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.org_project))

    def test_joining_an_admin_team_is_refused_when_the_org_requires_it(self):
        self._require([GATE_SHARE_TEAM_ADMIN])

        self.assert_enrol_required(self._join(self.team))
        self.assertFalse(self._in_team(self.team))

    def test_joining_an_admin_team_goes_through_when_not_required(self):
        self._require([])

        response = self._join(self.team)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(self._in_team(self.team))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.org_project))


@gating(GATE_GRANT_ORG_ADMIN, GATE_SHARE_TEAM_ADMIN)
class TestJoinOwnersTeamChecksEveryAction(TeamWiringTestCase):
    """Joining the Owners team makes two gated changes, ``grant-org-admin``
    and ``share-team-admin``."""

    def setUp(self):
        super().setUp()
        self.owner_team = Team.objects.get(
            organization=self.organization.user,
            name=f"{self.organization.user.username}#{Team.OWNER_TEAM_NAME}",
        )
        OwnerRole.add(self.owner_team, self.org_project)
        self.assertTrue(
            OwnerRole.has_role(
                get_perms(self.owner_team, self.org_project), self.org_project
            )
        )
        self.assertFalse(self._in_team(self.owner_team))

    def test_an_org_requiring_only_the_second_action_refuses_the_join(self):
        self._require([GATE_SHARE_TEAM_ADMIN])

        self.assert_enrol_required(self._join(self.owner_team))
        self.assertFalse(self._in_team(self.owner_team))
        self.assertFalse(self.organization.is_organization_owner(self.alice))

    def test_joining_the_owners_team_goes_through_when_not_required(self):
        self._require([])

        response = self._join(self.owner_team)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.organization.is_organization_owner(self.alice))


@gating(GATE_SHARE_TEAM_ADMIN)
class TestTeamHoldingsOwners(TeamWiringTestCase):
    """A team in ``denoinc`` manages a project ``otherinc`` owns, so joining
    or moving it hands out a role ``otherinc`` governs."""

    def setUp(self):
        super().setUp()
        self.other = self._other_org()
        self._project_create(
            {"name": "other project", "owner": _url("users", self.other.user.username)}
        )
        self.other_project = self.project
        self.assert_org_owns(self.other_project.organization, self.other)
        ShareTeamProject(self.team, self.other_project, ManagerRole.name).save()
        self._require([])

    def _move_to_a_third_org(self):
        home = self.organization
        self._org_create({"org": "thirdinc"})
        third, self.organization = self.organization, home
        view = TeamViewSet.as_view({"put": "update"})
        data = {"name": "dreamteam", "organization": third.user.username}
        request = self.factory.put(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        return third, view(request, pk=self.team.pk)

    def test_joining_is_refused_when_the_managed_projects_org_requires_it(self):
        self._require_of(self.other, [GATE_SHARE_TEAM_ADMIN])

        self.assert_enrol_required(self._join(self.team))
        self.assertFalse(self._in_team(self.team))

    def test_joining_goes_through_when_the_managed_projects_org_does_not(self):
        self._require_of(self.other, [])

        self.assertEqual(self._join(self.team).status_code, 201)
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.other_project))

    def test_moving_is_refused_when_the_managed_projects_org_requires_it(self):
        self._require_of(self.other, [GATE_SHARE_TEAM_ADMIN])

        _third, response = self._move_to_a_third_org()

        self.assert_enrol_required(response)
        self.team.refresh_from_db()
        self.assert_org_owns(self.team.organization)

    def test_moving_goes_through_when_the_managed_projects_org_does_not(self):
        self._require_of(self.other, [])

        third, response = self._move_to_a_third_org()

        self.assertEqual(response.status_code, 200, response.data)
        self.team.refresh_from_db()
        self.assert_org_owns(self.team.organization, third)


@gating(GATE_SHARE_TEAM_ADMIN)
class TestMembersTeamHoldingsOwners(OrgWiringTestCase):
    """``denoinc``'s members team manages a project ``otherinc`` owns, so
    adding a member hands out a role ``otherinc`` governs."""

    def setUp(self):
        super().setUp()
        self.alice = self._create_user("alice", "alice", create_profile=True)
        self.other = self._other_org()
        self._project_create(
            {"name": "other project", "owner": _url("users", self.other.user.username)}
        )
        self.other_project = self.project
        self.assert_org_owns(self.other_project.organization, self.other)
        ShareTeamProject(
            get_organization_members_team(self.organization),
            self.other_project,
            ManagerRole.name,
        ).save()
        self._require([])
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.other_project))

    def _add_member(self):
        view = OrganizationProfileViewSet.as_view({"post": "members"})
        request = self.factory.post(
            "/", data={"username": "alice"}, format="json", **self.extra
        )
        return view(request, user=self.organization.user.username)

    def test_adding_a_member_is_refused_when_a_managed_projects_org_requires_it(
        self,
    ):
        self._require_of(self.other, [GATE_SHARE_TEAM_ADMIN])

        self.assert_enrol_required(self._add_member())
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.other_project))

    def test_adding_a_member_goes_through_when_no_managed_projects_org_does(self):
        self._require_of(self.other, [])

        self.assertEqual(self._add_member().status_code, 201)
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.other_project))


@gating(GATE_GRANT_ORG_ADMIN, GATE_SHARE_TEAM_ADMIN)
class TestOwnersTeamHoldingsOwners(OrgWiringTestCase):
    """``denoinc``'s Owners team manages a project ``otherinc`` owns, so
    appointing an owner hands out a role ``otherinc`` governs."""

    def setUp(self):
        super().setUp()
        self.alice = self._create_user("alice", "alice", create_profile=True)
        self.other = self._other_org()
        self._project_create(
            {"name": "other project", "owner": _url("users", self.other.user.username)}
        )
        self.other_project = self.project
        self.assert_org_owns(self.other_project.organization, self.other)
        ShareTeamProject(
            get_or_create_organization_owners_team(self.organization),
            self.other_project,
            ManagerRole.name,
        ).save()
        self._require([])
        self.assertFalse(ManagerRole.user_has_role(self.alice, self.other_project))

    def _add_owner(self):
        view = OrganizationProfileViewSet.as_view({"post": "members"})
        request = self.factory.post(
            "/",
            data={"username": "alice", "role": OwnerRole.name},
            format="json",
            **self.extra,
        )
        return view(request, user=self.organization.user.username)

    def test_appointing_an_owner_is_refused_when_a_managed_projects_org_requires_it(
        self,
    ):
        self._require_of(self.other, ["all"])

        self.assert_enrol_required(self._add_owner())
        self.assertFalse(self.organization.is_organization_owner(self.alice))

    def test_appointing_an_owner_goes_through_when_no_managed_projects_org_does(
        self,
    ):
        self._require_of(self.other, [])

        self.assertEqual(self._add_owner().status_code, 201)
        self.assertTrue(self.organization.is_organization_owner(self.alice))
        self.assertTrue(ManagerRole.user_has_role(self.alice, self.other_project))


class OrgMembersWiringTestCase(OrgWiringTestCase):
    def setUp(self):
        super().setUp()
        self.alice = self._create_user("alice", "alice", create_profile=True)
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.organization))

    def _add_owner(self):
        view = OrganizationProfileViewSet.as_view({"post": "members"})
        request = self.factory.post(
            "/",
            data={"username": "alice", "role": OwnerRole.name},
            format="json",
            **self.extra,
        )
        return view(request, user=self.organization.user.username)


@gating(GATE_GRANT_ORG_ADMIN)
class TestOrgMembersOwners(OrgMembersWiringTestCase):
    def test_appointing_an_owner_is_refused_when_the_org_requires_it(self):
        self._require([GATE_GRANT_ORG_ADMIN])

        self.assert_enrol_required(self._add_owner())
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.organization))

    def test_appointing_an_owner_goes_through_when_not_required(self):
        self._require([])

        response = self._add_owner()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.organization))


@gating(GATE_GRANT_ORG_ADMIN, GATE_SHARE_TEAM_ADMIN)
class TestOrgMembersChecksEveryAction(OrgMembersWiringTestCase):
    """Adding an owner appoints an organisation owner and shares
    ``self.org_project`` with them as owner."""

    def setUp(self):
        super().setUp()
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.org_project))

    def test_an_org_requiring_only_the_second_action_refuses_the_owner(self):
        self._require([GATE_SHARE_TEAM_ADMIN])

        self.assert_enrol_required(self._add_owner())
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.organization))
        self.assertFalse(OwnerRole.user_has_role(self.alice, self.org_project))

    def test_adding_the_owner_goes_through_when_not_required(self):
        self._require([])

        response = self._add_owner()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.organization))
        self.assertTrue(OwnerRole.user_has_role(self.alice, self.org_project))


@gating(GATE_ROTATE_ORG_KEY)
@patch("onadata.libs.serializers.organization_serializer.rotate_key")
class TestRotateKeyOwners(OrgWiringTestCase):
    def setUp(self):
        super().setUp()
        self.kms_key = self._key("fake-key-id")

    def _key(self, key_id):
        return KMSKey.objects.create(
            key_id=key_id,
            description="Key-2025-04-25",
            public_key="fake-pub-key",
            content_type=ContentType.objects.get_for_model(OrganizationProfile),
            object_id=self.organization.pk,
            provider=KMSKey.KMSProvider.AWS,
        )

    def _rotate(self):
        view = OrganizationProfileViewSet.as_view({"post": "rotate_key"})
        request = self.factory.post("/", data={"id": self.kms_key.id}, **self.extra)
        return view(request, user=self.organization.user.username)

    def test_rotating_the_key_is_refused_when_the_org_requires_it(self, rotate):
        self._require([GATE_ROTATE_ORG_KEY])

        self.assert_enrol_required(self._rotate())
        rotate.assert_not_called()

    def test_rotating_the_key_goes_through_when_not_required(self, rotate):
        rotate.return_value = self._key("new-key")
        self._require([])

        response = self._rotate()

        self.assertEqual(response.status_code, 200, response.data)
        rotate.assert_called_once()


@gating(GATE_TRANSFER_PROJECT)
class TestFormMoveOwners(OrgWiringTestCase):
    def setUp(self):
        super().setUp()
        self._project_create({"name": "personal"})
        self.personal_project = self.project
        self.assertEqual(self.personal_project.organization, self.user)

    def _move(self, project):
        view = ProjectViewSet.as_view({"post": "forms"})
        request = self.factory.post("/", data={"formid": self.xform.pk}, **self.extra)
        return view(request, pk=project.pk)

    def _project_of_the_form(self):
        self.xform.refresh_from_db()
        return self.xform.project

    def _personal_form(self):
        self._publish_xls_form_to_project()
        self.assertEqual(self.xform.user, self.user)
        self.assertEqual(self._project_of_the_form(), self.personal_project)

    def _org_form(self):
        self.project = self.org_project
        self._publish_xls_form_to_project()
        self.assert_org_owns(self.xform.user)

    def test_moving_a_form_in_is_refused_when_the_org_requires_it(self):
        self._personal_form()
        self._require([GATE_TRANSFER_PROJECT])

        self.assert_enrol_required(self._move(self.org_project))
        self.assertEqual(self._project_of_the_form(), self.personal_project)

    def test_moving_a_form_in_goes_through_when_not_required(self):
        self._personal_form()
        self._require([])

        response = self._move(self.org_project)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self._project_of_the_form(), self.org_project)

    def test_moving_an_org_form_out_is_refused_when_the_org_requires_it(self):
        self._org_form()
        self._require([GATE_TRANSFER_PROJECT])

        self.assert_enrol_required(self._move(self.personal_project))
        self.assertEqual(self._project_of_the_form(), self.org_project)
        self._require([])
        self.assertEqual(self._move(self.personal_project).status_code, 201)
        self.assertEqual(self._project_of_the_form(), self.personal_project)

    @gating(GATE_TRANSFER_PROJECT, GATE_SHARE_FORM_ADMIN)
    def test_an_org_requiring_only_the_covered_action_refuses_the_move(self):
        alice = self._move_appointing_an_admin()
        self._require([GATE_SHARE_FORM_ADMIN])

        self.assert_enrol_required(self._move(self.org_project))
        self.assertEqual(self._project_of_the_form(), self.personal_project)
        self.assertFalse(OwnerRole.user_has_role(alice, self.xform))

    @gating(GATE_TRANSFER_PROJECT, GATE_SHARE_FORM_ADMIN)
    def test_a_move_appointing_an_admin_goes_through_when_not_required(self):
        alice = self._move_appointing_an_admin()
        self._require([])

        response = self._move(self.org_project)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self._project_of_the_form(), self.org_project)
        self.assertTrue(OwnerRole.user_has_role(alice, self.xform))

    def _move_appointing_an_admin(self):
        """A personal form whose meta permissions make an editor of
        ``self.org_project`` its owner once moved there."""
        self._personal_form()
        self._set_meta_perms(EDITOR_BECOMES_OWNER)
        alice = self._create_user("alice", "alice", create_profile=True)
        EditorRole.add(alice, self.org_project)
        self.assertTrue(move_appoints_admins(self.xform, self.org_project))
        self.assertFalse(OwnerRole.user_has_role(alice, self.xform))
        return alice

    def _set_meta_perms(self, value):
        MetaData.xform_meta_permission(self.xform, data_value=value)
        self.assertEqual(MetaData.xform_meta_permission(self.xform).data_value, value)


@gating(
    GATE_INVITE_PROJECT_ADMIN,
    PROJECT_INVITATION_URL={"*": "https://example.com/register"},
)
@patch(
    "onadata.libs.serializers.project_invitation_serializer"
    ".send_project_invitation_email_async.delay"
)
class TestProjectInvitationOwners(OrgWiringTestCase):
    def _invite(self, method, payload):
        view = ProjectViewSet.as_view({method: "invitations"})
        request = getattr(self.factory, method)(
            "/",
            data=json.dumps(payload),
            content_type="application/json",
            **self.extra,
        )
        return view(request, pk=self.org_project.pk)

    def _create(self):
        return self._invite(
            "post", {"email": "jane@example.com", "role": OwnerRole.name}
        )

    def _raise_to_owner(self):
        invitation = self.org_project.invitations.create(
            email="jane@example.com",
            role=EditorRole.name,
            status=ProjectInvitation.Status.PENDING,
        )
        response = self._invite(
            "put",
            {
                "invitation_id": invitation.pk,
                "email": invitation.email,
                "role": OwnerRole.name,
            },
        )
        invitation.refresh_from_db()
        return response, invitation

    def test_inviting_an_owner_is_refused_when_the_org_requires_it(self, _send):
        self._require([GATE_INVITE_PROJECT_ADMIN])

        self.assert_enrol_required(self._create())
        self.assertFalse(self.org_project.invitations.exists())

    def test_inviting_an_owner_goes_through_when_not_required(self, _send):
        self._require([])

        response = self._create()

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.org_project.invitations.get().role, OwnerRole.name)

    def test_raising_an_invitation_is_refused_when_the_org_requires_it(self, _send):
        self._require([GATE_INVITE_PROJECT_ADMIN])

        response, invitation = self._raise_to_owner()

        self.assert_enrol_required(response)
        self.assertEqual(invitation.role, EditorRole.name)

    def test_raising_an_invitation_goes_through_when_not_required(self, _send):
        self._require([])

        response, invitation = self._raise_to_owner()

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(invitation.role, OwnerRole.name)


@gating(GATE_PUBLISH_DATA)
class TestFormPagesOwners(OrgWiringTestCase):
    """The form edit page's ``toggle_shared`` and the permissions page's
    public link."""

    def setUp(self):
        super().setUp()
        self._publish_xls_form_to_project()
        self.assert_org_owns(self.xform.user)
        self.assertTrue(OwnerRole.user_has_role(self.user, self.xform))
        self.assertFalse(self.xform.shared)
        self.assertFalse(MetaData.public_link(self.xform))

    def _page_post(self, page, data, xform=None):
        xform = xform or self.xform
        url = reverse(
            page,
            kwargs={"username": xform.user.username, "id_string": xform.id_string},
        )
        return self.client.post(url, data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def _share_form(self, xform=None):
        return self._page_post(edit, {"toggle_shared": "form"}, xform)

    def _turn_link_on(self):
        return self._page_post(set_perm, {"perm_type": "link", "for_user": "all"})

    def _shared(self, xform=None):
        return XForm.objects.get(pk=(xform or self.xform).pk).shared

    def test_sharing_a_form_is_refused_when_the_org_requires_it(self):
        self._require([GATE_PUBLISH_DATA])

        self.assert_page_enrol_required(self._share_form())
        self.assertFalse(self._shared())

    def test_sharing_a_form_goes_through_when_not_required(self):
        self._require([])

        response = self._share_form()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(self._shared())

    def test_sharing_counts_the_forms_project_org_for_a_personal_form(self):
        xform = self._personal_form_in_org_project()
        self.assertFalse(xform.shared)
        self._require([GATE_PUBLISH_DATA])

        self.assert_page_enrol_required(self._share_form(xform))
        self.assertFalse(self._shared(xform))
        self._require([])
        self.assertEqual(self._share_form(xform).status_code, 200)
        self.assertTrue(self._shared(xform))

    def test_turning_on_the_public_link_is_refused_when_the_org_requires_it(self):
        self._require([GATE_PUBLISH_DATA])

        self.assert_page_enrol_required(self._turn_link_on())
        self.assertFalse(MetaData.public_link(self.xform))

    def test_turning_on_the_public_link_goes_through_when_not_required(self):
        self._require([])

        response = self._turn_link_on()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(MetaData.public_link(self.xform))
