import json

from guardian.shortcuts import get_perms

from onadata.apps.api import tools
from onadata.apps.api.models import Team
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.tools import add_user_to_team
from onadata.apps.api.tools import get_or_create_organization_owners_team, \
    get_organization_members_team
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.api.viewsets.organization_profile_viewset import \
    OrganizationProfileViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.team_viewset import TeamViewSet
from onadata.apps.logger.models import Project
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.permissions import OwnerRole
from onadata.libs.permissions import ReadOnlyRole, EditorRole, EditorMinorRole
from onadata.libs.permissions import get_role
from onadata.libs.utils.common_tags import XFORM_META_PERMS


class TestTeamViewSet(TestAbstractViewSet, TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = TeamViewSet.as_view({
            'get': 'list',
            'post': 'create'
        })

    def test_teams_list(self):
        self._team_create()

        # access the url with an unauthorised user
        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        # access the url with an authorised user
        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        owner_team = {
            'teamid': self.owner_team.pk,
            'url':
            'http://testserver/api/v1/teams/%s' % self.owner_team.pk,
            'name': u'Owners',
            'organization': 'denoinc',
            'projects': [],
            'users': [{'username': u'bob',
                       'first_name': u'Bob',
                       'last_name': u'erama',
                       'id': self.user.pk}
                      ]
        }
        memberteam = Team.objects.get(
            organization=self.organization.user,
            name='%s#%s' % (self.organization.user.username, "members"))
        member_team = {
            'teamid': memberteam.pk,
            'url': 'http://testserver/api/v1/teams/%s' % memberteam.pk,
            'name': u'members',
            'organization': u'denoinc',
            'projects': [],
            'users': [{'id': self.organization.user.pk,
                       'username': u'denoinc',
                       'first_name': u'Dennis',
                       'last_name': u''}]
        }
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [owner_team, member_team,
                                         self.team_data])

    def test_teams_get(self):
        self._team_create()
        view = TeamViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.team.pk)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.team_data)

    def test_teams_create(self):
        self._team_create()

    def test_add_user_to_team(self):
        self._team_create()
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

        view = TeamViewSet.as_view({
            'post': 'members'
        })

        data = {'username': self.user.username}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data,
                         [self.user.username])
        self.assertIn(self.team.group_ptr, self.user.groups.all())

    def test_add_user_to_team_missing_username(self):
        self._team_create()
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

        view = TeamViewSet.as_view({
            'post': 'members'
        })

        data = {}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data,
                         {'username': [u'This field is required.']})
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

    def test_add_user_to_team_user_does_not_exist(self):
        self._team_create()
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

        view = TeamViewSet.as_view({
            'post': 'members'
        })

        data = {'username': 'aboy'}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data,
                         {'username': [u'User `aboy` does not exist.']})
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

    def test_remove_user_from_team(self):
        self._team_create()
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

        view = TeamViewSet.as_view({
            'post': 'members',
            'delete': 'members'
        })

        data = {'username': self.user.username}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data,
                         [self.user.username])
        self.assertIn(self.team.group_ptr, self.user.groups.all())

        request = self.factory.delete(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data,
                         [])
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

    def test_team_share(self):
        self._team_create()
        self._publish_xls_form_to_project()
        chuck_data = {'username': 'chuck', 'email': 'chuck@localhost.com'}
        chuck_profile = self._create_user_profile(chuck_data)
        user_chuck = chuck_profile.user

        tools.add_user_to_team(self.team, user_chuck)
        view = TeamViewSet.as_view({
            'post': 'share'})

        ROLES = [ReadOnlyRole,
                 EditorRole]

        for role_class in ROLES:
            self.assertFalse(role_class.user_has_role(user_chuck,
                                                      self.project))
            data = {'role': role_class.name,
                    'project': self.project.pk}
            request = self.factory.post(
                '/', data=json.dumps(data),
                content_type="application/json", **self.extra)
            response = view(request, pk=self.team.pk)

            self.assertEqual(response.status_code, 204)

            self.assertTrue(role_class.user_has_role(user_chuck, self.project))
            self.assertTrue(role_class.user_has_role(user_chuck, self.xform))

    def test_remove_team_from_project(self):
        self._team_create()
        self._publish_xls_form_to_project()
        chuck_data = {'username': 'chuck', 'email': 'chuck@localhost.com'}
        chuck_profile = self._create_user_profile(chuck_data)
        user_chuck = chuck_profile.user

        tools.add_user_to_team(self.team, user_chuck)
        view = TeamViewSet.as_view({
            'post': 'share'})

        self.assertFalse(EditorRole.user_has_role(user_chuck,
                                                  self.project))
        data = {'role': EditorRole.name,
                'project': self.project.pk}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(EditorRole.user_has_role(user_chuck, self.project))

        data = {'role': EditorRole.name,
                'project': self.project.pk,
                'remove': True}

        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(EditorRole.user_has_role(user_chuck, self.project))
        self.assertFalse(EditorRole.user_has_role(user_chuck, self.xform))

    def test_get_all_team(self):
        self._team_create()
        self.assertNotIn(self.team.group_ptr, self.user.groups.all())

        view = TeamViewSet.as_view({
            'get': 'list',
            'post': 'members'
        })

        data = {'username': self.user.username}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data,
                         [self.user.username])
        self.assertIn(self.team.group_ptr, self.user.groups.all())

        get_data = {'org': 'denoinc'}
        request = self.factory.get('/', data=get_data, **self.extra)
        response = view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

    def test_team_share_members(self):
        self._team_create()
        project = Project.objects.create(name="Test Project",
                                         organization=self.team.organization,
                                         created_by=self.user,
                                         metadata='{}')

        view = TeamViewSet.as_view({
            'get': 'list',
            'post': 'share'})

        get_data = {'org': 'denoinc'}
        request = self.factory.get('/', data=get_data, **self.extra)
        response = view(request)
        # get the members team
        self.assertEquals(response.data[1].get('name'), 'members')
        teamid = response.data[1].get('teamid')

        chuck_data = {'username': 'chuck', 'email': 'chuck@localhost.com'}
        chuck_profile = self._create_user_profile(chuck_data)
        user_chuck = chuck_profile.user

        self.team = Team.objects.get(pk=teamid)
        tools.add_user_to_team(self.team, user_chuck)

        self.assertFalse(EditorRole.user_has_role(user_chuck,
                                                  project))
        post_data = {'role': EditorRole.name,
                     'project': project.pk,
                     'remove': False,
                     'org': 'denoinc'}
        request = self.factory.post(
            '/', data=post_data, **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(EditorRole.user_has_role(user_chuck, project))

        view = ProjectViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=project.pk)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.data.get('users')), 2)

    def test_add_user_to_team_no_perms(self):
        self._team_create()

        view = TeamViewSet.as_view({
            'post': 'members',
            'get': 'retrieve',
            'delete': 'members'
        })

        # add bob
        data = {'username': self.user.username}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data,
                         [self.user.username])

        # create user alice
        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)

        # add alice to the team
        data = {'username': alice_profile.user.username}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(sorted(response.data),
                         sorted([self.user.username,
                                 alice_profile.user.username]))

        # check that alice is able to access the team
        alice_extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % alice_profile.user.auth_token}
        request = self.factory.get(
            '/', content_type="application/json", **alice_extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 200)

        # remove alice from the team
        data = {'username': alice_profile.user.username}
        request = self.factory.delete(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data,
                         [self.user.username])

        # check alice cant access the team
        request = self.factory.get(
            '/', content_type="application/json", **alice_extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 404)

    def test_non_owners_should_be_able_to_change_member_permissions(self):
        self._org_create()
        self._publish_xls_form_to_project()

        chuck_data = {'username': 'chuck', 'email': 'chuck@localhost.com'}
        chuck_profile = self._create_user_profile(chuck_data)

        view = OrganizationProfileViewSet.as_view({
            'post': 'members'
        })

        data = {'username': chuck_profile.user.username,
                'role': OwnerRole.name}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user=self.organization.user.username)

        self.assertEqual(response.status_code, 201)

        owners_team = get_or_create_organization_owners_team(self.organization)
        self.assertIn(chuck_profile.user, owners_team.user_set.all())

        alice_data = {'username': 'alice', 'email': 'alice@localhost.com'}
        alice_profile = self._create_user_profile(alice_data)

        data = {'username': alice_profile.user.username}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)

        response = view(request, user=self.organization.user.username)

        self.assertEqual(response.status_code, 201)

        member_team = get_organization_members_team(self.organization)
        self.assertIn(alice_profile.user, member_team.user_set.all())

        view = TeamViewSet.as_view({
            'post': 'share'
        })

        post_data = {'role': EditorRole.name,
                     'project': self.project.pk,
                     'org': self.organization.user.username}
        request = self.factory.post(
            '/', data=post_data, **self.extra)
        response = view(request, pk=member_team.pk)

        self.assertEqual(response.status_code, 204)

        post_data = {'role': ReadOnlyRole.name,
                     'project': self.project.pk,
                     'org': self.organization.user.username}

        extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % chuck_profile.user.auth_token}
        request = self.factory.post(
            '/', data=post_data, **extra)
        response = view(request, pk=member_team.pk)
        self.assertEqual(response.status_code, 204)

    def test_team_members_meta_perms_restrictions(self):
        self._team_create()
        self._publish_xls_form_to_project()
        user_alice = self._create_user('alice', 'alice')

        members_team = Team.objects.get(
            name='%s#%s' % (self.organization.user.username, 'members'))

        # add alice to members team
        add_user_to_team(members_team, user_alice)

        # confirm that the team and members have no permissions on form
        self.assertFalse(get_perms(members_team, self.xform))
        self.assertFalse(get_perms(user_alice, self.xform))

        # share project to team
        view = TeamViewSet.as_view({
            'get': 'list',
            'post': 'share'})

        post_data = {
            'role': EditorRole.name,
            'project': self.project.pk,
            'remove': False
        }
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request, pk=members_team.pk)
        self.assertEqual(response.status_code, 204)

        # team members should have editor permissions now
        alice_perms = get_perms(user_alice, self.xform)
        alice_role = get_role(alice_perms, self.xform)
        self.assertEqual(EditorRole.name, alice_role)
        self.assertTrue(EditorRole.user_has_role(user_alice, self.xform))

        # change meta permissions
        meta_view = MetaDataViewSet.as_view({
            'post': 'create',
            'put': 'update'
        })

        data = {
            'data_type': XFORM_META_PERMS,
            'data_value': 'editor-minor|dataentry',
            'xform': self.xform.pk
        }

        request = self.factory.post('/', data, **self.extra)
        response = meta_view(request)
        self.assertEqual(response.status_code, 201)

        # members should now have EditorMinor role
        self.assertTrue(EditorMinorRole.user_has_role(user_alice, self.xform))
