# -*- coding: utf-8 -*-
"""
OpenData tests.
"""
import os
import json

from django.test import RequestFactory
from django.utils.dateparse import parse_datetime
from django.contrib.auth.models import User

from onadata.apps.logger.models import OpenData, Instance
from onadata.apps.logger.models.open_data import get_or_create_opendata
from onadata.apps.api.viewsets.open_data_viewset import (
    OpenDataViewSet, replace_special_characters_with_underscores
)
from onadata.apps.main.tests.test_base import TestBase


def streaming_data(response):
    return json.loads(u''.join(
        [i.decode('utf-8') for i in response.streaming_content]))


class TestOpenDataViewSet(TestBase):

    def setUp(self):
        super(TestOpenDataViewSet, self).setUp()
        self._create_user_and_login()
        self._publish_transportation_form()
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}

        self.view = OpenDataViewSet.as_view({
            'post': 'create',
            'patch': 'partial_update',
            'delete': 'destroy',
            'get': 'data'
        })

    def test_replace_special_characters_with_underscores(self):
        data = ['john_doe[3]/_visual-studio-code']
        self.assertEqual(
            replace_special_characters_with_underscores(
                data,
            ),
            ['john_doe_3___visual_studio_code']
        )

    def get_open_data_object(self):
        return get_or_create_opendata(self.xform)[0]

    def test_create_open_data_object_with_valid_fields(self):
        initial_count = OpenData.objects.count()
        request = self.factory.post('/', data={})
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        data = {
            'object_id': self.xform.id,
            'data_type': 'xform',
            'name': self.xform.id_string
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(initial_count + 1, OpenData.objects.count())

    def test_create_open_data_object_with_invalid_fields(self):
        data = {
            'data_type': 'xform',
            'name': self.xform.id_string
        }

        data.update({'object_id': 'sup'})
        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {'object_id': [u'A valid integer is required.']}
        )

        # check for xform with non-existent xform id (object_id)
        data.update({'object_id': 1000})
        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 404)

        data.pop('object_id')
        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            ['Fields object_id, data_type and name are required.']
        )

    def test_get_data_using_uuid(self):
        self._make_submissions()
        self.view = OpenDataViewSet.as_view({
            'get': 'data'
        })
        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid
        request = self.factory.get('/', **self.extra)
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        # cast generator response to list so that we can get the response count
        self.assertEqual(len(streaming_data(response)), 4)

    def test_tableau_get_group_data(self):
        """
        Test tableau unpacks group data successfully
        """
        self._make_submissions()
        self.view = OpenDataViewSet.as_view({
            'get': 'data'
        })
        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid

        request = self.factory.get('/', **self.extra)
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        # cast generator response to list for easy manipulation
        row_data = streaming_data(response)
        self.assertEqual(len(row_data), 4)
        # Confirm group data is available in tableau
        self.assertEqual(
            row_data[3]['transport_available_'
                        'transportation_types_to_referral_facility'],  # noqa
            'taxi other')
        self.assertEqual(
            row_data[3][
                'transport_loop_over_transport_'
                'types_frequency_taxi_frequency_to_referral_facility'],  # noqa
            'daily')

    def test_get_data_with_pagination(self):
        self._make_submissions()
        self.view = OpenDataViewSet.as_view({
            'get': 'data'
        })
        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid

        # no pagination
        request = self.factory.get('/', **self.extra)
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        # cast generator response to list so that we can get the response count
        self.assertEqual(len(streaming_data(response)), 4)

        # with pagination
        request = self.factory.get('/', {'page_size': 3}, **self.extra)
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        # cast generator response to list so that we can get the response count
        self.assertEqual(len(streaming_data(response)), 3)

        # with count
        request = self.factory.get('/', {'count': 1}, **self.extra)
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'count': 4})

    def test_get_data_using_uuid_and_greater_than_query_param(self):
        self._make_submissions()
        self.view = OpenDataViewSet.as_view({
            'get': 'data'
        })
        first_instance = Instance.objects.first()
        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid

        request = self.factory.get(
            '/', {'gt_id': first_instance.id}, **self.extra
        )
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        # cast generator response to list so that we can get the response count
        self.assertEqual(len(streaming_data(response)), 3)

    def test_update_open_data_with_valid_fields_and_data(self):
        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid
        data = {'name': 'updated_name'}

        request = self.factory.patch(
            '/',
            data=json.dumps(data),
            content_type="application/json"
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.patch(
            '/',
            data=json.dumps(data),
            content_type="application/json",
            **self.extra
        )
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)

        _open_data = OpenData.objects.last()
        self.assertEqual(_open_data.name, 'updated_name')

    def test_delete_open_data_object(self):
        inital_count = OpenData.objects.count()
        _open_data = self.get_open_data_object()
        self.assertEqual(OpenData.objects.count(), inital_count + 1)

        request = self.factory.delete('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.delete('/', **self.extra)
        response = self.view(request, uuid=_open_data.uuid)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(OpenData.objects.count(), inital_count)

    def test_column_headers_endpoint(self):
        self.view = OpenDataViewSet.as_view({
            'get': 'schema'
        })

        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid
        request = self.factory.get('/', **self.extra)
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(
            ['column_headers', 'connection_name', 'table_alias'],
            sorted(list(response.data))
        )
        connection_name = u"%s_%s" % (
            self.xform.project_id,
            self.xform.id_string
        )
        self.assertEqual(connection_name, response.data.get('connection_name'))
        self.assertEqual(
            u'transportation_2011_07_25',
            response.data.get('table_alias')
        )

        _id_datatype = [
            a.get('dataType')
            for a in response.data['column_headers']
            if a.get('id') == '_id'][0]
        self.assertEqual(_id_datatype, 'int')

    def test_uuid_endpoint(self):
        self.view = OpenDataViewSet.as_view({
            'get': 'uuid'
        })

        request = self.factory.get('/')
        response = self.view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.get('/', **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data, "Query params data_type and object_id are required"
        )

        data = {
            'object_id': self.xform.id,
            'data_type': 'non_clazz',
        }
        request = self.factory.get('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 404)

        _open_data = self.get_open_data_object()
        data = {
            'object_id': self.xform.id,
            'data_type': 'xform',
        }

        # check authenticated user without permission to the object gets
        # 403 response.
        anonymous_user = User.objects.get(username='AnonymousUser')
        anonymous_user_auth = {
            'HTTP_AUTHORIZATION': 'Token %s' % anonymous_user.auth_token
        }
        request = self.factory.get('/', data=data, **anonymous_user_auth)
        response = self.view(request)
        self.assertEqual(response.status_code, 403)

        request = self.factory.get('/', data=data, **self.extra)
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'uuid': _open_data.uuid})

    def test_response_if_open_data_object_is_inactive(self):
        _open_data = self.get_open_data_object()
        uuid = _open_data.uuid
        _open_data.active = False
        _open_data.save()

        request = self.factory.get('/', **self.extra)
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 404)


