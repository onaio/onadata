import json

from onadata.apps.api.models import Team
from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet

from onadata.apps.api import tools
from onadata.apps.api.models.project import Project
from onadata.apps.api.viewsets.team_viewset import TeamViewSet
from onadata.libs.permissions import ReadOnlyRole, DataEntryRole


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
        owner_team = {
            'teamid': self.owner_team.pk,
            'url':
            'http://testserver/api/v1/teams/%s' % self.owner_team.pk,
            'name': u'Owners',
            'organization': 'denoinc',
            'projects': [],
            'users': [{'username': u'bob',
                       'first_name': u'Bob',
                       'last_name': u'',
                       'id': self.user.pk}
                      ]
        }
        self.assertNotEqual(response.get('Last-Modified'), None)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted(response.data), [owner_team, self.team_data])

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

    def test_set_default_project_permissions(self):
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
            'post': 'default_permissions'})

        ROLES = [ReadOnlyRole,
                 DataEntryRole]

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
