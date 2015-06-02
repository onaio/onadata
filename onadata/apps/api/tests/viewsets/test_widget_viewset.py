from django.contrib.contenttypes.models import ContentType

from onadata.apps.logger.models.widget import Widget
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.widget_viewset import WidgetViewSet
from onadata.apps.logger.models.data_view import DataView

class TestWidgetViewset(TestAbstractViewSet):
    def setUp(self):
        super(self.__class__, self).setUp()
        self._publish_xls_form_to_project()

        self.view = WidgetViewSet.as_view({
            'post': 'create',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy',
            'get': 'retrieve',
            'get': 'list'
        })

    def test_create_widget(self):
        data = {
            'title': "Widget that",
            'content_object': 'http://testserver/api/v1/forms/%s' % self.xform.pk,
            'description': "Test widget",
            'widget_type': "charts",
            'view_type': "horizontal-bar",
            'column': "_submitted_time",
            'group_by': "age"
        }
        count = DataView.objects.all().count()

        request = self.factory.post('/', data=data, **self.extra)
        response = self.view(request)

        import ipdb
        ipdb.set_trace()
        self.assertEquals(response.status_code, 201)
        self.assertEquals(count+1, DataView.objects.all().count())
