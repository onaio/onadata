# -*- coding: utf-8 -*-
"""
Test merged dataset functionality.
"""

import json

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
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
        view = MergedXFormViewSet.as_view({'post': 'create', })
        xform1 = self._publish_md(MD, self.user, id_string='a')
        xform2 = self._publish_md(MD, self.user, id_string='b')

        data = {
            'xforms': [
                "http://testserver.com/api/v1/forms/%s" % xform1.pk,
                "http://testserver.com/api/v1/forms/%s" % xform2.pk,
            ],
            'name': 'Merged Dataset',
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
        view = MergedXFormViewSet.as_view({'get': 'list', })
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

    def test_merged_datasets_retrieve(self):
        """Test retrieving a specific merged dataset"""
        merged_dataset = self._create_merged_dataset()
        view = MergedXFormViewSet.as_view({'get': 'retrieve', })
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

        # merged dataset should be available at api/forms/[pk] endpoint
        request = self.factory.get('/', **self.extra)
        view = XFormViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(merged_dataset['id'], response.data['formid'])
        self.assertIn('is_merged_dataset', response.data)
        self.assertTrue(response.data['is_merged_dataset'])

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
        for key in ['children', 'id_string', 'name', 'default_language', 'num_of_submissions']:
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

        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # make submission to form a
        form_a = merged_xform.xforms.all()[0]
        xml = '<data id="a"><fruits>orange</fruits></data>'
        Instance(xform=form_a, xml=xml).save()
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        fruits = [d['fruits'] for d in response.data]
        expected_fruits = ['orange']
        self.assertEqual(fruits, expected_fruits)

        # make submission to form b
        form_b = merged_xform.xforms.all()[1]
        xml = '<data id="b"><fruits>mango</fruits></data>'
        Instance(xform=form_b, xml=xml).save()
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        fruits = [d['fruits'] for d in response.data]
        expected_fruits = ['orange', 'mango']
        self.assertEqual(fruits, expected_fruits)

    def test_update_merged_dataset(self):
        self.assertEqual(False, 'update' in dir(MergedXFormViewSet))
