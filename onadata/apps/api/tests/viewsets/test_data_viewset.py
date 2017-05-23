import geojson
import json
import os
import requests
import datetime
from mock import patch
from datetime import timedelta
from django.utils import timezone
from django.test import RequestFactory
from django.test.utils import override_settings
from django_digest.test import DigestAuth
from django_digest.test import Client as DigestClient
from httmock import urlmatch, HTTMock

from onadata.apps.api.viewsets.data_viewset import DataViewSet
from onadata.apps.main import tests as main_tests
from onadata.apps.api.viewsets.project_viewset import ProjectViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.main.models import UserProfile
from onadata.apps.main.tests.test_base import TestBase
from onadata.libs.utils.logger_tools import create_instance
from onadata.apps.logger.models import Attachment
from onadata.apps.logger.models import Instance
from onadata.apps.main.models.meta_data import MetaData
from onadata.apps.logger.models.instance import InstanceHistory
from onadata.apps.logger.models import XForm
from onadata.libs.permissions import ReadOnlyRole, EditorRole, \
    EditorMinorRole, DataEntryOnlyRole, DataEntryMinorRole
from onadata.libs import permissions as role
from onadata.libs.utils.common_tags import MONGO_STRFTIME
from onadata.apps.logger.models.instance import get_attachment_url
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    enketo_preview_url_mock


@urlmatch(netloc=r'(.*\.)?enketo\.ona\.io$')
def enketo_mock(url, request):
    response = requests.Response()
    response.status_code = 201
    response._content = '{"url": "https://hmh2a.enketo.ona.io"}'
    return response


def _data_list(formid):
    return [{
        u'id': formid,
        u'id_string': u'transportation_2011_07_25',
        u'title': 'transportation_2011_07_25',
        u'description': '',
        u'url': u'http://testserver/api/v1/data/%s' % formid
    }]


def _data_instance(dataid):
    return {
        u'_bamboo_dataset_id': u'',
        u'_attachments': [],
        u'_geolocation': [None, None],
        u'_xform_id_string': u'transportation_2011_07_25',
        u'transport/available_transportation_types_to_referral_facility':
        u'none',
        u'_status': u'submitted_via_web',
        u'_id': dataid
    }


