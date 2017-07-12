# coding=utf-8
import json

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.merged_xform_viewset import MergedXFormViewSet
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
    def setUp(self):
        super(self.__class__, self).setUp()

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
        self._create_merged_dataset()

    def test_merged_datasets_list(self):
        view = MergedXFormViewSet.as_view({'get': 'list', })
        request = self.factory.get('/')

        # Empty list when there are no merged datasets
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual([], response.data)

        # A list containing the merged datasets
        merged_dataset = self._create_merged_dataset()
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertIn(merged_dataset, response.data)

    def test_merged_datasets_retrieve(self):
        merged_dataset = self._create_merged_dataset()
        view = MergedXFormViewSet.as_view({'get': 'retrieve', })
        request = self.factory.get('/')

        # status_code is 404 when the pk doesn't exist
        response = view(request, pk=(1000 * merged_dataset['id']))
        self.assertEqual(response.status_code, 404)

        # status_code is 200 when the pk exists
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)

        # data has expected fields
        self.assertIn('id', response.data)
        self.assertIn('title', response.data)
        self.assertIn('xforms', response.data)

    def test_retrieve_merged_dataset_form_json(self):
        # create a merged dataset
        merged_dataset = self._create_merged_dataset()

        view = MergedXFormViewSet.as_view({'get': 'form'})
        request = self.factory.get('/')
        response = view(request, pk=merged_dataset['id'], format='json')
        self.assertEqual(response.status_code, 200)

        response.render()
        self.assertEqual('application/json', response['Content-Type'])

        data = json.loads(response.content)
        self.assertIsInstance(data, dict)
        for key in ['children', 'id_string', 'name', 'default_language']:
            self.assertIn(key, data)

    def test_retrieve_merged_dataset_form_xml(self):
        # create a merged dataset
        merged_dataset = self._create_merged_dataset()

        view = MergedXFormViewSet.as_view({'get': 'form'})
        request = self.factory.get('/')
        response = view(request, pk=merged_dataset['id'], format='xml')
        self.assertEqual(response.status_code, 200)

        response.render()
        self.assertEqual('text/xml; charset=utf-8', response['Content-Type'])

    def test_retrieve_merged_dataset_data(self):
        merged_dataset = self._create_merged_dataset()
        request = self.factory.get('/')
        view = MergedXFormViewSet.as_view({'get': 'data'})
        merged_xform = MergedXForm.objects.get(pk=merged_dataset['id'])

        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

        # make submission to form a
        a = merged_xform.xforms.all()[0]
        xml = '<data id="a"><fruits>orange</fruits></data>'
        Instance(xform=a, xml=xml).save()
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        fruits = [d['fruits'] for d in response.data]
        expected_fruits = ['orange']
        self.assertEqual(fruits, expected_fruits)

        # make submission to form b
        b = merged_xform.xforms.all()[1]
        xml = '<data id="b"><fruits>mango</fruits></data>'
        Instance(xform=b, xml=xml).save()
        response = view(request, pk=merged_dataset['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        fruits = [d['fruits'] for d in response.data]
        expected_fruits = ['orange', 'mango']
        self.assertEqual(fruits, expected_fruits)
