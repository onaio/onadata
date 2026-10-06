import json

from guardian.shortcuts import assign_perm, get_perms

from onadata.apps.api import tools
from onadata.apps.api.models import Team
from onadata.apps.api.tests.viewsets.test_abstract_viewset import TestAbstractViewSet
from onadata.apps.api.tools import add_user_to_team
from onadata.apps.api.tools import (
    get_or_create_organization_owners_team,
    get_organization_members_team,
)
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.api.viewsets.organization_profile_viewset import (
    OrganizationProfileViewSet,
)
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.team_viewset import TeamViewSet
from onadata.apps.logger.models import Project
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import OwnerRole, ReadOnlyRoleNoDownload
from onadata.libs.permissions import (
    ReadOnlyRole,
    EditorRole,
    DataEntryOnlyRole,
    EditorMinorRole,
    ManagerRole,
)
from onadata.libs.serializers.metadata_serializer import MetaDataSerializer
from onadata.libs.permissions import get_role
from onadata.libs.utils.common_tags import XFORM_META_PERMS


class TestTeamViewSet(TestAbstractViewSet, TestBase):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = TeamViewSet.as_view({"get": "list", "post": "create"})

    def test_teams_list(self):
        self._team_create()

        # access the url with an unauthorised user
        request = self.factory.get("/")
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        # access the url with an authorised user
        request = self.factory.get("/", **self.extra)
        response = self.view(request)
        owner_team = {
            "teamid": self.owner_team.pk,
            "url": "http://testserver/api/v1/teams/%s" % self.owner_team.pk,
            "name": "Owners",
            "organization": "denoinc",
            "projects": [],
            "users": [
                {
                    "username": "bob",
                    "first_name": "Bob",
                    "last_name": "erama",
                    "id": self.user.pk,
                }
            ],
        }
        memberteam = Team.objects.get(
            organization=self.organization.user,
            name="%s#%s" % (self.organization.user.username, "members"),
        )
        member_team = {
            "teamid": memberteam.pk,
            "url": "http://testserver/api/v1/teams/%s" % memberteam.pk,
            "name": "members",
            "organization": "denoinc",
            "projects": [],
            "users": [
                {
                    "id": self.organization.user.pk,
                    "username": "denoinc",
                    "first_name": "Dennis",
                    "last_name": "",
                }
            ],
        }
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [owner_team, member_team, self.team_data])

    def test_teams_get(self):
        self._team_create()
        view = TeamViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=self.team.pk)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.team_data)

    def test_teams_create(self):
        self._team_create()

    def test_add_user_to_team(self):
        self._team_create()
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

        view = TeamViewSet.as_view({"post": "members"})

        data = {"username": self.user.username}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [self.user.username])
        self.assertIn(self.team.group_ptr, self.user.groups.all())

    def test_add_user_to_team_missing_username(self):
        self._team_create()
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

        view = TeamViewSet.as_view({"post": "members"})

        data = {}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"username": ["This field is required."]})
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

    def test_add_user_to_team_user_does_not_exist(self):
        self._team_create()
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

        view = TeamViewSet.as_view({"post": "members"})

        data = {"username": "aboy"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"username": ["User `aboy` does not exist."]})
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

    def test_remove_user_from_team(self):
        self._team_create()
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

        view = TeamViewSet.as_view({"post": "members", "delete": "members"})

        data = {"username": self.user.username}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [self.user.username])
        self.assertIn(self.team.group_ptr, self.user.groups.all())

        request = self.factory.delete(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [])
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

    def test_team_share(self):
        self._team_create()
        self._publish_xls_form_to_project()
        chuck_data = {"username": "chuck", "email": "chuck@localhost.com"}
        chuck_profile = self._create_user_profile(chuck_data)
        user_chuck = chuck_profile.user

        tools.add_user_to_team(self.team, user_chuck)
        view = TeamViewSet.as_view({"post": "share"})

        ROLES = [ReadOnlyRole, EditorRole]
        ROLES_SET = [ReadOnlyRoleNoDownload, DataEntryOnlyRole]

        for role_class, role_class_set_for_user in zip(ROLES, ROLES_SET):
            self.assertFalse(role_class.user_has_role(user_chuck, self.project))
            self.assertFalse(
                role_class_set_for_user.user_has_role(user_chuck, self.project)
            )
            data = {"role": role_class.name, "project": self.project.pk}
            request = self.factory.post(
                "/",
                data=json.dumps(data),
                content_type="application/json",
                **self.extra,
            )
            response = view(request, pk=self.team.pk)

            self.assertEqual(response.status_code, 204)

            self.assertTrue(role_class.user_has_role(user_chuck, self.project))
            self.assertTrue(
                role_class_set_for_user.user_has_role(user_chuck, self.xform)
            )
        metadata = self.xform.metadata_set.get(data_type="xform_meta_perms")
        serializer = MetaDataSerializer(
            metadata,
            data={
                "data_value": "editor|dataentry|readonly",
                "data_type": "xform_meta_perms",
                "xform": self.xform.id,
            },
        )

        if serializer.is_valid():
            serializer.save()

        for role_class in ROLES:
            data = {"role": role_class.name, "project": self.project.pk}
            request = self.factory.post(
                "/",
                data=json.dumps(data),
                content_type="application/json",
                **self.extra,
            )
            response = view(request, pk=self.team.pk)

            self.assertEqual(response.status_code, 204)

            self.assertTrue(role_class.user_has_role(user_chuck, self.project))
            self.assertTrue(role_class.user_has_role(user_chuck, self.xform))

    def test_remove_team_from_project(self):
        self._team_create()
        self._publish_xls_form_to_project()
        chuck_data = {"username": "chuck", "email": "chuck@localhost.com"}
        chuck_profile = self._create_user_profile(chuck_data)
        user_chuck = chuck_profile.user

        tools.add_user_to_team(self.team, user_chuck)
        view = TeamViewSet.as_view({"post": "share"})

        self.assertFalse(EditorRole.user_has_role(user_chuck, self.project))
        data = {"role": EditorRole.name, "project": self.project.pk}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(EditorRole.user_has_role(user_chuck, self.project))

        data = {"role": EditorRole.name, "project": self.project.pk, "remove": True}

        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(EditorRole.user_has_role(user_chuck, self.project))
        self.assertFalse(EditorRole.user_has_role(user_chuck, self.xform))

    def test_get_all_team(self):
        self._team_create()
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

        view = TeamViewSet.as_view({"get": "list", "post": "members"})

        data = {"username": self.user.username}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [self.user.username])
        self.assertIn(self.team.group_ptr, self.user.groups.all())

        get_data = {"org": "denoinc"}
        request = self.factory.get("/", data=get_data, **self.extra)
        response = view(request)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

    def test_team_share_members(self):
        self._team_create()
        project = Project.objects.create(
            name="Test Project",
            organization=self.team.organization,
            created_by=self.user,
            metadata="{}",
        )

        view = TeamViewSet.as_view({"get": "list", "post": "share"})

        get_data = {"org": "denoinc"}
        request = self.factory.get("/", data=get_data, **self.extra)
        response = view(request)
        # get the members team
        self.assertEqual(response.data[1].get("name"), "members")
        teamid = response.data[1].get("teamid")

        chuck_data = {"username": "chuck", "email": "chuck@localhost.com"}
        chuck_profile = self._create_user_profile(chuck_data)
        user_chuck = chuck_profile.user

        self.team = Team.objects.get(pk=teamid)
        tools.add_user_to_team(self.team, user_chuck)

        self.assertFalse(EditorRole.user_has_role(user_chuck, project))
        post_data = {
            "role": EditorRole.name,
            "project": project.pk,
            "remove": False,
            "org": "denoinc",
        }
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(EditorRole.user_has_role(user_chuck, project))

        view = ProjectViewSet.as_view({"get": "retrieve"})
        request = self.factory.get("/", **self.extra)
        response = view(request, pk=project.pk)
        self.assertNotEqual(response.get("Cache-Control"), None)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.data.get("users")), 2)

    def test_add_user_to_team_no_perms(self):
        self._team_create()

        view = TeamViewSet.as_view(
            {"post": "members", "get": "retrieve", "delete": "members"}
        )

        # add bob
        data = {"username": self.user.username}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [self.user.username])

        # create user alice
        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)

        # add alice to the team
        data = {"username": alice_profile.user.username}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            sorted(response.data),
            sorted([self.user.username, alice_profile.user.username]),
        )

        # check that alice is able to access the team
        alice_extra = {"HTTP_AUTHORIZATION": "Token %s" % alice_profile.user.auth_token}
        request = self.factory.get("/", content_type="application/json", **alice_extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 200)

        # remove alice from the team
        data = {"username": alice_profile.user.username}
        request = self.factory.delete(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [self.user.username])

        # check alice cant access the team
        request = self.factory.get("/", content_type="application/json", **alice_extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 404)

    def test_non_owners_should_be_able_to_change_member_permissions(self):
        self._org_create()
        # an organization project, so every organization owner holds the
        # owner role on it and may set team permissions
        self._project_create(
            {
                "owner": f"http://testserver/api/v1/users/{self.organization.user.username}"
            }
        )

        chuck_data = {"username": "chuck", "email": "chuck@localhost.com"}
        chuck_profile = self._create_user_profile(chuck_data)

        view = OrganizationProfileViewSet.as_view({"post": "members"})

        data = {"username": chuck_profile.user.username, "role": OwnerRole.name}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user=self.organization.user.username)

        self.assertEqual(response.status_code, 201)

        owners_team = get_or_create_organization_owners_team(self.organization)
        self.assertIn(chuck_profile.user, owners_team.user_set.all())

        alice_data = {"username": "alice", "email": "alice@localhost.com"}
        alice_profile = self._create_user_profile(alice_data)

        data = {"username": alice_profile.user.username}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )

        response = view(request, user=self.organization.user.username)

        self.assertEqual(response.status_code, 201)

        member_team = get_organization_members_team(self.organization)
        self.assertIn(alice_profile.user, member_team.user_set.all())

        view = TeamViewSet.as_view({"post": "share"})

        post_data = {
            "role": EditorRole.name,
            "project": self.project.pk,
            "org": self.organization.user.username,
        }
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=member_team.pk)

        self.assertEqual(response.status_code, 204)

        post_data = {
            "role": ReadOnlyRole.name,
            "project": self.project.pk,
            "org": self.organization.user.username,
        }

        extra = {"HTTP_AUTHORIZATION": "Token %s" % chuck_profile.user.auth_token}
        request = self.factory.post("/", data=post_data, **extra)
        response = view(request, pk=member_team.pk)
        self.assertEqual(response.status_code, 204)

    def test_team_members_meta_perms_restrictions(self):
        self._team_create()
        self._publish_xls_form_to_project()
        user_alice = self._create_user("alice", "alice")

        members_team = Team.objects.get(
            name="%s#%s" % (self.organization.user.username, "members")
        )

        # add alice to members team
        add_user_to_team(members_team, user_alice)

        # confirm that the team and members have no permissions on form
        self.assertFalse(get_perms(members_team, self.xform))
        self.assertFalse(get_perms(user_alice, self.xform))

        # share project to team
        view = TeamViewSet.as_view({"get": "list", "post": "share"})

        post_data = {
            "role": EditorRole.name,
            "project": self.project.pk,
            "remove": False,
        }
        request = self.factory.post("/", data=post_data, **self.extra)
        response = view(request, pk=members_team.pk)
        self.assertEqual(response.status_code, 204)

        # team members should have editor permissions now
        alice_perms = get_perms(user_alice, self.xform)
        alice_role = get_role(alice_perms, self.xform)
        self.assertEqual(EditorRole.name, alice_role)
        self.assertTrue(EditorRole.user_has_role(user_alice, self.xform))

        # change meta permissions
        meta_view = MetaDataViewSet.as_view({"post": "create", "put": "update"})

        data = {
            "data_type": XFORM_META_PERMS,
            "data_value": "editor-minor|dataentry|readonly-no-download",
            "xform": self.xform.pk,
        }

        request = self.factory.post("/", data, **self.extra)
        response = meta_view(request)
        self.assertEqual(response.status_code, 201)

        # members should now have EditorMinor role
        self.assertTrue(EditorMinorRole.user_has_role(user_alice, self.xform))

    def test_create_team_requires_organization_admin(self):
        """Only owners and managers of an organization can create its teams."""
        self._org_create()
        alice = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        ).user
        alice_extra = {"HTTP_AUTHORIZATION": f"Token {alice.auth_token}"}
        org_username = self.organization.user.username
        team_name = f"{org_username}#xOwners"
        data = {"name": "xOwners", "organization": org_username}

        # an account with no role in the organization
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **alice_extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Team.objects.filter(name=team_name).exists())

        # a member of the organization without an administrative role
        tools.add_user_to_organization(self.organization, alice, EditorRole.name)
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **alice_extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Team.objects.filter(name=team_name).exists())

        # an organization manager
        tools.add_user_to_organization(self.organization, alice, ManagerRole.name)
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **alice_extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        team = Team.objects.get(name=team_name)
        self.assertEqual(team.created_by, alice)

        # and the manager can then manage that team's membership
        view = TeamViewSet.as_view({"post": "members"})
        request = self.factory.post(
            "/",
            data=json.dumps({"username": "alice"}),
            content_type="application/json",
            **alice_extra,
        )
        response = view(request, pk=team.pk)
        self.assertEqual(response.status_code, 201)
        self.assertIn(team.group_ptr, alice.groups.all())

    def test_move_team_requires_admin_of_target_organization(self):
        """A team cannot be moved into an organization the caller does not manage."""
        self._team_create()
        alice = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        ).user
        self._create_organization(
            username="aliceinc", name="Alice Inc", created_by=alice
        )

        view = TeamViewSet.as_view({"put": "update"})
        data = {"name": "dreamteam", "organization": "aliceinc"}
        request = self.factory.put(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 403)
        self.team.refresh_from_db()
        self.assertEqual(self.team.organization, self.organization.user)

    def test_move_team_requires_admin_of_current_organization(self):
        """A former team creator cannot move the team into another organization."""
        self._org_create()
        alice = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        ).user
        alice_extra = {"HTTP_AUTHORIZATION": f"Token {alice.auth_token}"}

        # alice, while a manager of denoinc, creates a team there
        tools.add_user_to_organization(self.organization, alice, ManagerRole.name)
        data = {"name": "fieldteam", "organization": self.organization.user.username}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **alice_extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        team = Team.objects.get(pk=response.data["teamid"])

        # alice is then removed from denoinc and administers her own organization
        tools.remove_user_from_organization(self.organization, alice)
        self._create_organization(
            username="aliceinc", name="Alice Inc", created_by=alice
        )

        view = TeamViewSet.as_view({"put": "update"})
        data = {"name": "fieldteam", "organization": "aliceinc"}
        request = self.factory.put(
            "/", data=json.dumps(data), content_type="application/json", **alice_extra
        )
        response = view(request, pk=team.pk)

        self.assertEqual(response.status_code, 403)
        team.refresh_from_db()
        self.assertEqual(team.organization, self.organization.user)

    def test_rename_team_requires_admin_of_organization(self):
        """A former team creator cannot rename the team."""
        self._org_create()
        alice = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        ).user
        alice_extra = {"HTTP_AUTHORIZATION": f"Token {alice.auth_token}"}

        # alice, while a manager of denoinc, creates a team there
        tools.add_user_to_organization(self.organization, alice, ManagerRole.name)
        data = {"name": "fieldteam", "organization": self.organization.user.username}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **alice_extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        team = Team.objects.get(pk=response.data["teamid"])

        # alice is then removed from denoinc
        tools.remove_user_from_organization(self.organization, alice)

        # a partial update names no organization, so only the team's current
        # organization can authorize it
        view = TeamViewSet.as_view({"patch": "partial_update"})
        request = self.factory.patch(
            "/",
            data=json.dumps({"name": "changed"}),
            content_type="application/json",
            **alice_extra,
        )
        response = view(request, pk=team.pk)

        self.assertEqual(response.status_code, 403)
        team.refresh_from_db()
        self.assertEqual(team.name, "denoinc#fieldteam")

    def test_delete_team_requires_admin_of_organization(self):
        """A former team creator cannot delete the team."""
        self._org_create()
        alice = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        ).user
        alice_extra = {"HTTP_AUTHORIZATION": f"Token {alice.auth_token}"}

        # alice, while a manager of denoinc, creates a team there
        tools.add_user_to_organization(self.organization, alice, ManagerRole.name)
        data = {"name": "fieldteam", "organization": self.organization.user.username}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **alice_extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        team = Team.objects.get(pk=response.data["teamid"])

        # alice is then removed from denoinc
        tools.remove_user_from_organization(self.organization, alice)

        view = TeamViewSet.as_view({"delete": "destroy"})
        request = self.factory.delete("/", **alice_extra)
        response = view(request, pk=team.pk)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Team.objects.filter(pk=team.pk).exists())

        # an owner of the organization can delete it
        request = self.factory.delete("/", **self.extra)
        response = view(request, pk=team.pk)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Team.objects.filter(pk=team.pk).exists())

    def test_owners_lookalike_team_grants_no_organization_perms(self):
        """Membership of a team merely named like Owners grants nothing extra."""
        self._org_create()
        alice = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        ).user
        alice_extra = {"HTTP_AUTHORIZATION": f"Token {alice.auth_token}"}
        owners_team = Team.objects.get(
            organization=self.organization.user, name="denoinc#Owners"
        )
        members_team = Team.objects.get(
            organization=self.organization.user, name="denoinc#members"
        )

        data = {"name": "Data Owners", "organization": self.organization.user.username}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **self.extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        team = Team.objects.get(pk=response.data["teamid"])

        view = TeamViewSet.as_view({"post": "members"})
        request = self.factory.post(
            "/",
            data=json.dumps({"username": "alice"}),
            content_type="application/json",
            **self.extra,
        )
        response = view(request, pk=team.pk)
        self.assertEqual(response.status_code, 201)
        self.assertIn(team.group_ptr, alice.groups.all())

        self.assertEqual(get_perms(alice, owners_team), [])
        self.assertEqual(get_perms(alice, members_team), [])
        self.assertFalse(self.organization.is_organization_owner(alice))

        # the look-alike team is no stepping stone into the real Owners team
        request = self.factory.post(
            "/",
            data=json.dumps({"username": "alice"}),
            content_type="application/json",
            **alice_extra,
        )
        response = view(request, pk=owners_team.pk)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(owners_team.group_ptr, alice.groups.all())
        self.assertFalse(self.organization.is_organization_owner(alice))

    def test_share_requires_project_owner_or_manager(self):
        """Only owners and managers of a project can grant team roles on it."""
        self._team_create()
        self._publish_xls_form_to_project()
        chuck = self._create_user_profile(
            {"username": "chuck", "email": "chuck@localhost.com"}
        ).user
        chuck_extra = {"HTTP_AUTHORIZATION": f"Token {chuck.auth_token}"}

        # chuck administers a different organization and one of its teams
        chuck_org = self._create_organization(
            username="chuckinc", name="Chuck Inc", created_by=chuck
        )
        chuck_org.created_by = chuck
        chuck_org.save()
        data = {"name": "raiders", "organization": "chuckinc"}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **chuck_extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        chuck_team = Team.objects.get(pk=response.data["teamid"])
        view = TeamViewSet.as_view({"post": "share"})

        for extra in [{}, {"remove": True}]:
            data = {"role": OwnerRole.name, "project": self.project.pk, **extra}
            request = self.factory.post(
                "/",
                data=json.dumps(data),
                content_type="application/json",
                **chuck_extra,
            )
            response = view(request, pk=chuck_team.pk)
            self.assertEqual(response.status_code, 403)

        self.assertEqual(get_perms(chuck_team, self.project), [])
        self.assertEqual(get_perms(chuck_team, self.xform), [])

        # an editor on the project still cannot grant team roles
        EditorRole.add(chuck, self.project)
        data = {"role": OwnerRole.name, "project": self.project.pk}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **chuck_extra
        )
        response = view(request, pk=chuck_team.pk)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(get_perms(chuck_team, self.project), [])

        # a manager of the project can
        ManagerRole.add(chuck, self.project)
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **chuck_extra
        )
        response = view(request, pk=chuck_team.pk)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(
            OwnerRole.has_role(get_perms(chuck_team, self.project), self.project)
        )

        # and can revoke again
        data["remove"] = True
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **chuck_extra
        )
        response = view(request, pk=chuck_team.pk)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(get_perms(chuck_team, self.project), [])

    def test_team_membership_changes_require_organization_admin(self):
        """A team-level permission alone does not allow changing membership."""
        self._team_create()
        alice = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        ).user
        alice_extra = {"HTTP_AUTHORIZATION": f"Token {alice.auth_token}"}
        for perm in ["view_team", "add_team", "delete_team"]:
            assign_perm(perm, alice, self.team)
        tools.add_user_to_team(self.team, self.user)
        view = TeamViewSet.as_view({"post": "members", "delete": "members"})

        request = self.factory.post(
            "/",
            data=json.dumps({"username": "alice"}),
            content_type="application/json",
            **alice_extra,
        )

        response = view(request, pk=self.team.pk)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(self.team.group_ptr, alice.groups.all())

        request = self.factory.delete(
            "/",
            data=json.dumps({"username": self.user.username}),
            content_type="application/json",
            **alice_extra,
        )
        response = view(request, pk=self.team.pk)
        self.assertEqual(response.status_code, 403)
        self.assertIn(self.team.group_ptr, self.user.groups.all())

    def test_team_routes_cannot_take_over_organization(self):
        """An outsider cannot chain the team routes into organization ownership."""
        self._org_create()
        project = Project.objects.create(
            name="Org Project",
            organization=self.organization.user,
            created_by=self.user,
            metadata="{}",
        )
        alice = self._create_user_profile(
            {"username": "alice", "email": "alice@localhost.com"}
        ).user
        alice_extra = {"HTTP_AUTHORIZATION": f"Token {alice.auth_token}"}
        owners_team = Team.objects.get(
            organization=self.organization.user, name="denoinc#Owners"
        )

        # create a look-alike Owners team inside the victim organization
        data = {"name": "xOwners", "organization": self.organization.user.username}
        request = self.factory.post(
            "/", data=json.dumps(data), content_type="application/json", **alice_extra
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Team.objects.filter(name="denoinc#xOwners").exists())

        # or join the real Owners team directly
        view = TeamViewSet.as_view({"post": "members"})
        request = self.factory.post(
            "/",
            data=json.dumps({"username": "alice"}),
            content_type="application/json",
            **alice_extra,
        )
        response = view(request, pk=owners_team.pk)
        self.assertEqual(response.status_code, 404)

        self.assertNotIn(owners_team.group_ptr, alice.groups.all())
        self.assertFalse(self.organization.is_organization_owner(alice))
        self.assertEqual(get_perms(alice, project), [])
