import json
import os

from django.conf import settings
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.auth.models import Permission
from rest_framework.test import APIRequestFactory

from onadata.apps.api.models import OrganizationProfile, Project
from onadata.apps.api.viewsets.organization_profile_viewset import\
    OrganizationProfileViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.main.models import UserProfile
from onadata.libs.serializers.project_serializer import ProjectSerializer


class TestAbstractViewSet(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        self.factory = APIRequestFactory()
        self._login_user_and_profile()
        self.maxDiff = None

    def _set_api_permissions(self, user):
        add_userprofile = Permission.objects.get(
            content_type__app_label='main', content_type__model='userprofile',
            codename='add_userprofile')
        user.user_permissions.add(add_userprofile)

    def _login_user_and_profile(self, extra_post_data={}):
        post_data = {
            'username': 'bob',
            'email': 'bob@columbia.edu',
            'password1': 'bobbob',
            'password2': 'bobbob',
            'name': 'Bob',
            'city': 'Bobville',
            'country': 'US',
            'organization': 'Bob Inc.',
            'home_page': 'bob.com',
            'twitter': 'boberama'
        }
        post_data = dict(post_data.items() + extra_post_data.items())
        user, created = User.objects.get_or_create(
            username=post_data['username'],
            first_name=post_data['name'],
            email=post_data['email'])
        user.set_password(post_data['password1'])
        user.save()
        new_profile, created = UserProfile.objects.get_or_create(
            user=user, name=post_data['name'],
            city=post_data['city'],
            country=post_data['country'],
            organization=post_data['organization'],
            home_page=post_data['home_page'],
            twitter=post_data['twitter'])
        self.user = user
        self.assertTrue(
            self.client.login(username=self.user.username, password='bobbob'))
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    def _org_create(self):
        view = OrganizationProfileViewSet.as_view({
            'get': 'list',
            'post': 'create'
        })
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        data = {
            'org': u'denoinc',
            'name': u'Dennis',
            'city': u'Denoville',
            'country': u'US',
            'home_page': u'deno.com',
            'twitter': u'denoinc',
            'description': u'',
            'address': u'',
            'phonenumber': u'',
            'require_auth': False,
        }
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 201)
        data['url'] = 'http://testserver/api/v1/orgs/denoinc'
        data['user'] = 'http://testserver/api/v1/users/denoinc'
        data['creator'] = 'http://testserver/api/v1/users/bob'
        self.assertDictContainsSubset(data, response.data)
        self.company_data = response.data
        self.organization = OrganizationProfile.objects.get(
            user__username=data['org'])

    def _project_create(self):
        view = ProjectViewSet.as_view({
            'post': 'create'
        })
        data = {
            'name': u'demo',
            'owner': 'http://testserver/api/v1/users/%s' % self.user.username
        }
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 201)
        self.project = Project.objects.filter(
            name=data['name'], created_by=self.user)[0]
        data['url'] = 'http://testserver/api/v1/projects/%s/%s'\
            % (self.user.username, self.project.pk)
        self.assertDictContainsSubset(data, response.data)
        self.project_data = ProjectSerializer(
            self.project, context={'request': request}).data

    def _publish_xls_form_to_project(self):
        self._project_create()
        view = ProjectViewSet.as_view({
            'post': 'forms'
        })
        project_id = self.project.pk
        data = {
            'owner': 'http://testserver/api/v1/users/%s' % self.user.username,
            'public': False,
            'public_data': False,
            'description': u'',
            'downloadable': True,
            'allows_sms': False,
            'encrypted': False,
            'sms_id_string': u'transportation_2011_07_25',
            'id_string': u'transportation_2011_07_25',
            'title': u'transportation_2011_07_25',
            'bamboo_dataset': u''
        }
        path = os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation.xls")
        with open(path) as xls_file:
            post_data = {'xls_file': xls_file}
            request = self.factory.post('/', data=post_data, **self.extra)
            response = view(request, owner=self.user.username, pk=project_id)
            self.assertEqual(response.status_code, 201)
            self.xform = self.user.xforms.all()[0]
            data.update({
                'url':
                'http://testserver/api/v1/forms/%s/%s' % (self.user.username,
                                                          self.xform.pk)
            })
            self.assertDictContainsSubset(data, response.data)
            self.form_data = response.data
