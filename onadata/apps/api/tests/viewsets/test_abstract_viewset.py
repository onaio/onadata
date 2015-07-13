import json
import os
import re
import requests
import StringIO

from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import TestCase
from django_digest.test import Client as DigestClient
from tempfile import NamedTemporaryFile
from django.contrib.auth.models import User
from django_digest.test import DigestAuth
from django.contrib.auth import authenticate
from httmock import urlmatch, HTTMock

from rest_framework.test import APIRequestFactory

from onadata.apps.api.models import OrganizationProfile
from onadata.apps.api.viewsets.metadata_viewset import MetaDataViewSet
from onadata.apps.api.viewsets.organization_profile_viewset import\
    OrganizationProfileViewSet
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet
from onadata.apps.api.viewsets.widget_viewset import WidgetViewSet
from onadata.apps.main.models import UserProfile, MetaData
from onadata.apps.main import tests as main_tests
from onadata.apps.logger.models import Attachment
from onadata.apps.logger.models import Instance
from onadata.apps.logger.models import XForm
from onadata.apps.logger.models import Project
from onadata.apps.logger.models.widget import Widget
from onadata.apps.logger.models.data_view import DataView
from onadata.libs.serializers.project_serializer import ProjectSerializer
from onadata.apps.logger.views import submission
from onadata.apps.api.models import Team
from onadata.apps.api.viewsets.team_viewset import TeamViewSet


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$', path=r'^/api_v1/survey/preview$')
def enketo_preview_url_mock(url, request):
    response = requests.Response()
    response.status_code = 201
    response._content = \
        '{\n  "preview_url": "https:\\/\\/enketo.ona.io\\/preview/::YY8M",\n'\
        '  "code": "201"\n}'
    return response


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$', path=r'^/api_v1/survey$')
def enketo_url_mock(url, request):
    response = requests.Response()
    response.status_code = 201
    response._content = \
        '{\n  "url": "https:\\/\\/enketo.ona.io\\/::YY8M",\n'\
        '  "code": "200"\n}'
    return response