class TestOpenData(TestBase):
    """
    Test tableau unpacks repeat data successfully
    """

    def setUp(self):
        super(TestOpenData, self).setUp()
        self._create_user_and_login()
        self._submission_time = parse_datetime('2020-02-18 15:54:01Z')
        self.fixture_dir = os.path.join(
            self.this_directory, 'fixtures', 'csv_export')
        path = os.path.join(self.fixture_dir, 'tutorial_w_repeats.xls')
        self._publish_xls_file_and_set_xform(path)
        path = os.path.join(self.fixture_dir, 'tutorial_w_repeats.xml')
        self.factory = RequestFactory()
        self.extra = {
            'HTTP_AUTHORIZATION': 'Token %s' % self.user.auth_token}
        self._make_submission(
            path, forced_submission_time=self._submission_time)

        self.view = OpenDataViewSet.as_view({
            'post': 'create',
            'patch': 'partial_update',
            'delete': 'destroy',
            'get': 'data'
        })

    def test_tableau_data_fetch(self):  # pylint: disable=invalid-name
        """
        Test that the row headers generated
        match the column headers for the same form
        """
        self.view = OpenDataViewSet.as_view({
            'get': 'schema'
        })

        _open_data = get_or_create_opendata(self.xform)
        uuid = _open_data[0].uuid
        request1 = self.factory.get('/', **self.extra)
        response1 = self.view(request1, uuid=uuid)
        self.assertEqual(response1.status_code, 200)
        self.assertListEqual(
            ['column_headers', 'connection_name', 'table_alias'],
            sorted(list(response1.data))
        )

        expected_column_headers = [
            '_gps_altitude',
            '_gps_latitude',
            '_gps_longitude',
            '_gps_precision',
            '_id',
            'age',
            'children_1__childs_age',
            'children_1__childs_name',
            'children_2__childs_age',
            'children_2__childs_name',
            'children_3__childs_age',
            'children_3__childs_name',
            'children_4__childs_age',
            'children_4__childs_name',
            'gps',
            'has_children',
            'meta_instanceID',
            'name',
            'picture',
            'web_browsers_chrome',
            'web_browsers_firefox',
            'web_browsers_ie',
            'web_browsers_safari'
        ]

        self.view = OpenDataViewSet.as_view({
            'get': 'data'
        })
        request2 = self.factory.get('/', **self.extra)
        response2 = self.view(request2, uuid=uuid)
        self.assertEqual(response2.status_code, 200)
        # cast generator response to list for easy manipulation
        row_data = streaming_data(response2)
        row_data_fields = [k for k in row_data[0].keys()]
        row_data_fields.sort()
        self.assertEqual(row_data_fields, expected_column_headers)

    def test_tableau_get_repeat_data(self):
        """
        Test that data received from repeats is flattened
        and the tablau data endpoint returns accurate data
        for this question type
        """
        self.view = OpenDataViewSet.as_view({
            'get': 'data'
        })

        repeat_data = [
            {
                'children/childs_age': 12,
                'children/childs_name': 'Tom'
            },
            {
                'children/childs_age': 5,
                'children/childs_name': 'Dick'
            }
        ]

        inst = Instance.objects.filter(
            xform=self.xform).first()
        self.assertEqual(inst.json['children'], repeat_data)

        _open_data = get_or_create_opendata(self.xform)
        uuid = _open_data[0].uuid
        request = self.factory.get('/', **self.extra)
        response = self.view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        # cast generator response to list for easy manipulation
        row_data = streaming_data(response)
        # Test that Tableau receives this data
        self.assertEqual(
            row_data[0]['children_1__childs_name'],
            'Tom')
        self.assertEqual(
            row_data[0]['children_2__childs_age'],
            5)