class TestDataViewSet(TestBase):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    def test_data(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())

        dataid = self.xform.instances.all().order_by('id')[0].pk
        data = _data_instance(dataid)
        self.assertDictContainsSubset(data, sorted(response.data)[0])

        data = {
            u'_xform_id_string': u'transportation_2011_07_25',
            u'transport/available_transportation_types_to_referral_facility':
            u'none',
            u'_submitted_by': u'bob',
        }
        view = DataViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertIsInstance(response.data, dict)
        self.assertDictContainsSubset(data, response.data)

    @override_settings(STREAM_DATA=True)
    def test_data_streaming(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)

        # expect streaming response
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        streaming_data = json.loads(
            u''.join([i for i in response.streaming_content])
        )
        self.assertIsInstance(streaming_data, list)
        self.assertTrue(self.xform.instances.count())

        dataid = self.xform.instances.all().order_by('id')[0].pk
        data = _data_instance(dataid)
        self.assertDictContainsSubset(data, sorted(streaming_data)[0])

        data = {
            u'_xform_id_string': u'transportation_2011_07_25',
            u'transport/available_transportation_types_to_referral_facility':
            u'none',
            u'_submitted_by': u'bob',
        }
        view = DataViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertIsInstance(response.data, dict)
        self.assertDictContainsSubset(data, response.data)

    def test_catch_data_error(self):
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk
        query_str = [(u'\'{"_submission_time":{'
                      '"$and":[{"$gte":"2015-11-15T00:00:00"},'
                      '{"$lt":"2015-11-16T00:00:00"}]}}')]

        data = {
            'query': query_str,
        }
        request = self.factory.get('/', data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data.get('detail'),
            u'invalid regular expression: invalid character range\n')

    def test_data_list_with_xform_in_delete_async_queue(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.status_code, 200)
        initial_count = len(response.data)

        self.xform.deleted_at = timezone.now()
        self.xform.save()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(len(response.data), initial_count - 1)

    def test_numeric_types_are_rendered_as_required(self):
        tutorial_folder = os.path.join(
            os.path.dirname(__file__),
            '..', 'fixtures', 'forms', 'tutorial')
        self._publish_xls_file_and_set_xform(os.path.join(tutorial_folder,
                                                          'tutorial.xls'))

        instance_path = os.path.join(tutorial_folder, 'instances', '1.xml')
        create_instance(self.user.username, open(instance_path), [])

        self.assertEqual(self.xform.instances.count(), 1)
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.xform.id)
        self.assertEqual(response.status_code, 200)
        # check that ONLY values with numeric and decimal types are converted
        self.assertEqual(response.data[0].get('age'), 35)
        self.assertEqual(response.data[0].get('net_worth'), 100000.00)
        self.assertEqual(response.data[0].get('imei'), u'351746052009472')

    def test_data_jsonp(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid, format='jsonp')
        self.assertEqual(response.status_code, 200)
        response.render()
        self.assertTrue(response.content.startswith('callback('))
        self.assertTrue(response.content.endswith(');'))
        self.assertEqual(len(response.data), 4)

    def _assign_user_role(self, user, role):
        # share bob's project with alice and give alice an editor role
        data = {'username': user.username, 'role': role.name}
        request = self.factory.put('/', data=data, **self.extra)
        xform_view = XFormViewSet.as_view({
            'put': 'share'
        })
        response = xform_view(request, pk=self.xform.pk)
        self.assertEqual(response.status_code, 204)

        self.assertTrue(
            role.user_has_role(user, self.xform)
        )

    def test_returned_data_is_based_on_form_permissions(self):
        # create a form and make submissions to it
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        # create user alice
        user_alice = self._create_user('alice', 'alice')
        # create user profile and set require_auth to false for tests
        profile, created = UserProfile.objects.get_or_create(user=user_alice)
        profile.require_auth = False
        profile.save()

        # Enable meta perms
        data_value = "editor-minor|dataentry-minor"
        MetaData.xform_meta_permission(self.xform, data_value=data_value)

        self._assign_user_role(user_alice, DataEntryOnlyRole)

        alices_extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % user_alice.auth_token.key
        }

        request = self.factory.get('/', **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        data = {"start": 1, "limit": 4}
        request = self.factory.get('/', data=data, **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        data = {"sort": 1}
        request = self.factory.get('/', data=data, **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        self._assign_user_role(user_alice, EditorMinorRole)
        # check that by default, alice can be able to access all the data

        request = self.factory.get('/', **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # change xform permission for users with editor role - they should
        # only view data that they submitted
        self.xform.save()

        # change user in 2 instances to be owned by alice - they should appear
        # as if they were submitted by alice
        for i in self.xform.instances.all()[:2]:
            i.user = user_alice
            i.save()

        # check that 2 instances were 'submitted by' alice
        instances_submitted_by_alice = self.xform.instances.filter(
            user=user_alice).count()
        self.assertTrue(instances_submitted_by_alice, 2)

        # check that alice will only be able to see the data she submitted
        request = self.factory.get('/', **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        data = {"start": 1, "limit": 1}
        request = self.factory.get('/', data=data, **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        data = {"sort": 1}
        request = self.factory.get('/', data=data, **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # change meta perms
        data_value = "editor|dataentry-minor"
        MetaData.xform_meta_permission(self.xform, data_value=data_value)

        self._assign_user_role(user_alice, EditorRole)

        request = self.factory.get('/', **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        self._assign_user_role(user_alice, ReadOnlyRole)

        request = self.factory.get('/', **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    def test_xform_meta_permissions_not_affected_w_projects_perms(self):
        # create a form and make submissions to it
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        # create user alice
        user_alice = self._create_user('alice', 'alice')
        # create user profile and set require_auth to false for tests
        profile, created = UserProfile.objects.get_or_create(user=user_alice)
        profile.require_auth = False
        profile.save()

        data = {'username': user_alice.username, 'role': EditorRole.name}
        request = self.factory.put('/', data=data, **self.extra)
        project_view = ProjectViewSet.as_view({
            'put': 'share'
        })
        response = project_view(request, pk=self.project.pk)
        self.assertEqual(response.status_code, 204)

        self.assertTrue(
            EditorRole.user_has_role(user_alice, self.xform)
        )
        self._assign_user_role(user_alice, EditorMinorRole)
        MetaData.xform_meta_permission(self.xform,
                                       data_value='editor-minor|dataentry')

        self.assertFalse(
            EditorRole.user_has_role(user_alice, self.xform)
        )

        alices_extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % user_alice.auth_token.key
        }

        request = self.factory.get('/', **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

        self.assertFalse(
            EditorRole.user_has_role(user_alice, self.xform)
        )
        self.assertEqual(len(response.data), 0)

    def test_data_entryonly_can_submit_but_not_view(self):
        # create user alice
        user_alice = self._create_user('alice', 'alice')
        # create user profile and set require_auth to false for tests
        profile, created = UserProfile.objects.get_or_create(user=user_alice)
        profile.require_auth = False
        profile.save()

        # Enable meta perms
        data_value = "editor-minor|dataentry-minor"
        MetaData.xform_meta_permission(self.xform, data_value=data_value)

        DataEntryOnlyRole.add(user_alice, self.xform)
        DataEntryOnlyRole.add(user_alice, self.project)

        auth = DigestAuth('alice', 'alice')

        paths = [os.path.join(
            self.this_directory, 'fixtures', 'transportation',
            'instances', s, s + '.xml') for s in self.surveys]

        for path in paths:
            self._make_submission(path, auth=auth)

        alices_extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % user_alice.auth_token.key
        }

        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk
        request = self.factory.get('/', **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        DataEntryMinorRole.add(user_alice, self.xform)
        DataEntryMinorRole.add(user_alice, self.project)

        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk
        request = self.factory.get('/', **alices_extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    def test_data_pagination(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk

        # no page param no pagination
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.has_header('X-total'))
        self.assertEqual(int(response.get('X-total')), 4)
        self.assertEqual(len(response.data), 4)

        request = self.factory.get('/', data={"page": "1", "page_size": 2},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.has_header('X-total'))
        self.assertEqual(int(response.get('X-total')), 4)
        self.assertEqual(len(response.data), 2)

        request = self.factory.get('/', data={"page_size": "3"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.has_header('X-total'))
        self.assertEqual(int(response.get('X-total')), 4)
        self.assertEqual(len(response.data), 3)

        request = self.factory.get(
            '/', data={"page": "1", "page_size": "2"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.has_header('X-total'))
        self.assertEqual(int(response.get('X-total')), 4)
        self.assertEqual(len(response.data), 2)

        # invalid page returns a 404
        request = self.factory.get('/', data={"page": "invalid"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 404)

        # invalid page size is ignored
        request = self.factory.get('/', data={"page_size": "invalid"},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        request = self.factory.get(
            '/', data={"page": "invalid", "page-size": "invalid"},
            **self.extra)
        response = view(request, pk=formid)

    def test_sort_query_param_with_invalid_values(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk

        # without sort param
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        error_message = (u'Expecting property name enclosed in '
                         'double quotes: line 1 column 2 (char 1)')

        request = self.factory.get('/', data={"sort": u'{'':}'},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('detail'), error_message)

        request = self.factory.get('/', data={"sort": u'{:}'},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('detail'), error_message)

        request = self.factory.get('/', data={"sort": u'{'':''}'},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('detail'), error_message)

        # test sort with a key that os likely in the json data
        request = self.factory.get('/', data={"sort": u'random'},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    def test_data_start_limit_no_records(self):
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk

        # no start, limit params
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)
        etag_data = response['Etag']

        request = self.factory.get('/', data={"start": "1", "limit": 2},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)
        self.assertNotEqual(etag_data, response['Etag'])

    def test_data_start_limit(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk

        # no start, limit params
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)
        self.assertTrue(response.has_header('ETag'))
        etag_data = response['Etag']

        request = self.factory.get('/', data={"start": "1", "limit": 2},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertNotEqual(etag_data, response['Etag'])
        etag_data = response['Etag']
        response.render()
        data = json.loads(response.content)
        self.assertEqual([i['_uuid'] for i in data],
                         [u'f3d8dc65-91a6-4d0f-9e97-802128083390',
                          u'9c6f3468-cfda-46e8-84c1-75458e72805d'])

        request = self.factory.get('/', data={"start": "3", "limit": 1},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertNotEqual(etag_data, response['Etag'])
        etag_data = response['Etag']
        response.render()
        data = json.loads(response.content)
        self.assertEqual([i['_uuid'] for i in data],
                         [u'9f0a1508-c3b7-4c99-be00-9b237c26bcbf'])

        request = self.factory.get('/', data={"limit": "3"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)
        self.assertNotEqual(etag_data, response['Etag'])
        etag_data = response['Etag']

        request = self.factory.get(
            '/', data={"start": "1", "limit": "2"}, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertNotEqual(etag_data, response['Etag'])

        # invalid start is ignored, all data is returned
        request = self.factory.get('/', data={"start": "invalid"},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        # invalid limit is ignored, all data is returned
        request = self.factory.get('/', data={"limit": "invalid"},
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    def test_data_start_limit_sort(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk
        data = {"start": 1, "limit": 2, "sort": '{"_id":1}'}
        request = self.factory.get('/', data=data,
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertTrue(response.has_header('ETag'))
        response.render()
        data = json.loads(response.content)
        self.assertEqual([i['_uuid'] for i in data],
                         [u'f3d8dc65-91a6-4d0f-9e97-802128083390',
                          u'9c6f3468-cfda-46e8-84c1-75458e72805d'])

    @override_settings(STREAM_DATA=True)
    def test_data_start_limit_sort_json_field(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk
        # will result in a generator due to the JSON sort
        # hence self.total_count will be used for length in streaming response
        data = {
            "start": 1,
            "limit": 2,
            "sort": '{"transport/available_transportation_types_to_referral_facility":1}'  # noqa
        }
        request = self.factory.get('/', data=data,
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.has_header('ETag'))
        data = json.loads(''.join([c for c in response.streaming_content]))
        self.assertEqual(len(data), 2)
        self.assertEqual([i['_uuid'] for i in data],
                         [u'f3d8dc65-91a6-4d0f-9e97-802128083390',
                          u'5b2cc313-fc09-437e-8149-fcd32f695d41'])

        # will result in a queryset due to the page and page_size params
        # hence paging and thus len(self.object_list) for length
        data = {
            "page": 1,
            "page_size": 2,
        }
        request = self.factory.get('/', data=data,
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        data = json.loads(''.join([c for c in response.streaming_content]))
        self.assertEqual(len(data), 2)

        data = {
            "page": 1,
            "page_size": 3,
        }
        request = self.factory.get('/', data=data,
                                   **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        data = json.loads(''.join([c for c in response.streaming_content]))
        self.assertEqual(len(data), 3)

    def test_data_anon(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        formid = self.xform.pk
        response = view(request, pk=formid)
        # data not found for anonymous access to private data
        self.assertEqual(response.status_code, 404)

        self.xform.shared = True
        self.xform.save()
        response = view(request, pk=formid)
        # access to a shared form but private data
        self.assertEqual(response.status_code, 404)

        self.xform.shared_data = True
        self.xform.save()
        response = view(request, pk=formid)
        # access to a public data
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = self.xform.instances.all().order_by('id')[0].pk
        data = _data_instance(dataid)

        self.assertDictContainsSubset(data, sorted(response.data)[0])

        data = {
            u'_xform_id_string': u'transportation_2011_07_25',
            u'transport/available_transportation_types_to_referral_facility':
            u'none',
            u'_submitted_by': u'bob',
        }
        view = DataViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, dict)
        self.assertDictContainsSubset(data, response.data)

    def test_data_public(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request, pk='public')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.has_header('X-total'))
        self.assertEqual(int(response.get('X-total')), 0)
        self.assertEqual(response.data, [])
        self.xform.shared_data = True
        self.xform.save()
        formid = self.xform.pk
        data = _data_list(formid)
        response = view(request, pk='public')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.has_header('X-total'))
        self.assertEqual(int(response.get('X-total')), 1)
        self.assertEqual(response.data, data)

    def test_data_public_anon_user(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        response = view(request, pk='public')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.xform.shared_data = True
        self.xform.save()
        formid = self.xform.pk
        data = _data_list(formid)
        response = view(request, pk='public')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_data_user_public(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request, pk='public')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.xform.shared_data = True
        self.xform.save()
        formid = self.xform.pk
        data = _data_list(formid)
        response = view(request, pk='public')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_data_bad_formid(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

        formid = 98918
        self.assertEqual(XForm.objects.filter(pk=formid).count(), 0)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 404)

        formid = "INVALID"
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get('Cache-Control'), None)
        data = {u'detail': u'Invalid form ID: INVALID'}
        self.assertEqual(response.data, data)

    def test_data_bad_dataid(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = 'INVALID'
        data = _data_instance(dataid)
        view = DataViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get('Cache-Control'), None)

    def test_filter_by_submission_time_and_submitted_by(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        instance = self.xform.instances.all().order_by('pk')[0]
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        submission_time = instance.date_created.strftime(MONGO_STRFTIME)
        query_str = ('{"_submission_time": {"$gte": "%s"},'
                     ' "_submitted_by": "%s"}' % (submission_time, 'bob'))
        data = {
            'query': query_str,
            'limit': 2,
            'sort': []
        }
        request = self.factory.get('/', data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_filter_by_submission_time_and_submitted_by_with_data_arg(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        instance = self.xform.instances.all().order_by('pk')[0]
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        submission_time = instance.date_created.strftime(MONGO_STRFTIME)
        query_str = ('{"_submission_time": {"$gte": "%s"},'
                     ' "_submitted_by": "%s"}' % (submission_time, 'bob'))
        data = {
            'data': query_str,
            'limit': 2,
            'sort': []
        }
        request = self.factory.get('/', data=data, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_data_with_query_parameter(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        instance = self.xform.instances.all().order_by('pk')[0]
        dataid = instance.pk
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        query_str = '{"_id": "%s"}' % dataid
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.has_header('X-total'))
        self.assertEqual(int(response.get('X-total')), 1)
        self.assertEqual(len(response.data), 1)

        submission_time = instance.date_created.strftime(MONGO_STRFTIME)
        query_str = '{"_submission_time": {"$gte": "%s"}}' % submission_time
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

        # reorder date submitted
        start_time = datetime.datetime(2015, 12, 2)
        curr_time = start_time
        for inst in self.xform.instances.all():
            inst.date_created = curr_time
            inst.json = instance.get_full_dict()
            inst.save()
            inst.parsed_instance.save()
            curr_time += timedelta(days=1)

        first_datetime = start_time.strftime(MONGO_STRFTIME)
        second_datetime = start_time + timedelta(days=1, hours=20)

        query_str = '{"_submission_time": {"$gte": "'\
                    + first_datetime + '", "$lte": "'\
                    + second_datetime.strftime(MONGO_STRFTIME) + '"}}'

        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        query_str = '{"_id: "%s"}' % dataid
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get('detail'),
                         u"Expecting ':' delimiter: line 1 column 9 (char 8)")

        query_str = '{"transport/available_transportation' \
                    '_types_to_referral_facility": {"$i": "%s"}}' % "ambula"
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        # search a text
        query_str = 'uuid:9f0a1508-c3b7-4c99-be00-9b237c26bcbf'
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        # search an integer
        query_str = 7545
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_anon_data_list(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        response = view(request)
        self.assertEqual(response.status_code, 200)

    def test_add_form_tag_propagates_to_data_tags(self):
        """Test that when a tag is applied on an xform,
        it propagates to the instance submissions
        """
        self._make_submissions()
        xform = XForm.objects.all()[0]
        pk = xform.id
        view = XFormViewSet.as_view({
            'get': 'labels',
            'post': 'labels',
            'delete': 'labels'
        })
        data_view = DataViewSet.as_view({
            'get': 'list',
        })
        # no tags
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=pk)
        self.assertEqual(response.data, [])

        request = self.factory.get('/', {'tags': 'hello'}, **self.extra)
        response = data_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get('/', {'not_tagged': 'hello'}, **self.extra)
        response = data_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        # add tag "hello"
        request = self.factory.post('/', data={"tags": "hello"}, **self.extra)
        response = view(request, pk=pk)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [u'hello'])
        for i in self.xform.instances.all():
            self.assertIn(u'hello', i.tags.names())

        request = self.factory.get('/', {'tags': 'hello'}, **self.extra)
        response = data_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        request = self.factory.get('/', {'not_tagged': 'hello'}, **self.extra)
        response = data_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # remove tag "hello"
        request = self.factory.delete('/', data={"tags": "hello"},
                                      **self.extra)
        response = view(request, pk=pk, label='hello')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        for i in self.xform.instances.all():
            self.assertNotIn(u'hello', i.tags.names())

    def test_data_tags(self):
        """Test that when a tag is applied on an xform,
        it propagates to the instance submissions
        """
        self._make_submissions()
        submission_count = self.xform.instances.count()
        pk = self.xform.pk
        i = self.xform.instances.all()[0]
        dataid = i.pk
        data_view = DataViewSet.as_view({
            'get': 'list',
        })
        view = DataViewSet.as_view({
            'get': 'labels',
            'post': 'labels',
            'delete': 'labels'
        })

        # no tags
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=pk, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        request = self.factory.get('/', {'tags': 'hello'}, **self.extra)
        response = data_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        request = self.factory.get('/', {'not_tagged': 'hello'}, **self.extra)
        response = data_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), submission_count)

        # add tag "hello"
        request = self.factory.post('/', data={"tags": "hello"}, **self.extra)
        response = view(request, pk=pk, dataid=dataid)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data, [u'hello'])
        self.assertIn(u'hello', Instance.objects.get(pk=dataid).tags.names())

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=pk, dataid=dataid)
        self.assertEqual(response.data, [u'hello'])

        request = self.factory.get('/', {'tags': 'hello'}, **self.extra)
        response = data_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        request = self.factory.get('/', {'not_tagged': 'hello'}, **self.extra)
        response = data_view(request, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), submission_count - 1)

        # remove tag "hello"
        request = self.factory.delete('/', **self.extra)
        response = view(request, pk=pk, dataid=dataid, label='hello')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.assertNotIn(
            u'hello', Instance.objects.get(pk=dataid).tags.names())

    def test_labels_action_with_params(self):
        self._make_submissions()
        xform = XForm.objects.all()[0]
        pk = xform.id
        dataid = xform.instances.all()[0].id
        view = DataViewSet.as_view({
            'get': 'labels'
        })

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=pk, dataid=dataid, label='hello')
        self.assertEqual(response.status_code, 200)

    def test_data_list_filter_by_user(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        formid = self.xform.pk
        bobs_data = _data_list(formid)[0]

        previous_user = self.user
        self._create_user_and_login('alice', 'alice')
        self.assertEqual(self.user.username, 'alice')
        self.assertNotEqual(previous_user, self.user)

        ReadOnlyRole.add(self.user, self.xform)

        # publish alice's form
        self._publish_transportation_form()

        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        formid = self.xform.pk
        alice_data = _data_list(formid)[0]

        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        # should be both bob's and alice's form
        self.assertEqual(sorted(response.data),
                         sorted([bobs_data, alice_data]))

        # apply filter, see only bob's forms
        request = self.factory.get('/', data={'owner': 'bob'}, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [bobs_data])

        # apply filter, see only alice's forms
        request = self.factory.get('/', data={'owner': 'alice'}, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [alice_data])

        # apply filter, see a non existent user
        request = self.factory.get('/', data={'owner': 'noone'}, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_get_enketo_edit_url(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'enketo'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by('id')[0].pk

        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get('Cache-Control'), None)
        # add data check
        self.assertEqual(
            response.data,
            {'detail': 'return_url not provided.'})

        request = self.factory.get(
            '/',
            data={'return_url': "http://test.io/test_url"}, **self.extra)

        with HTTMock(enketo_mock):
            response = view(request, pk=formid, dataid=dataid)
            self.assertEqual(
                response.data['url'],
                "https://hmh2a.enketo.ona.io")

    def test_get_form_public_data(self):
        self._make_submissions()
        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/')
        formid = self.xform.pk
        response = view(request, pk=formid)

        # data not found for anonymous access to private data
        self.assertEqual(response.status_code, 404)
        self.xform.shared_data = True
        self.xform.save()

        # access to a public data as anon
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = self.xform.instances.all().order_by('id')[0].pk
        data = _data_instance(dataid)
        self.assertDictContainsSubset(data, sorted(response.data)[0])

        # access to a public data as other user
        self._create_user_and_login('alice', 'alice')
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = self.xform.instances.all().order_by('id')[0].pk
        data = _data_instance(dataid)
        self.assertDictContainsSubset(data, sorted(response.data)[0])

    def test_same_submission_with_different_attachments(self):
        self._submit_transport_instance_w_attachment()

        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)

        dataid = self.xform.instances.all().order_by('id')[0].pk

        data = {
            u'_bamboo_dataset_id': u'',
            u'_attachments': [{
                'download_url': get_attachment_url(self.attachment),
                'small_download_url':
                get_attachment_url(self.attachment, 'small'),
                'medium_download_url':
                get_attachment_url(self.attachment, 'medium'),
                u'mimetype': self.attachment.mimetype,
                u'instance': self.attachment.instance.pk,
                u'filename': self.attachment.media_file.name,
                u'id': self.attachment.pk,
                u'xform': self.xform.id}
            ],
            u'_geolocation': [None, None],
            u'_xform_id_string': u'transportation_2011_07_25',
            u'transport/available_transportation_types_to_referral_facility':
            u'none',
            u'_status': u'submitted_via_web',
            u'_id': dataid
        }
        self.assertDictContainsSubset(data, sorted(response.data)[0])

        patch_value = 'onadata.libs.utils.logger_tools.get_filtered_instances'
        with patch(patch_value) as get_filtered_instances:
            get_filtered_instances.return_value = Instance.objects.filter(
                uuid='#doesnotexist')
            s = self.surveys[0]
            media_file = "1442323232322.jpg"
            self._make_submission_w_attachment(os.path.join(
                self.this_directory, 'fixtures',
                'transportation', 'instances', s, s + '.xml'),
                os.path.join(self.this_directory, 'fixtures',
                             'transportation', 'instances', s, media_file))
            self.attachment = Attachment.objects.last()
            self.attachment_media_file = self.attachment.media_file

            data['_attachments'] = data.get('_attachments') + [{
                'download_url': get_attachment_url(self.attachment),
                'small_download_url':
                get_attachment_url(self.attachment, 'small'),
                'medium_download_url':
                get_attachment_url(self.attachment, 'medium'),
                u'mimetype': self.attachment.mimetype,
                u'instance': self.attachment.instance.pk,
                u'filename': self.attachment.media_file.name,
                u'id': self.attachment.pk,
                u'xform': self.xform.id
            }]
            response = view(request, pk=formid)

            self.assertDictContainsSubset(data, sorted(response.data)[0])
            self.assertEqual(response.status_code, 200)

    def test_data_w_attachment(self):
        self._submit_transport_instance_w_attachment()

        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        formid = self.xform.pk
        data = _data_list(formid)
        self.assertEqual(response.data, data)
        response = view(request, pk=formid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertTrue(self.xform.instances.count())
        dataid = self.xform.instances.all().order_by('id')[0].pk

        data = {
            u'_bamboo_dataset_id': u'',
            u'_attachments': [{
                'download_url': get_attachment_url(self.attachment),
                'small_download_url':
                get_attachment_url(self.attachment, 'small'),
                'medium_download_url':
                get_attachment_url(self.attachment, 'medium'),
                u'mimetype': self.attachment.mimetype,
                u'instance': self.attachment.instance.pk,
                u'filename': self.attachment.media_file.name,
                u'id': self.attachment.pk,
                u'xform': self.xform.id}
            ],
            u'_geolocation': [None, None],
            u'_xform_id_string': u'transportation_2011_07_25',
            u'transport/available_transportation_types_to_referral_facility':
            u'none',
            u'_status': u'submitted_via_web',
            u'_id': dataid
        }
        self.assertDictContainsSubset(data, sorted(response.data)[0])

        data = {
            u'_xform_id_string': u'transportation_2011_07_25',
            u'transport/available_transportation_types_to_referral_facility':
            u'none',
            u'_submitted_by': u'bob',
        }
        view = DataViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid, dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, dict)
        self.assertDictContainsSubset(data, response.data)

    def test_delete_submission(self):
        self._make_submissions()
        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by('id')[0].pk
        view = DataViewSet.as_view({
            'delete': 'destroy',
            'get': 'list'
        })

        # 4 submissions
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 4)

        request = self.factory.delete('/', **self.extra)
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)

        # remaining 3 submissions
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 3)

        self._create_user_and_login(username='alice', password='alice')
        # Managers can delete
        role.ManagerRole.add(self.user, self.xform)
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        request = self.factory.delete('/', **self.extra)
        dataid = self.xform.instances.filter(deleted_at=None)\
            .order_by('id')[0].pk
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)

        # remaining 3 submissions
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 2)

    def test_delete_submission_inactive_form(self):
        self._make_submissions()
        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by('id')[0].pk
        view = DataViewSet.as_view({
            'delete': 'destroy',
        })

        request = self.factory.delete('/', **self.extra)
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)

        # make form inactive
        self.xform.downloadable = False
        self.xform.save()

        dataid = self.xform.instances.filter(deleted_at=None)\
            .order_by('id')[0].pk

        request = self.factory.delete('/', **self.extra)
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 400)

    def test_delete_submission_by_editor(self):
        self._make_submissions()
        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by('id')[0].pk
        view = DataViewSet.as_view({
            'delete': 'destroy',
            'get': 'list'
        })

        # 4 submissions
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 4)

        self._create_user_and_login(username='alice', password='alice')

        # Editor can delete submission
        role.EditorRole.add(self.user, self.xform)
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        request = self.factory.delete('/', **self.extra)
        dataid = self.xform.instances.filter(deleted_at=None)\
            .order_by('id')[0].pk
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)

        # remaining 3 submissions
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 3)

    def test_delete_submission_by_owner(self):
        self._make_submissions()
        formid = self.xform.pk
        dataid = self.xform.instances.all().order_by('id')[0].pk
        view = DataViewSet.as_view({
            'delete': 'destroy',
            'get': 'list'
        })

        # 4 submissions
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 4)

        self._create_user_and_login(username='alice', password='alice')

        # Owner can delete submission
        role.OwnerRole.add(self.user, self.xform)
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        request = self.factory.delete('/', **self.extra)
        dataid = self.xform.instances.filter(deleted_at=None)\
            .order_by('id')[0].pk
        response = view(request, pk=formid, dataid=dataid)

        self.assertEqual(response.status_code, 204)

        # remaining 3 submissions
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 3)

    def test_geojson_format(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by('id')[0].pk

        view = DataViewSet.as_view({'get': 'retrieve'})
        data_get = {
            "fields": 'today'
        }
        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, dataid=dataid,
                        format='geojson')

        self.assertEqual(response.status_code, 200)

        test_geo = {
            'type': 'Feature',
            'geometry': {
                u'type': u'GeometryCollection',
                u'geometries': [{
                    u'type': u'Point',
                    u'coordinates': [
                        36.787219,
                        -1.294197
                    ]
                }
                ]
            },
            'properties': {
                'id': dataid,
                'xform': self.xform.pk,
                'today': '2015-01-15'
            }
        }

        self.assertEqual(response.data, test_geo)

        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format='geojson')
        instances = self.xform.instances.all()
        data = {
            'type': 'FeatureCollection',
            'features': [
                {
                    'type': 'Feature',
                    'geometry': {
                        u'type': u'GeometryCollection',
                        u'geometries': [{
                            u'type': u'Point',
                            u'coordinates': [
                                36.787219,
                                -1.294197
                            ]
                        }
                        ]
                    },
                    'properties': {
                        'id': instances[0].pk,
                        'xform': self.xform.pk,
                        'today': '2015-01-15'
                    }
                },
                {
                    'type': 'Feature',
                    'geometry': {
                        u'type': u'GeometryCollection',
                        u'geometries': [{
                            u'type': u'Point',
                            u'coordinates': [
                                36.787219,
                                -1.294197
                            ]
                        }
                        ]
                    },
                    'properties': {
                        'id': instances[1].pk,
                        'xform': self.xform.pk,
                        'today': '2015-01-15'
                    }
                },
                {
                    'type': 'Feature',
                    'geometry': {
                        u'type': u'GeometryCollection',
                        u'geometries': [{
                            u'type': u'Point',
                            u'coordinates': [
                                36.787219,
                                -1.294197
                            ]
                        }
                        ]
                    },
                    'properties': {
                        'id': instances[2].pk,
                        'xform': self.xform.pk,
                        'today': '2015-01-15'
                    }
                },
                {
                    'type': 'Feature',
                    'geometry': {
                        u'type': u'GeometryCollection',
                        u'geometries': [{
                            u'type': u'Point',
                            u'coordinates': [
                                36.787219,
                                -1.294197
                            ]
                        }
                        ]
                    },
                    'properties': {
                        'id': instances[3].pk,
                        'xform': self.xform.pk,
                        'today': '2015-01-15'
                    }
                }
            ]
        }
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

    def test_geojson_geofield(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by('id')[0].pk

        data_get = {
            "geo_field": 'location',
            "fields": 'today'
        }

        view = DataViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, dataid=dataid,
                        format='geojson')

        self.assertEqual(response.status_code, 200)
        test_loc = geojson.Feature(
            geometry=geojson.GeometryCollection([
                geojson.Point((36.787219, -1.294197))]),
            properties={
                'xform': self.xform.pk,
                'id': dataid,
                u'today': '2015-01-15'
            }
        )
        if 'id' in test_loc:
            test_loc.pop('id')

        self.assertEqual(response.data, test_loc)

        view = DataViewSet.as_view({'get': 'list'})

        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format='geojson')

        self.assertEqual(response.status_code, 200)
        self.assertEquals(response.data['type'], 'FeatureCollection')
        self.assertEquals(len(response.data['features']), 4)
        self.assertEquals(response.data['features'][0]['type'], 'Feature')
        self.assertEquals(
            response.data['features'][0]['geometry']['geometries'][0]['type'],
            'Point'
        )

    def test_geojson_linestring(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by('id')[0].pk

        data_get = {
            "geo_field": 'path',
            "fields": 'today,path'
        }

        view = DataViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, dataid=dataid,
                        format='geojson')

        self.assertEqual(response.status_code, 200)

        self.assertEquals(response.data['type'], 'Feature')
        self.assertEquals(len(response.data['geometry']['coordinates']), 5)
        self.assertIn('path', response.data['properties'])
        self.assertEquals(response.data['geometry']['type'], 'LineString')

        view = DataViewSet.as_view({'get': 'list'})

        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format='geojson')

        self.assertEqual(response.status_code, 200)
        self.assertEquals(response.data['type'], 'FeatureCollection')
        self.assertEquals(len(response.data['features']), 4)
        self.assertEquals(response.data['features'][0]['type'], 'Feature')
        self.assertEquals(response.data['features'][0]['geometry']['type'],
                          'LineString')

    def test_geojson_polygon(self):
        self._publish_submit_geojson()

        dataid = self.xform.instances.all().order_by('id')[0].pk

        data_get = {
            "geo_field": 'shape',
            "fields": 'today,shape'
        }

        view = DataViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, dataid=dataid,
                        format='geojson')

        self.assertEqual(response.status_code, 200)

        self.assertEquals(response.data['type'], 'Feature')
        self.assertEquals(len(response.data['geometry']['coordinates'][0]), 6)
        self.assertIn('shape', response.data['properties'])
        self.assertEquals(response.data['geometry']['type'], 'Polygon')

        view = DataViewSet.as_view({'get': 'list'})

        request = self.factory.get('/', data=data_get, **self.extra)
        response = view(request, pk=self.xform.pk, format='geojson')

        self.assertEqual(response.status_code, 200)
        self.assertEquals(response.data['type'], 'FeatureCollection')
        self.assertEquals(len(response.data['features']), 4)
        self.assertEquals(response.data['features'][0]['type'], 'Feature')
        self.assertEquals(response.data['features'][0]['geometry']['type'],
                          'Polygon')

    def test_data_in_public_project(self):
        self._make_submissions()

        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        with HTTMock(enketo_preview_url_mock, enketo_mock):
            response = view(request, pk=formid)
            self.assertEquals(response.status_code, 200)
            self.assertEqual(len(response.data), 4)
            # get project id
            projectid = self.xform.project.pk

            view = ProjectViewSet.as_view({
                'put': 'update'
            })

            data = {'public': True,
                    'name': 'test project',
                    'owner': 'http://testserver/api/v1/users/%s'
                    % self.user.username}
            request = self.factory.put('/', data=data, **self.extra)
            response = view(request, pk=projectid)

            self.assertEqual(response.status_code, 200)
            self.xform.reload()
            self.assertEqual(self.xform.shared, True)

            # anonymous user
            view = DataViewSet.as_view({'get': 'list'})
            request = self.factory.get('/')
            formid = self.xform.pk
            response = view(request, pk=formid)

            self.assertEquals(response.status_code, 200)
            self.assertEqual(len(response.data), 4)

    def test_data_diff_version(self):
        self._make_submissions()
        # update the form version
        self.xform.version = "212121211"
        self.xform.save()

        # make more submission after form update
        surveys = ['transport_2011-07-25_19-05-36-edited']
        main_directory = os.path.dirname(main_tests.__file__)
        paths = [os.path.join(main_directory, 'fixtures', 'transportation',
                              'instances_w_uuid', s, s + '.xml')
                 for s in surveys]

        auth = DigestAuth('bob', 'bob')
        for path in paths:
            self._make_submission(path, None, None, auth=auth)

        data_view = DataViewSet.as_view({'get': 'list'})

        request = self.factory.get('/', **self.extra)

        response = data_view(request, pk=self.xform.pk)

        self.assertEquals(len(response.data), 5)

        query_str = '{"_version": "2014111"}'
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = data_view(request, pk=self.xform.pk)

        self.assertEquals(len(response.data), 4)

        query_str = '{"_version": "212121211"}'
        request = self.factory.get('/?query=%s' % query_str, **self.extra)
        response = data_view(request, pk=self.xform.pk)

        self.assertEquals(len(response.data), 1)

    def test_last_modified_on_data_list_response(self):
        self._make_submissions()

        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)

        self.assertEquals(response.status_code, 200)
        self.assertEqual(response.get('Cache-Control'), 'max-age=60')

        self.assertTrue(response.has_header('ETag'))
        etag_value = response.get('ETag')

        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)

        self.assertEquals(response.status_code, 200)

        self.assertEquals(etag_value, response.get('ETag'))

        # delete one submission
        inst = Instance.objects.filter(xform=self.xform)
        inst[0].delete()

        view = DataViewSet.as_view({'get': 'list'})
        request = self.factory.get('/', **self.extra)
        formid = self.xform.pk
        response = view(request, pk=formid)

        self.assertEquals(response.status_code, 200)
        self.assertNotEquals(etag_value, response.get('ETag'))

    def test_submission_history(self):
        """Test submission json includes has_history key"""
        # create form
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/tutorial.xls"
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        # create submission
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )

        self._make_submission(xml_submission_file_path)
        instance = Instance.objects.last()
        instance_count = Instance.objects.count()
        instance_history_count = InstanceHistory.objects.count()

        # edit submission
        xml_edit_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml"
        )
        xml_edit_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml"
        )
        client = DigestClient()
        client.set_authorization('bob', 'bob', 'Digest')
        self._make_submission(xml_edit_submission_file_path, client=client)

        self.assertEqual(self.response.status_code, 201)

        self.assertEqual(instance_count, Instance.objects.count())
        self.assertEqual(instance_history_count + 1,
                         InstanceHistory.objects.count())

        # retrieve submission history
        view = DataViewSet.as_view({'get': 'history'})
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.xform.pk, dataid=instance.id)
        self.assertEqual(response.status_code, 200)

        history_instance = InstanceHistory.objects.last()
        instance = Instance.objects.last()

        self.assertDictEqual(response.data[0], history_instance.json)
        self.assertNotEqual(response.data[0], instance.json)

    def test_submission_history_not_digit(self):
        """Test submission json includes has_history key"""
        # retrieve submission history
        view = DataViewSet.as_view({'get': 'history'})
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.xform.pk, dataid="boo!")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'],
                         u'Data ID should be an integer')

        history_instance_count = InstanceHistory.objects.count()
        self.assertEqual(history_instance_count, 0)

    def test_data_endpoint_etag_on_submission_edit(self):
        """Test etags get updated on submission edit"""
        # create form
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/tutorial.xls"
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        def _data_response():
            view = DataViewSet.as_view({'get': 'list'})
            request = self.factory.get('/', **self.extra)
            response = view(request, pk=self.xform.pk)
            self.assertEqual(response.status_code, 200)

            return response

        response = _data_response()
        etag_data = response['Etag']

        # create submission
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )

        self._make_submission(xml_submission_file_path)
        response = _data_response()
        self.assertNotEqual(etag_data, response['Etag'])
        etag_data = response['Etag']

        # edit submission
        xml_edit_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited.xml"
        )
        client = DigestClient()
        client.set_authorization('bob', 'bob', 'Digest')
        self._make_submission(xml_edit_submission_file_path, client=client)
        self.assertEqual(self.response.status_code, 201)

        response = _data_response()
        self.assertNotEqual(etag_data, response['Etag'])
        etag_data = response['Etag']
        response = _data_response()
        self.assertEqual(etag_data, response['Etag'])

    def test_submission_edit_w_blank_field(self):
        """Test submission json includes has_history key"""
        # create form
        xls_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../fixtures/tutorial/tutorial.xls"
        )
        self._publish_xls_file_and_set_xform(xls_file_path)

        # create submission
        xml_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid.xml"
        )

        self._make_submission(xml_submission_file_path)
        instance = Instance.objects.last()
        instance_count = Instance.objects.count()

        # edit submission
        xml_edit_submission_file_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "fixtures", "tutorial", "instances",
            "tutorial_2012-06-27_11-27-53_w_uuid_edited_blank.xml"
        )
        client = DigestClient()
        client.set_authorization('bob', 'bob', 'Digest')
        self._make_submission(xml_edit_submission_file_path, client=client)

        self.assertEqual(self.response.status_code, 201)

        self.assertEqual(instance_count, Instance.objects.count())

        # retrieve submission history
        view = DataViewSet.as_view({'get': 'retrieve'})
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.xform.pk, dataid=instance.id)

        self.assertEqual(instance_count, Instance.objects.count())
        self.assertNotIn('name', response.data)


