# -*- coding: utf-8 -*-
"""
Test merged dataset functionality.
"""

import csv
import json
from cStringIO import StringIO

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.data_viewset import DataViewSet
from onadata.apps.api.viewsets.merged_xform_viewset import MergedXFormViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import Instance, MergedXForm

MD = """
| survey |
|        | type              | name  | label |
|        | select one fruits | fruit | Fruit |

| choices |
|         | list name | name   | label  |
|         | fruits    | orange | Orange |
|         | fruits    | mango  | Mango  |
"""


class TestMergedXFormViewSet(TestAbstractViewSet):
    """Test merged dataset functionality."""

    def _create_merged_dataset(self):
        view = MergedXFormViewSet.as_view({
            'post': 'create',
        })
        xform1 = self._publish_md(MD, self.user, id_string='a')
        xform2 = self._publish_md(MD, self.user, id_string='b')

        data = {
            'xforms': [
                "http://testserver.com/api/v1/forms/%s" % xform1.pk,
                "http://testserver.com/api/v1/forms/%s" % xform2.pk,
            ],
            'name':
            'Merged Dataset',
            'project':
            "http://testserver.com/api/v1/projects/%s" % self.project.pk,
        }
        # anonymous user
        request = self.factory.post('/', data=data)
        response = view(request)
        self.assertEqual(response.status_code, 401)

        request = self.factory.post('/', data=data, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 201)
        self.assertIn('id', response.data)
        self.assertIn('title', response.data)
        self.assertIn('xforms', response.data)

        return response.data

    def test_create_merged_dataset(self):
        """Test creating a merged dataset"""
        self._create_merged_dataset()

    def test_merged_datasets_list(self):
        """Test list endpoint of a merged dataset"""
        view = MergedXFormViewSet.as_view({
            'get': 'list',
        })
        request = self.factory.get('/')

        # Empty list when there are no merged datasets
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual([], response.data)

        # create a merged dataset
        merged_dataset = self._create_merged_dataset()

        # Empty list for anonymous user
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual([], response.data)

        # A list containing the merged datasets for user bob
        request = self.factory.get('/', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertIn(merged_dataset, response.data)

        # merged dataset included in api/forms endpoint
        request = self.factory.get('/', **self.extra)
        view = XFormViewSet.as_view({'get': 'list'})
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 3)
        self.assertIn(merged_dataset['id'],
                      [d['formid'] for d in response.data])
        data = [
            _ for _ in response.data if _['formid'] == merged_dataset['id']
        ][0]
        self.assertIn('is_merged_dataset', data)
        self.assertTrue(data['is_merged_dataset'])

    def test_merged_datasets_retrieve(self):
        """Test retrieving a specific merged dataset"""
        merged_dataset = self._create_merged_dataset()
        merged_xform = MergedXForm.objects.get(pk=merged_dataset['id'])

        # make submission to form b
        form_b = merged_xform.xforms.all()[1]
        xml = '<data id="b"><fruit>mango</fruit></data>'
        Instance(xform=form_b, xml=xml).save()
        view = MergedXFormViewSet.as_view({
            'get': 'retrieve',
        })
        request = self.factory.get('/')

        # status_code is 404 when the pk doesn't exist
        response = view(request, pk=(1000 * merged_dataset['id']))
        self.assertEqual(response.status_code, 404)

        # status_code is 404 when: pk exists, user is not authenticated
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 404)

        # status_code is 200 when: pk exists, user is authenticated
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)

        # data has expected fields
        self.assertIn('id', response.data)
        self.assertIn('title', response.data)
        self.assertIn('xforms', response.data)
        self.assertEqual(response.data['num_of_submissions'], 1)

        # merged dataset should be available at api/forms/[pk] endpoint
        request = self.factory.get('/', **self.extra)
        view = XFormViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(merged_dataset['id'], response.data['formid'])
        self.assertIn('is_merged_dataset', response.data)
        self.assertTrue(response.data['is_merged_dataset'])
        self.assertEqual(response.data['num_of_submissions'], 1)

    def test_merged_datasets_form_json(self):
        """Test retrieving the XLSForm JSON of a merged dataset"""
        # create a merged dataset
        merged_dataset = self._create_merged_dataset()

        view = MergedXFormViewSet.as_view({'get': 'form'})
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=merged_dataset['id'], format='json')
        self.assertEqual(response.status_code, 200)

        response.render()
        self.assertEqual('application/json', response['Content-Type'])

        data = json.loads(response.content)
        self.assertIsInstance(data, dict)
        for key in ['children', 'id_string', 'name', 'default_language']:
            self.assertIn(key, data)

    def test_merged_datasets_form_xml(self):
        """Test retrieving the XLSForm XForm of a merged dataset"""
        # create a merged dataset
        merged_dataset = self._create_merged_dataset()

        view = MergedXFormViewSet.as_view({'get': 'form'})
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=merged_dataset['id'], format='xml')
        self.assertEqual(response.status_code, 200)

        response.render()
        self.assertEqual('text/xml; charset=utf-8', response['Content-Type'])

    def test_merged_datasets_data(self):
        """Test retrieving data of a merged dataset"""
        merged_dataset = self._create_merged_dataset()
        request = self.factory.get('/', **self.extra)
        view = MergedXFormViewSet.as_view({'get': 'data'})
        merged_xform = MergedXForm.objects.get(pk=merged_dataset['id'])
        detail_view = MergedXFormViewSet.as_view({
            'get': 'retrieve',
        })

        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # check num_of_submissions
        response = detail_view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['num_of_submissions'], 0)

        # make submission to form a
        form_a = merged_xform.xforms.all()[0]
        xml = '<data id="a"><fruit>orange</fruit></data>'
        Instance(xform=form_a, xml=xml).save()
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        fruit = [d['fruit'] for d in response.data]
        expected_fruit = ['orange']
        self.assertEqual(fruit, expected_fruit)

        # check num_of_submissions
        response = detail_view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['num_of_submissions'], 1)

        # make submission to form b
        form_b = merged_xform.xforms.all()[1]
        xml = '<data id="b"><fruit>mango</fruit></data>'
        Instance(xform=form_b, xml=xml).save()
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        fruit = [d['fruit'] for d in response.data]
        expected_fruit = ['orange', 'mango']
        self.assertEqual(fruit, expected_fruit)

        # check num_of_submissions
        response = detail_view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['num_of_submissions'], 2)

    def test_md_data_viewset(self):
        """Test retrieving data of a merged dataset at the /data endpoint"""
        merged_dataset = self._create_merged_dataset()
        merged_xform = MergedXForm.objects.get(pk=merged_dataset['id'])
        request = self.factory.get('/', **self.extra)
        data_view = DataViewSet.as_view({
            'get': 'list',
        })

        # make submission to form a
        form_a = merged_xform.xforms.all()[0]
        xml = '<data id="a"><fruit>orange</fruit></data>'
        Instance(xform=form_a, xml=xml).save()

        # DataViewSet /data/[pk] endpoint
        response = data_view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        fruit = [d['fruit'] for d in response.data]
        expected_fruit = ['orange']
        self.assertEqual(fruit, expected_fruit)

        # make submission to form b
        form_b = merged_xform.xforms.all()[1]
        xml = '<data id="b"><fruit>mango</fruit></data>'
        Instance(xform=form_b, xml=xml).save()

        # DataViewSet /data/[pk] endpoint
        response = data_view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        dataid = response.data[0]['_id']

        fruit = [d['fruit'] for d in response.data]
        expected_fruit = ['orange', 'mango']
        self.assertEqual(fruit, expected_fruit)

        # DataViewSet /data/[pk]/[dataid] endpoint
        data_view = DataViewSet.as_view({
            'get': 'retrieve',
        })
        response = data_view(request, pk=merged_dataset['id'], dataid=dataid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['fruit'], 'orange')

    def test_md_csv_export(self):
        """Test CSV export of a merged dataset"""
        merged_dataset = self._create_merged_dataset()
        merged_xform = MergedXForm.objects.get(pk=merged_dataset['id'])

        # make submission to form a
        form_a = merged_xform.xforms.all()[0]
        xml = '<data id="a"><fruit>orange</fruit></data>'
        Instance(xform=form_a, xml=xml).save()

        # make submission to form b
        form_b = merged_xform.xforms.all()[1]
        xml = '<data id="b"><fruit>mango</fruit></data>'
        Instance(xform=form_b, xml=xml).save()

        # merged dataset should be available at api/forms/[pk] endpoint
        request = self.factory.get('/', **self.extra)
        view = XFormViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=merged_dataset['id'], format='csv')
        self.assertEqual(response.status_code, 200)

        csv_file_obj = StringIO(u''.join(response.streaming_content))
        csv_reader = csv.reader(csv_file_obj)
        # jump over headers first
        headers = csv_reader.next()
        self.assertEqual(headers, [
            'fruit', 'meta/instanceID', '_uuid', '_submission_time', '_tags',
            '_notes', '_version', '_duration', '_submitted_by'
        ])
        row1 = csv_reader.next()
        self.assertEqual(row1[0], 'orange')
        row2 = csv_reader.next()
        self.assertEqual(row2[0], 'mango')
