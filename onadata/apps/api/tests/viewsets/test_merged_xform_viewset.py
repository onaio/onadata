# -*- coding: utf-8 -*-
"""
Test merged dataset functionality.
"""
from __future__ import unicode_literals

import csv
import json
from io import StringIO

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.charts_viewset import ChartsViewSet
from onadata.apps.api.viewsets.data_viewset import DataViewSet
from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet
from onadata.apps.api.viewsets.merged_xform_viewset import MergedXFormViewSet
from onadata.apps.api.viewsets.open_data_viewset import OpenDataViewSet
from onadata.apps.api.viewsets.xform_list_viewset import XFormListViewSet
from onadata.apps.api.viewsets.xform_viewset import XFormViewSet
from onadata.apps.logger.models import Instance, MergedXForm, XForm
from onadata.apps.logger.models.instance import FormIsMergedDatasetError
from onadata.apps.logger.models.open_data import get_or_create_opendata
from onadata.apps.restservice.models import RestService
from onadata.apps.restservice.viewsets.restservices_viewset import \
    RestServicesViewSet
from onadata.libs.utils.export_tools import get_osm_data_kwargs
from onadata.libs.utils.user_auth import get_user_default_project

MD = """
| survey  |
|         | type              | name  | label   |
|         | select one fruits | fruit | Fruit   |

| choices |
|         | list name         | name   | label  |
|         | fruits            | orange | Orange |
|         | fruits            | mango  | Mango  |
"""

NOT_MATCHING = """
| survey  |
|         | type              | name  | label   |
|         | select one fruits | tunda | Tunda   |

| choices |
|         | list name         | name   | label  |
|         | fruits            | orange | Orange |
|         | fruits            | mango  | Mango  |
"""

# https://github.com/onaio/onadata/issues/1153
REFERENCE_ISSUE = """
| survey  |
|         | type              | name  | label            |
|         | select one fruits | tunda | Tunda            |
|         | select one fruits | fruit | Fruit ${tunda}   |

| choices |
|         | list name         | name   | label           |
|         | fruits            | orange | Orange          |
|         | fruits            | mango  | Mango           |
"""


def streaming_data(response):
    """
    Iterates through a streaming response to return a json list object
    """
    return json.loads(u''.join(
        [i.decode('utf-8') for i in response.streaming_content]))


def _make_submissions_merged_datasets(merged_xform):
    # make submission to form a
    form_a = merged_xform.xforms.all()[0]
    xml = '<data id="a"><fruit>orange</fruit></data>'
    Instance(xform=form_a, xml=xml).save()

    # make submission to form b
    form_b = merged_xform.xforms.all()[1]
    xml = '<data id="b"><fruit>mango</fruit></data>'
    Instance(xform=form_b, xml=xml).save()