class TestOSM(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._login_user_and_profile()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

    def test_data_retrieve_instance_osm_format(self):
        filenames = [
            'OSMWay234134797.osm',
            'OSMWay34298972.osm',
        ]
        osm_fixtures_dir = os.path.realpath(os.path.join(
            os.path.dirname(__file__), '..', 'fixtures', 'osm'))
        paths = [
            os.path.join(osm_fixtures_dir, filename)
            for filename in filenames]
        xlsform_path = os.path.join(osm_fixtures_dir, 'osm.xlsx')
        combined_osm_path = os.path.join(osm_fixtures_dir, 'combined.osm')
        self._publish_xls_form_to_project(xlsform_path=xlsform_path)
        submission_path = os.path.join(osm_fixtures_dir, 'instance_a.xml')
        files = [open(path) for path in paths]
        count = Attachment.objects.filter(extension='osm').count()
        self._make_submission(submission_path, media_file=files)
        self.assertTrue(
            Attachment.objects.filter(extension='osm').count() > count)

        formid = self.xform.pk
        dataid = self.xform.instances.latest('date_created').pk
        request = self.factory.get('/', **self.extra)

        # look at the data/[pk]/[dataid].osm endpoint
        view = DataViewSet.as_view({'get': 'list'})
        response1 = view(request, pk=formid, format='osm')
        self.assertEqual(response1.status_code, 200)

        # look at the data/[pk]/[dataid].osm endpoint
        view = DataViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=formid, dataid=dataid, format='osm')
        self.assertEqual(response.status_code, 200)
        with open(combined_osm_path) as f:
            osm = f.read()
            response.render()
            self.assertMultiLineEqual(response.content.strip(), osm.strip())

            # look at the data/[pk].osm endpoint
            view = DataViewSet.as_view({'get': 'list'})
            response = view(request, pk=formid, format='osm')
            self.assertEqual(response.status_code, 200)
            response.render()
            response1.render()
            self.assertMultiLineEqual(response1.content.strip(), osm.strip())
            self.assertMultiLineEqual(response.content.strip(), osm.strip())

        # filter using value that exists
        request = self.factory.get(
            '/',
            data={"query": u'{"osm_road": "OSMWay234134797.osm"}'},
            **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 1)

        # filter using value that doesn't exists
        request = self.factory.get(
            '/',
            data={"query": u'{"osm_road": "OSMWay123456789.osm"}'},
            **self.extra)
        response = view(request, pk=formid)
        self.assertEqual(len(response.data), 0)
