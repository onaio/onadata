# -*- coding=utf-8 -*-
"""
Test FloipViewset module.
"""
import json
import os
from builtins import open

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.floip_viewset import FloipViewSet
from onadata.apps.logger.models import Instance, XForm


class TestFloipViewSet(TestAbstractViewSet):
    """
    Test FloipViewSet class.
    """

    def _publish_floip(self,
                       path='flow-results-example-2-api.json',
                       test=True):
        view = FloipViewSet.as_view({'post': 'create'})
        path = os.path.join(os.path.dirname(__file__), "../", "fixtures", path)
        with open(path, encoding='utf-8') as json_file:
            post_data = json_file.read()
            request = self.factory.post(
                '/',
                data=post_data,
                content_type='application/vnd.api+json',
                **self.extra)
            response = view(request)
            if test:
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response['Content-Type'],
                                 'application/vnd.api+json')
                self.assertEqual(
                    response['Location'],
                    'http://testserver/api/v1/flow-results/packages/'
                    + response.data['id'])
                self.assertEqual(response.data['profile'],
                                 'flow-results-package')
            return response.data

    def test_publishing_descriptor(self):
        """
        Tests publishing a Flow results descriptor file creates a form.
        """
        xforms = XForm.objects.count()
        self._publish_floip()
        self.assertEqual(xforms + 1, XForm.objects.count())

    def test_publishing_descriptor_w_id(self):
        """
        Tests publishing a Flow results descriptor file creates a form and
        maintains user defined id.
        """
        xforms = XForm.objects.count()
        data = self._publish_floip(path='flow-results-example-w-uuid.json')
        self.assertEqual(data['id'], 'ee21fa6f-3027-4bdd-a534-1bb324782b6f')
        response = self._publish_floip(path='flow-results-example-w-uuid.json',
                                       test=False)
        self.assertEqual(
            response['text'],
            'An xform with uuid: ee21fa6f-3027-4bdd-a534-1bb324782b6f already'
            ' exists')
        self.assertEqual(xforms + 1, XForm.objects.count())

    def test_list_package(self):
        """
        Test list endpoint for packages.
        """
        view = FloipViewSet.as_view({'get': 'list'})
        data = self._publish_floip(path='flow-results-example-w-uuid.json')
        request = self.factory.get(
            '/flow-results/packages',
            content_type='application/vnd.api+json', **self.extra)
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('created', response.data[0])
        self.assertIn('modified', response.data[0])
        self.assertEqual(response.data[0]['name'], data['name'])
        self.assertEqual(response.data[0]['title'], data['title'])
        self.assertEqual(response.data[0]['id'], data['id'])

        # render and change that JSON API returns the same id/uuid
        response.render()
        rendered_data = json.loads(response.rendered_content)
        self.assertEqual(rendered_data['data'][0]['id'], data['id'])
        self.assertEqual(rendered_data['data'][0]['type'], 'packages')

    def test_retrieve_package(self):
        """
        Test retrieving a specific package.
        """
        view = FloipViewSet.as_view({'get': 'retrieve'})
        data = self._publish_floip(path='flow-results-example-w-uuid.json')
        request = self.factory.get(
            '/flow-results/packages/' + data['id'],
            content_type='application/vnd.api+json', **self.extra)
        response = view(request, uuid=data['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, data)

        # render and change that JSON API returns the same id/uuid
        response.render()
        rendered_data = json.loads(response.rendered_content)
        self.assertEqual(rendered_data['data']['id'], data['id'])

    def test_update_package(self):
        """
        Test updating a specific package.
        """
        view = FloipViewSet.as_view({'put': 'update'})
        data = self._publish_floip(path='flow-results-example-w-uuid.json')
        question = 'f1448506774982_01'
        self.assertNotIn(question, data['resources'][0]['schema']['questions'])
        path = os.path.join(os.path.dirname(__file__), "../", "fixtures",
                            'flow-results-example-w-uuid-update.json')
        with open(path, encoding='utf-8') as json_file:
            post_data = json_file.read()
            request = self.factory.put(
                '/flow-results/packages/' + data['id'],
                data=post_data, content_type='application/vnd.api+json',
                **self.extra)
            response = view(request, uuid=data['id'])
            self.assertEqual(response.status_code, 200)
            response.render()
            self.assertEqual(response['Content-Type'],
                             'application/vnd.api+json')
            self.assertEqual(response.data['profile'], 'flow-results-package')
            self.assertIn(question,
                          response.data['resources'][0]['schema']['questions'])

    def test_publishing_responses(self):
        """
        Test publishing Flow results.
        """
        count = Instance.objects.count()
        floip_data = self._publish_floip()
        view = FloipViewSet.as_view({'post': 'responses'})
        path = os.path.join(
            os.path.dirname(__file__), "../", "fixtures",
            "flow-results-example-2-api-data.json")
        with open(path, encoding='utf-8') as json_file:
            descriptor = json.load(json_file)
            descriptor['data']['id'] = floip_data['id']
            request = self.factory.post(
                '/',
                data=json.dumps(descriptor),
                content_type='application/vnd.api+json',
                **self.extra)
            response = view(request, uuid=floip_data['id'])
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response['Content-Type'],
                             'application/vnd.api+json')
            self.assertEqual(response['Location'],
                             'http://testserver/api/v1/flow-results/packages/'
                             + floip_data['id'] + '/responses')
            self.assertEqual(count + 2, Instance.objects.count())

            request = self.factory.post(
                '/',
                data=json.dumps(descriptor),
                content_type='application/vnd.api+json',
                **self.extra)
            response = view(request, uuid=floip_data['id'])
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response['Content-Type'],
                             'application/vnd.api+json')
            self.assertEqual(response['Location'],
                             'http://testserver/api/v1/flow-results/packages/'
                             + floip_data['id'] + '/responses')
            self.assertEqual(count + 2, Instance.objects.count())

    def test_publish_number_question_names(self):  # pylint: disable=C0103
        """
        Test publishing a descriptor with question identifiers that start with
        a number.
        """
        view = FloipViewSet.as_view({'post': 'create'})
        path = os.path.join(
            os.path.dirname(__file__), "../", "fixtures",
            "flow-results-number-question-names.json")
        with open(path, encoding='utf-8') as json_file:
            post_data = json_file.read()
            request = self.factory.post(
                '/',
                data=post_data,
                content_type='application/vnd.api+json',
                **self.extra)
            response = view(request)
            response.render()
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response['Content-Type'],
                             'application/vnd.api+json')
            self.assertIn(
                u"The name '1448506769745_42' is an invalid xml tag",
                response.data['text'])
