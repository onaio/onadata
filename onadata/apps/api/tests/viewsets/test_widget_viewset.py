from django.contrib.contenttypes.models import ContentType

from onadata.apps.logger.models.widget import Widget
from onadata.apps.api.tests.viewsets.test_abstract_viewset import \
    TestAbstractViewSet
from onadata.apps.api.viewsets.widget_viewset import WidgetViewSet

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
        xform_type = ContentType.objects.get(app_label='logger', model='xform')

        widget = Widget(content_object=self.xform,
                        widget_type=Widget.CHARTS,
                        view_type="horizontal-bar",
                        column="_submitted_time",
                        )

        widget.save()
