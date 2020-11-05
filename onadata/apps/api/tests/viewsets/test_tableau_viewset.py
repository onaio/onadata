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
from onadata.apps.api.viewsets.tableau_viewset import TableauViewSet

from onadata.apps.main.tests.test_base import TestBase


def streaming_data(response):
    return json.loads(u''.join(
        [i.decode('utf-8') for i in response.streaming_content]))


class TestTableauViewSet(TestBase):

    def setUp(self):
        super(TestTableauViewSet, self).setUp()
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

        self.view = TableauViewSet.as_view({
            'post': 'create',
            'patch': 'partial_update',
            'delete': 'destroy',
            'get': 'data'
        })
    
    def get_open_data_object(self):
        return get_or_create_opendata(self.xform)[0]


    def test_tableau_data_and_fetch(self):  # pylint: disable=invalid-name
        """
        Test the schema and data endpoint and data returned by each.
        """
        self.view = TableauViewSet.as_view({
            'get': 'schema'
        })

        _open_data = get_or_create_opendata(self.xform)
        uuid = _open_data[0].uuid
        expected_schema = [
            {
                'table_alias': 'data',
                'connection_name': '1_tutorial_w_repeats',
                'column_headers': [
                    {
                        'id': '_id',
                        'dataType': 'int',
                        'alias': '_id'
                    },
                    {
                        'id': 'name',
                        'dataType': 'string',
                        'alias': 'name'
                    },
                    {
                        'id': 'age',
                        'dataType': 'int',
                        'alias': 'age'
                    },
                    {
                        'id': 'picture',
                        'dataType': 'string',
                        'alias': 'picture'
                    },
                    {
                        'id': 'has_children',
                        'dataType': 'string',
                        'alias': 'has_children'
                    },
                    {
                        'id': '_gps_latitude',
                        'dataType': 'string',
                        'alias': '_gps_latitude'
                    },
                    {
                        'id': '_gps_longitude',
                        'dataType': 'string',
                        'alias': '_gps_longitude'
                    },
                    {
                        'id': '_gps_altitude',
                        'dataType': 'string',
                        'alias': '_gps_altitude'
                    },
                    {
                        'id': '_gps_precision',
                        'dataType': 'string',
                        'alias': '_gps_precision'
                    },
                    {
                        'id': 'browsers_firefox',
                        'dataType': 'string',
                        'alias': 'browsers_firefox'
                    },
                    {
                        'id': 'browsers_chrome',
                        'dataType': 'string',
                        'alias': 'browsers_chrome'
                    },
                    {
                        'id': 'browsers_ie',
                        'dataType': 'string',
                        'alias': 'browsers_ie'
                    },
                    {
                        'id': 'browsers_safari',
                        'dataType': 'string',
                        'alias': 'browsers_safari'
                    },
                    {
                        'id': 'meta_instanceID',
                        'dataType': 'string',
                        'alias': 'meta_instanceID'
                    }
                ]
            },
            {
                'table_alias': 'children',
                'connection_name': '1_tutorial_w_repeats_children',
                'column_headers': [
                    {
                        'id': '_id',
                        'dataType': 'int',
                        'alias': '_id'
                    },
                    {
                        'id': '__parent_id',
                        'dataType': 'int',
                        'alias': '__parent_id'
                    },
                    {
                        'id': '__parent_table',
                        'dataType': 'string',
                        'alias': '__parent_table'
                    },
                    {
                        'id': 'childs_name',
                        'dataType': 'string',
                        'alias': 'childs_name'
                    },
                    {
                        'id': 'childs_age',
                        'dataType': 'int',
                        'alias': 'childs_age'
                    }
                    ]
                }]

        request1 = self.factory.get('/', **self.extra)
        response1 = self.view(request1, uuid=uuid)
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response1.data, expected_schema)
        # Test that multiple schemas are generated for each repeat
        self.assertEqual(len(response1.data), 2)
        self.assertListEqual(
            ['column_headers', 'connection_name', 'table_alias'],
            sorted(list(response1.data[0].keys()))
        )

        connection_name = u"%s_%s" % (
            self.xform.project_id,
            self.xform.id_string
        )
        self.assertEqual(connection_name, response1.data[0].get('connection_name'))
        # Test that the table alias field being sent to Tableau
        # for each schema contains the right table name
        self.assertEqual(
            u'data', response1.data[0].get('table_alias')
        )
        self.assertEqual(
            u'children', response1.data[1].get('table_alias')
        )

        _id_datatype = [
            a.get('dataType')
            for a in response1.data[0]['column_headers']
            if a.get('id') == '_id'][0]
        self.assertEqual(_id_datatype, 'int')

        expected_data = [
            {
                '_gps_altitude': '0.0',
                '_gps_latitude': '-1.2625621',
                '_gps_longitude': '36.7921711',
                '_gps_precision': '20.0',
                '_id': 1,
                'age': 25,
                'children': [{'__parent_id': 1,
                                '__parent_table': 'data',
                                '_id': 4,
                                'childs_age': 12,
                                'childs_name': 'Tom'},
                            {'__parent_id': 1,
                                '__parent_table': 'data',
                                '_id': 8,
                                'childs_age': 5,
                                'childs_name': 'Dick'}],
                'has_children': '1',
                'meta_instanceID': 'uuid:b31c6ac2-b8ca-4180-914f-c844fa10ed3b',
                'name': 'Bob'
            }]
        

        self.view = TableauViewSet.as_view({
            'get': 'data'
        })
        request2 = self.factory.get('/', **self.extra)
        response2 = self.view(request2, uuid=uuid)
        self.assertEqual(response2.status_code, 200)
        # cast generator response to list for easy manipulation
        row_data = streaming_data(response2)
        # Test to confirm that the repeat tables generated
        # are related to the main table
        self.assertEqual(
            row_data[0]['children'][0]['__parent_table'],
            response1.data[0]['table_alias'])
        self.assertEqual(row_data, expected_data)
