
from onadata.apps.api.tests.viewsets.test_abstract_viewset import\
    TestAbstractViewSet

from onadata.apps.api.viewsets.dataview_viewset import DataViewViewSet


class TestProjectViewSet(TestAbstractViewSet):

    def setUp(self):
        super(self.__class__, self).setUp()
        self._publish_xls_form_to_project()
        self.view = DataViewViewSet.as_view({
            'get': 'list',
            'post': 'create',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy',
            'get': 'retrieve'
        })

    def test_create_dataview(self):
        data = {
            'name': "My DataView",
            'xform': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'project':  'http://testserver/api/v1/projects/%s' % self.project.pk,
            'columns': ["asdasda", "asdasad"],
            'query': [{"sadsa","asdasd"}]
        }

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        self.assertEquals(response.status_code, 201)