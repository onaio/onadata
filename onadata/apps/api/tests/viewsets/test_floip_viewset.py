# -*- coding=utf-8 -*-
"""
Test FloipViewset module.
"""
import json
import os

from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.floip_viewset import FloipViewSet
from onadata.apps.logger.models import Instance, XForm


class TestFloipViewSet(TestAbstractViewSet):
    """
    Test FloipViewSet class.
    """

    def _publish_floip(self, path='flow-results-example-2-api.json'):
        view = FloipViewSet.as_view({'post': 'create'})
        path = os.path.join(os.path.dirname(__file__), "../", "fixtures", path)
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
        with self.assertRaises(AssertionError) as assert_error:
            self._publish_floip(path='flow-results-example-w-uuid.json')
        self.assertEqual(
            assert_error.exception.message.get('text'),
            'An xform with uuid: ee21fa6f-3027-4bdd-a534-1bb324782b6f already'
            ' exists')
        self.assertEqual(xforms + 1, XForm.objects.count())

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
            self.assertEqual(count + 2, Instance.objects.count())

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

    def test_publish_number_question_names(self):  # pylint: disable=C0103
        """
        Test publishing a descriptor with question identifiers that start with
        a number.
        """
        view = FloipViewSet.as_view({'post': 'create'})
        path = os.path.join(
            os.path.dirname(__file__), "../", "fixtures",
            "flow-results-number-question-names.json")
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
            self.assertIn(
                u"The name '1448506769745_42' is an invalid xml tag",
                response.data['text'])