class TestAbstractViewSet(TestCase):
    surveys = ['transport_2011-07-25_19-05-49',
               'transport_2011-07-25_19-05-36',
               'transport_2011-07-25_19-06-01',
               'transport_2011-07-25_19-06-14']
    main_directory = os.path.dirname(main_tests.__file__)

    profile_data = {
        'username': 'bob',
        'email': 'bob@columbia.edu',
        'password1': 'bobbob',
        'password2': 'bobbob',
        'first_name': 'Bob',
        'last_name': 'erama',
        'city': 'Bobville',
        'country': 'US',
        'organization': 'Bob Inc.',
        'home_page': 'bob.com',
        'twitter': 'boberama',
        'name': u'Bob erama'
    }

    def setUp(self):
        TestCase.setUp(self)
        self.factory = APIRequestFactory()
        self._login_user_and_profile()
        self.maxDiff = None

    def user_profile_data(self):
        return {
            'id': self.user.pk,
            'url': 'http://testserver/api/v1/profiles/bob',
            'username': u'bob',
            'first_name': u'Bob',
            'last_name': 'erama',
            'email': u'bob@columbia.edu',
            'city': u'Bobville',
            'country': u'US',
            'organization': u'Bob Inc.',
            'website': u'bob.com',
            'twitter': u'boberama',
            'gravatar': self.user.profile.gravatar,
            'require_auth': False,
            'user': 'http://testserver/api/v1/users/bob',
            'is_org': False,
            'metadata': {},
            'joined_on': self.user.date_joined,
            'name': u'Bob erama'
        }

    def _set_api_permissions(self, user):
        add_userprofile = Permission.objects.get(
            content_type__app_label='main', content_type__model='userprofile',
            codename='add_userprofile')
        user.user_permissions.add(add_userprofile)

    def _create_user_profile(self, extra_post_data={}):
        self.profile_data = dict(
            self.profile_data.items() + extra_post_data.items())
        user, created = User.objects.get_or_create(
            username=self.profile_data['username'],
            first_name=self.profile_data['first_name'],
            last_name=self.profile_data['last_name'],
            email=self.profile_data['email'])
        user.set_password(self.profile_data['password1'])
        user.save()
        new_profile, created = UserProfile.objects.get_or_create(
            user=user, name=self.profile_data['first_name'],
            city=self.profile_data['city'],
            country=self.profile_data['country'],
            organization=self.profile_data['organization'],
            home_page=self.profile_data['home_page'],
            twitter=self.profile_data['twitter'],
            require_auth=False
        )

        return new_profile

    def _login_user_and_profile(self, extra_post_data={}):
        profile = self._create_user_profile(extra_post_data)
        self.user = profile.user
        self.assertTrue(
            self.client.login(username=self.user.username,
                              password=self.profile_data['password1']))
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

    def _project_create(self, project_data={}, merge=True):
        view = ProjectViewSet.as_view({
            'post': 'create'
        })

        if merge:
            data = {
                'name': u'demo',
                'owner':
                'http://testserver/api/v1/users/%s' % self.user.username,
                'metadata': {'description': 'Some description',
                             'location': 'Naivasha, Kenya',
                             'category': 'governance'},
                'public': False
            }
            data.update(project_data)
        else:
            data = project_data

        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request, owner=self.user.username)
        self.assertEqual(response.status_code, 201)
        self.project = Project.objects.filter(
            name=data['name'], created_by=self.user)[0]
        data['url'] = 'http://testserver/api/v1/projects/%s'\
            % self.project.pk
        self.assertDictContainsSubset(data, response.data)

        request.user = self.user
        self.project_data = ProjectSerializer(
            self.project, context={'request': request}).data

    def _publish_xls_form_to_project(self, publish_data={}, merge=True,
                                     public=False, xlsform_path=None):
        if not hasattr(self, 'project'):
            self._project_create()
        elif self.project.created_by != self.user:
            self._project_create()

        view = ProjectViewSet.as_view({
            'post': 'forms'
        })

        project_id = self.project.pk
        if merge:
            data = {
                'owner': 'http://testserver/api/v1/users/%s'
                % self.project.organization.username,
                'public': False,
                'public_data': False,
                'description': u'transportation_2011_07_25',
                'downloadable': True,
                'allows_sms': False,
                'encrypted': False,
                'sms_id_string': u'transportation_2011_07_25',
                'id_string': u'transportation_2011_07_25',
                'title': u'transportation_2011_07_25',
                'bamboo_dataset': u''
            }
            data.update(publish_data)
        else:
            data = publish_data

        path = xlsform_path or os.path.join(
            settings.PROJECT_ROOT, "apps", "main", "tests", "fixtures",
            "transportation", "transportation.xls")

        with HTTMock(enketo_preview_url_mock, enketo_url_mock):
            with open(path) as xls_file:
                post_data = {'xls_file': xls_file}
                request = self.factory.post(
                    '/', data=post_data, **self.extra)
                response = view(request, pk=project_id)
                self.assertEqual(response.status_code, 201)
                self.xform = XForm.objects.all().order_by('pk').reverse()[0]
                data.update({
                    'url':
                    'http://testserver/api/v1/forms/%s' % (self.xform.pk)
                })

                # Input was a private so change to public if project public
                if public:
                    data['public_data'] = data['public'] = True

                self.form_data = response.data

    def _add_uuid_to_submission_xml(self, path, xform):
        tmp_file = NamedTemporaryFile(delete=False)
        split_xml = None

        with open(path) as _file:
            split_xml = re.split(r'(<transport>)', _file.read())

        split_xml[1:1] = [
            '<formhub><uuid>%s</uuid></formhub>' % xform.uuid
        ]
        tmp_file.write(''.join(split_xml))
        path = tmp_file.name
        tmp_file.close()

        return path

    def _make_submission(self, path, username=None, add_uuid=False,
                         forced_submission_time=None,
                         client=None, media_file=None, auth=None):
        # store temporary file with dynamic uuid
        self.factory = APIRequestFactory()
        if auth is None:
            auth = DigestAuth(self.profile_data['username'],
                              self.profile_data['password1'])

        tmp_file = None

        if add_uuid:
            path = self._add_uuid_to_submission_xml(path, self.xform)
        with open(path) as f:
            post_data = {'xml_submission_file': f}

            if media_file is not None:
                if isinstance(media_file, list):
                    for c in range(len(media_file)):
                        post_data['media_file_{}'.format(c)] = media_file[c]
                else:
                    post_data['media_file'] = media_file

            if username is None:
                username = self.user.username

            url_prefix = '%s/' % username if username else ''
            url = '/%ssubmission' % url_prefix

            request = self.factory.post(url, post_data)
            request.user = authenticate(username=auth.username,
                                        password=auth.password)
            self.response = submission(request, username=username)

            if auth and self.response.status_code == 401:
                request.META.update(auth(request.META, self.response))
                self.response = submission(request, username=username)

        if forced_submission_time:
            instance = Instance.objects.order_by('-pk').all()[0]
            instance.date_created = forced_submission_time
            instance.save()
            instance.parsed_instance.save()

        # remove temporary file if stored
        if add_uuid:
            os.unlink(tmp_file.name)

    def _make_submissions(self, username=None, add_uuid=False,
                          should_store=True):
        """Make test fixture submissions to current xform.

        :param username: submit under this username, default None.
        :param add_uuid: add UUID to submission, default False.
        :param should_store: should submissions be save, default True.
        """
        paths = [os.path.join(
            self.main_directory, 'fixtures', 'transportation',
            'instances', s, s + '.xml') for s in self.surveys]
        pre_count = Instance.objects.count()

        auth = DigestAuth(self.profile_data['username'],
                          self.profile_data['password1'])
        for path in paths:
            self._make_submission(path, username, add_uuid, auth=auth)
        post_count = pre_count + len(self.surveys) if should_store\
            else pre_count
        self.assertEqual(Instance.objects.count(), post_count)
        self.assertEqual(self.xform.instances.count(), post_count)
        xform = XForm.objects.get(pk=self.xform.pk)
        self.assertEqual(xform.num_of_submissions, post_count)
        self.assertEqual(xform.user.profile.num_of_submissions, post_count)

    def _submit_transport_instance_w_attachment(self,
                                                survey_at=0,
                                                media_file=None):
        s = self.surveys[survey_at]
        if not media_file:
            media_file = "1335783522563.jpg"
        path = os.path.join(self.main_directory, 'fixtures',
                            'transportation', 'instances', s, media_file)
        with open(path) as f:
            self._make_submission(os.path.join(
                self.main_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml'), media_file=f)

        attachment = Attachment.objects.all().reverse()[0]
        self.attachment = attachment

    def _post_form_metadata(self, data, test=True):
        count = MetaData.objects.count()
        view = MetaDataViewSet.as_view({'post': 'create'})
        request = self.factory.post('/', data, **self.extra)
        response = view(request)

        if test:
            self.assertEqual(response.status_code, 201)
            another_count = MetaData.objects.count()
            self.assertEqual(another_count, count + 1)
            self.metadata = MetaData.objects.get(pk=response.data['id'])
            self.metadata_data = response.data

        return response

    def _add_form_metadata(self, xform, data_type, data_value, path=None):
        data = {
            'data_type': data_type,
            'data_value': data_value,
            'xform': xform.pk
        }

        if path and data_value:
            with open(path) as media_file:
                data.update({
                    'data_file': media_file,
                })
                self._post_form_metadata(data)
        else:
            self._post_form_metadata(data)

    def _get_digest_client(self):
        self.user.profile.require_auth = True
        self.user.profile.save()
        client = DigestClient()
        client.set_authorization(self.profile_data['username'],
                                 self.profile_data['password1'],
                                 'Digest')
        return client

    def _create_dataview(self, data=None):
        view = DataViewViewSet.as_view({
            'post': 'create'
        })

        if data:
            data = data
        else:
            data = {
                'name': "My DataView",
                'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
                'project':  'http://testserver/api/v1/projects/%s'
                            % self.project.pk,
                'columns': '["name", "age", "gender"]',
                'query': '[{"column":"age","filter":">","value":"20"},'
                         '{"column":"age","filter":"<","value":"50"}]'
            }

        request = self.factory.post('/', data=data, **self.extra)
        response = view(request)

        self.assertEquals(response.status_code, 201)

        # load the created dataview
        self.data_view = DataView.objects.filter(xform=self.xform,
                                                 project=self.project)[0]

        self.assertEquals(response.data['name'], data['name'])
        self.assertEquals(response.data['xform'], data['xform'])
        self.assertEquals(response.data['project'], data['project'])
        self.assertEquals(response.data['columns'],
                          json.loads(data['columns']))
        self.assertEquals(response.data['query'],
                          json.loads(data['query']) if 'query' in data else {})
        self.assertEquals(response.data['url'],
                          'http://testserver/api/v1/dataviews/%s'
                          % self.data_view.pk)

    def _create_widget(self, data=None):
        view = WidgetViewSet.as_view({
            'post': 'create'
        })

        if data:
            data = data
        else:
            data = {
                'title': "Widget that",
                'content_object': 'http://testserver/api/v1/forms/%s' %
                                  self.xform.pk,
                'description': "Test widget",
                'widget_type': "charts",
                'view_type': "horizontal-bar",
                'column': "age",
                'group_by': "gender"
            }
        count = Widget.objects.all().count()

        request = self.factory.post('/', data=data, **self.extra)
        response = view(request)

        self.assertEquals(response.status_code, 201)
        self.assertEquals(count+1, Widget.objects.all().count())

        self.widget = Widget.objects.all().order_by('pk').reverse()[0]

        self.assertEquals(response.data['title'],
                          data['title'] if 'title' in data else None)
        self.assertEquals(response.data['content_object'],
                          data['content_object'])
        self.assertEquals(response.data['widget_type'], data['widget_type'])
        self.assertEquals(response.data['view_type'], data['view_type'])
        self.assertEquals(response.data['column'], data['column'])
        self.assertEquals(response.data['description'],
                          data['description']
                          if 'description' in data else None)
        self.assertEquals(response.data['group_by'],
                          data['group_by'] if 'group_by' in data else None)
        self.assertEquals(response.data['data'], [])

    def filename_from_disposition(self, content_disposition):
        filename_pos = content_disposition.index('filename=')
        assert filename_pos != -1
        return content_disposition[filename_pos + len('filename='):]

    def get_response_content(self, response):
        contents = u''
        if response.streaming:
            actual_content = StringIO.StringIO()
            for content in response.streaming_content:
                actual_content.write(content)
            contents = actual_content.getvalue()
            actual_content.close()
        else:
            contents = response.content
        return contents

    def _team_create(self):
        self._org_create()

        view = TeamViewSet.as_view({
            'get': 'list',
            'post': 'create'
        })

        data = {
            'name': u'dreamteam',
            'organization': self.company_data['org']
        }
        request = self.factory.post(
            '/', data=json.dumps(data),
            content_type="application/json", **self.extra)
        response = view(request)
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
