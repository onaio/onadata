import json

from onadata.apps.api.models import Team
from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet

from onadata.apps.api import tools
from onadata.apps.logger.models import Project
from onadata.apps.api.viewsets.team_viewset import TeamViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.libs.permissions import ReadOnlyRole, EditorRole


class TestTeamViewSet(TestAbstractViewSet):

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
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.data), 3)

    def test_teams_get(self):
        self._team_create()
        view = TeamViewSet.as_view({
            'get': 'retrieve'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.team.pk)
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.team_data)

    def _team_create(self):
        self._org_create()
        data = {
            'name': u'dreamteam',
            'organization': self.company_data['org']
        }
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        self.owner_team = Team.objects.get(
            organization=self.organization.user,
            name='%s#Owners' % (self.organization.user.username))
        team = Team.objects.get(
            organization=self.organization.user,
            name='%s#%s' % (self.organization.user.username, data['name']))
        data['url'] = 'http://testserver/api/v1/teams/%s' % team.pk
        data['teamid'] = team.id
        self.assertDictContainsSubset(data, response.data)
        self.team_data = response.data
        self.team = team

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
        project = Project.objects.create(name="Test Project",
                                         organization=self.team.organization,
                                         created_by=self.user,
                                         metadata='{}')
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
                                                      project))
            data = {'role': role_class.name,
                    'project': project.pk}
            request = self.factory.post(
                '/', data=json.dumps(data),
                content_type="application/json", **self.extra)
            response = view(request, pk=self.team.pk)

            self.assertEqual(response.status_code, 204)
            self.assertTrue(role_class.user_has_role(user_chuck, project))

    def test_remove_team_from_project(self):
        self._team_create()
        project = Project.objects.create(name="Test Project",
                                         organization=self.team.organization,
                                         created_by=self.user,
                                         metadata='{}')
        chuck_data = {'username': 'chuck', 'email': 'chuck@localhost.com'}
        chuck_profile = self._create_user_profile(chuck_data)
        user_chuck = chuck_profile.user

        tools.add_user_to_team(self.team, user_chuck)
        view = TeamViewSet.as_view({
            'post': 'share'})

        self.assertFalse(EditorRole.user_has_role(user_chuck,
                                                  project))
        data = {'role': EditorRole.name,
                'project': project.pk}
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 204)
        self.assertTrue(EditorRole.user_has_role(user_chuck, project))

        data = {'role': EditorRole.name,
                'project': project.pk,
                'remove': True}

        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, pk=self.team.pk)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(EditorRole.user_has_role(user_chuck, project))

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
        self.assertNotEqual(response.get('Last-Modified'), None)
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
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(response.data.get('users')),
                         3)
