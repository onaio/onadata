# -*- coding=utf-8 -*-
"""
Test FloipViewset module.
"""
import json
import os

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.floip_viewset import FloipViewSet
from onadata.apps.logger.models import XForm


class TestFloipViewSet(TestAbstractViewSet):
    """
    Test FloipViewSet class.
    """

    def test_publishing_descriptor(self):
        """
        Tests publishing a Flow results descriptor file creates a form.
        """
        xforms = XForm.objects.count()
        self._publish_floip()
        self.assertEqual(xforms + 1, XForm.objects.count())

    def _publish_floip(self):
        view = FloipViewSet.as_view({'post': 'create'})
        path = os.path.join(
            os.path.dirname(__file__), "../", "fixtures",
            "flow-results-example-2-api.json")
        with open(path) as json_file:
            post_data = json_file.read()
            request = self.factory.post(
                '/',
                data=post_data,
                content_type='application/vnd.api+json',
                **self.extra)
            response = view(request)
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response['Content-Type'],
                             'application/vnd.api+json')
            self.assertEqual(response['Location'],
                             'http://testserver/api/v1/flow-results/packages/'
                             + response.data['id'])
            self.assertEqual(response.data['profile'], 'flow-results-package')
            return response.data

    def test_publishing_responses(self):
        """
        Test publishing Flow results.
        """
        floip_data = self._publish_floip()
        view = FloipViewSet.as_view({'post': 'responses'})
        path = os.path.join(
            os.path.dirname(__file__), "../", "fixtures",
            "flow-results-example-2-api-data.json")
        with open(path) as json_file:
            descriptor = json.load(json_file)
            descriptor['data']['id'] = floip_data['id']
            request = self.factory.post(
                '/',
                data=json.dumps(descriptor),
                content_type='application/vnd.api+json',
                **self.extra)
            response = view(request, uuid=floip_data['id'])
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(response['Content-Type'],
                             'application/vnd.api+json')
            self.assertEqual(response['Location'],
                             'http://testserver/api/v1/flow-results/packages/'
                             + floip_data['id'] + '/responses')

    def test_publish_missing_resource_name(self):  # pylint: disable=C0103
        """
        Test publishing a descriptor with missing resource name.
        """
        view = FloipViewSet.as_view({'post': 'create'})
        path = os.path.join(
            os.path.dirname(__file__), "../", "fixtures",
            "flow-results-missing-resource-name.json")
        with open(path) as json_file:
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
            self.assertEqual(
                response.data['text'],
                "The data resource 'standard_test_survey-data'"
                " is not defined.")