class TestMergedXFormViewSet(TestAbstractViewSet):
    """Test merged dataset functionality."""

    def _create_merged_dataset(self, geo=False):
        view = MergedXFormViewSet.as_view({
            'post': 'create',
        })
        # pylint: disable=attribute-defined-outside-init
        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(MD, self.user, id_string='a')
        xform2 = self._publish_markdown(MD, self.user, id_string='b')
        if geo:
            xform2.instances_with_geopoints = True
            xform2.save(update_fields=['instances_with_geopoints'])

        data = {
            'xforms': [
                "http://testserver/api/v1/forms/%s" % xform1.pk,
                "http://testserver/api/v1/forms/%s" % xform2.pk,
            ],
            'name':
            'Merged Dataset',
            'project':
            "http://testserver/api/v1/projects/%s" % self.project.pk,
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
        expected_xforms_data = {
            'id': xform1.pk,
            'title': xform1.title,
            'id_string': xform1.id_string,
            'url': "http://testserver/api/v1/forms/%s" % xform1.pk,
            'num_of_submissions': xform1.num_of_submissions,
            'owner': xform1.user.username,
            'project_id': self.project.pk,
            'project_name': self.project.name
        }
        self.assertEqual(response.data['xforms'][0], expected_xforms_data)

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
        merged_dataset = self._create_merged_dataset(geo=True)
        merged_xform = MergedXForm.objects.get(pk=merged_dataset['id'])

        # make submission to form b
        form_b = merged_xform.xforms.all()[1]
        xml = '<data id="b"><fruit>mango</fruit></data>'
        instance = Instance(xform=form_b, xml=xml)
        instance.save()
        form_b.refresh_from_db()
        form_b.last_submission_time = instance.date_created
        form_b.save()
        view = MergedXFormViewSet.as_view({'get': 'retrieve'})
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
        self.assertEqual(response.data['last_submission_time'],
                         form_b.last_submission_time.isoformat())

        # merged dataset should be available at api/forms/[pk] endpoint
        request = self.factory.get('/', **self.extra)
        view = XFormViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(merged_dataset['id'], response.data['formid'])
        self.assertIn('is_merged_dataset', response.data)
        self.assertTrue(response.data['is_merged_dataset'])
        self.assertTrue(response.data['instances_with_geopoints'])
        self.assertEqual(response.data['num_of_submissions'], 1)
        self.assertEqual(response.data['last_submission_time'],
                         form_b.last_submission_time.isoformat())

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
        xform_detail_view = XFormViewSet.as_view({
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
        last_submission = Instance(xform=form_b, xml=xml)
        last_submission.save()
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        fruit = [d['fruit'] for d in response.data]
        expected_fruit = ['orange', 'mango']
        self.assertEqual(fruit, expected_fruit)

        # check num_of_submissions /merged-datasets/[pk]
        response = detail_view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['num_of_submissions'], 2)

        # check last_submission_time
        self.assertEqual(response.data['last_submission_time'],
                         last_submission.date_created.isoformat())

        # check num_of_submissions /forms/[pk]
        response = xform_detail_view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['num_of_submissions'], 2)

        # check last_submission_time
        self.assertEqual(response.data['last_submission_time'],
                         last_submission.date_created.isoformat())

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

    def test_deleted_forms(self):
        """Test retrieving data of a merged dataset with no forms linked."""
        merged_dataset = self._create_merged_dataset()
        merged_xform = MergedXForm.objects.get(pk=merged_dataset['id'])
        merged_xform.xforms.all().delete()
        request = self.factory.get(
            '/',
            data={
                'sort': '{"_submission_time":1}',
                'limit': '10'
            },
            **self.extra)
        data_view = DataViewSet.as_view({
            'get': 'list',
        })

        # DataViewSet /data/[pk] endpoint
        response = data_view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, [])

        data = {'field_name': 'fruit'}
        view = ChartsViewSet.as_view({'get': 'retrieve'})

        request = self.factory.get('/charts', data, **self.extra)
        response = view(request, pk=merged_dataset['id'], format='html')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data'].__len__(), 0)

    def test_md_csv_export(self):
        """Test CSV export of a merged dataset"""
        merged_dataset = self._create_merged_dataset()
        merged_xform = MergedXForm.objects.get(pk=merged_dataset['id'])

        _make_submissions_merged_datasets(merged_xform)

        # merged dataset should be available at api/forms/[pk] endpoint
        request = self.factory.get('/', **self.extra)
        view = XFormViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=merged_dataset['id'], format='csv')
        self.assertEqual(response.status_code, 200)

        csv_file_obj = StringIO(''.join(
            [c.decode('utf-8') for c in response.streaming_content]))
        csv_reader = csv.reader(csv_file_obj)
        # jump over headers first
        headers = next(csv_reader)
        self.assertEqual(headers, [
            'fruit', 'meta/instanceID', '_id', '_uuid', '_submission_time',
            '_tags', '_notes', '_version', '_duration', '_submitted_by',
            '_total_media', '_media_count', '_media_all_received'])
        row1 = next(csv_reader)
        self.assertEqual(row1[0], 'orange')
        row2 = next(csv_reader)
        self.assertEqual(row2[0], 'mango')

    def test_get_osm_data_kwargs(self):
        """
        Test get_osm_data_kwargs returns correct kwargs for a merged dataset.
        """
        merged_dataset = self._create_merged_dataset()
        merged_xform = MergedXForm.objects.get(pk=merged_dataset['id'])
        pks = [_ for _ in merged_xform.xforms.values_list('id', flat=True)]
        kwargs = get_osm_data_kwargs(merged_xform)
        self.assertEqual(kwargs, {
            'instance__deleted_at__isnull': True,
            'instance__xform_id__in': pks
        })

        xform = merged_xform.xforms.all()[0]
        kwargs = get_osm_data_kwargs(xform)
        self.assertEqual(kwargs, {
            'instance__deleted_at__isnull': True,
            'instance__xform_id': xform.pk
        })

    def test_merged_dataset_charts(self):
        """Test /charts endpoint for a merged dataset works"""

        merged_dataset = self._create_merged_dataset()
        merged_xform = MergedXForm.objects.get(pk=merged_dataset['id'])
        _make_submissions_merged_datasets(merged_xform)

        data = {'field_name': 'fruit'}
        view = ChartsViewSet.as_view({'get': 'retrieve'})

        request = self.factory.get('/charts', data, **self.extra)
        response = view(request, pk=merged_dataset['id'], format='html')
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get('Cache-Control'), None)
        self.assertEqual(response.data['field_type'], 'select one')
        self.assertEqual(response.data['field_name'], 'fruit')
        self.assertEqual(response.data['data_type'], 'categorized')
        self.assertEqual(response.data['data'][0]['fruit'], 'Mango')
        self.assertEqual(response.data['data'][1]['fruit'], 'Orange')

    def test_submissions_not_allowed(self):
        """Test submissions to a merged form is not allowed"""
        merged_dataset = self._create_merged_dataset()
        merged_xform = XForm.objects.get(pk=merged_dataset['id'])

        # make submission to form a
        xml = '<data id="a"><fruit>orange</fruit></data>'
        with self.assertRaises(FormIsMergedDatasetError):
            Instance(xform=merged_xform, xml=xml).save()

    def test_openrosa_form_list(self):
        """Test merged dataset form is not included in /formList"""
        merged_dataset = self._create_merged_dataset()
        merged_xform = XForm.objects.get(pk=merged_dataset['id'])
        view = XFormListViewSet.as_view({"get": "list"})
        request = self.factory.get('/')
        response = view(request, username=self.user.username)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(merged_xform.id_string,
                         [_['formID'] for _ in response.data])

    def test_open_data(self):
        """Test OpenDataViewSet data endpoint"""
        merged_dataset = self._create_merged_dataset()
        merged_xform = MergedXForm.objects.get(pk=merged_dataset['id'])
        _make_submissions_merged_datasets(merged_xform)
        xform = XForm.objects.get(pk=merged_dataset['id'])
        view = OpenDataViewSet.as_view({'get': 'data'})
        _open_data = get_or_create_opendata(xform)[0]
        uuid = _open_data.uuid
        request = self.factory.get('/', **self.extra)
        response = view(request, uuid=uuid)
        self.assertEqual(response.status_code, 200)
        # cast generator response to list so that we can get the response count
        self.assertEqual(len(streaming_data(response)), 2)

    def test_filtered_dataset(self):
        """
        Test a filtered datasets created on a merged xform returns data from
        the linked forms.
        """
        merged_dataset = self._create_merged_dataset()
        xform = XForm.objects.get(pk=merged_dataset['id'])
        _make_submissions_merged_datasets(xform.mergedxform)
        self.assertTrue(xform.is_merged_dataset)
        data = {
            'name': "My DataView",
            'xform': 'http://testserver/api/v1/forms/%s' % xform.pk,
            'project':
            'http://testserver/api/v1/projects/%s' % xform.project.pk,
            # ensure there's an attachment column(photo) in you dataview
            'columns': '["fruit"]'
        }
        view = DataViewViewSet.as_view({'get': 'data'})

        self._create_dataview(data=data, project=xform.project, xform=xform)
        request = self.factory.get('/', **self.extra)
        response = view(request, pk=self.data_view.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_rest_service(self):
        """
        Test rest service creating and deletion for a merged dataset.
        """
        count = RestService.objects.count()
        merged_dataset = self._create_merged_dataset()
        xform = XForm.objects.get(pk=merged_dataset['id'])
        view = RestServicesViewSet.as_view({'post': 'create'})

        post_data = {
            "name": "generic_json",
            "service_url": "http://crunch.goodbot.ai",
            "xform": xform.pk
        }
        request = self.factory.post('/', data=post_data, **self.extra)
        response = view(request)

        self.assertEquals(response.status_code, 201)
        self.assertEquals(count + 3, RestService.objects.count())

        # deleting the service for a merged xform deletes the same service from
        # the individual forms as well.
        service = RestService.objects.get(xform=xform)
        service.delete()
        self.assertEquals(count, RestService.objects.count())

    def test_md_has_deleted_xforms(self):
        """
        Test creating a merged dataset that includes a soft deleted form.
        """
        view = MergedXFormViewSet.as_view({
            'post': 'create',
        })
        # pylint: disable=attribute-defined-outside-init
        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(MD, self.user, id_string='a')
        xform2 = self._publish_markdown(MD, self.user, id_string='b')
        xform2.soft_delete()

        data = {
            'xforms': [
                "http://testserver/api/v1/forms/%s" % xform1.pk,
                "http://testserver/api/v1/forms/%s" % xform2.pk,
            ],
            'name':
            'Merged Dataset',
            'project':
            "http://testserver/api/v1/projects/%s" % self.project.pk,
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {'xforms': [u'Invalid hyperlink - Object does not exist.']})

    def test_md_has_no_matching_fields(self):
        """
        Test creating a merged dataset that has no matching fields.
        """
        view = MergedXFormViewSet.as_view({
            'post': 'create',
        })
        # pylint: disable=attribute-defined-outside-init
        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(MD, self.user, id_string='a')
        xform2 = self._publish_markdown(NOT_MATCHING, self.user, id_string='b')

        data = {
            'xforms': [
                "http://testserver/api/v1/forms/%s" % xform1.pk,
                "http://testserver/api/v1/forms/%s" % xform2.pk,
            ],
            'name':
            'Merged Dataset',
            'project':
            "http://testserver/api/v1/projects/%s" % self.project.pk,
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data,
                         {'xforms': [u'No matching fields in xforms.']})

    def test_md_data_viewset_deleted_form(self):
        """Test retrieving data of a merged dataset with one form deleted"""
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

        # DataViewSet /data/[pk] endpoint, form_a deleted
        form_a.soft_delete()
        response = data_view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        fruit = [d['fruit'] for d in response.data]
        expected_fruit = ['mango']
        self.assertEqual(fruit, expected_fruit)

        # DataViewSet /data/[pk]/[dataid] endpoint, form_a deleted
        data_view = DataViewSet.as_view({
            'get': 'retrieve',
        })
        response = data_view(request, pk=merged_dataset['id'], dataid=dataid)
        self.assertEqual(response.status_code, 404)

    def test_xform_has_uncommon_reference(self):
        """
        Test creating a merged dataset that has matching fields but with
        uncommon reference variable.
        """
        view = MergedXFormViewSet.as_view({
            'post': 'create',
        })
        # pylint: disable=attribute-defined-outside-init
        self.project = get_user_default_project(self.user)
        xform1 = self._publish_markdown(MD, self.user, id_string='a')
        xform2 = self._publish_markdown(
            REFERENCE_ISSUE, self.user, id_string='b')

        data = {
            'xforms': [
                "http://testserver/api/v1/forms/%s" % xform2.pk,
                "http://testserver/api/v1/forms/%s" % xform1.pk,
            ],
            'name':
            'Merged Dataset',
            'project':
            "http://testserver/api/v1/projects/%s" % self.project.pk,
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 400)
        error_message = (
            "There has been a problem trying to replace ${tunda} with the "
            "XPath to the survey element named 'tunda'. There is no survey "
            "element with this name.")
        self.assertIn('xforms', response.data)
        self.assertIn(error_message, response.data['xforms'])

    def test_merged_datasets_deleted_parent_retrieve(self):
        """Test retrieving a specific merged dataset when the parent is deleted
        """
        merged_dataset = self._create_merged_dataset(geo=True)
        merged_xform = MergedXForm.objects.get(pk=merged_dataset['id'])

        # make submission to form b
        form_b = merged_xform.xforms.all()[1]
        xml = '<data id="b"><fruit>mango</fruit></data>'
        instance = Instance(xform=form_b, xml=xml)
        instance.save()
        form_b.refresh_from_db()
        form_b.last_submission_time = instance.date_created
        form_b.save()
        view = MergedXFormViewSet.as_view({'get': 'retrieve'})

        # status_code is 200 when: pk exists, user is authenticated

        request = self.factory.get('/', **self.extra)
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)

        # delete parents
        [parent.delete() for parent in merged_xform.xforms.all()]
        merged_xform.refresh_from_db()

        # merged dataset should be available at api/forms/[pk] endpoint
        request = self.factory.get('/', **self.extra)
        view = XFormViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(merged_dataset['id'], response.data['formid'])
        self.assertTrue(response.data['is_merged_dataset'])
        self.assertTrue(response.data['instances_with_geopoints'])
        # deleted parents, 0 submissions
        self.assertEqual(response.data['num_of_submissions'], 0)
