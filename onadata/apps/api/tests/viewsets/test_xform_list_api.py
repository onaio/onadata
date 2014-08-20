import os

from django_digest.test import DigestAuth

from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet
from onadata.apps.api.viewsets.xform_list_api import XFormListApi


class TestXFormListApi(TestAbstractViewSet):
    def setUp(self):
        super(self.__class__, self).setUp()
        self.view = XFormListApi.as_view({
            "get": "list"
        })
        self._publish_xls_form_to_project()

    def test_get_xform_list(self):
        request = self.factory.get('/')
        response = self.view(request)
        auth = DigestAuth('bob', 'bobbob')
        request.META.update(auth(request.META, response))
        response = self.view(request)
        self.assertEqual(response.status_code, 200)

        path = os.path.join(
            os.path.dirname(__file__),
            '..', 'fixtures', 'formList.xml')

        with open(path) as f:
            form_list_xml = f.read().strip()
            content = response.render().content.replace(self.xform.hash, '')
            self.assertEqual(content, form_list_xml)
