from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.exceptions import ParseError

from onadata.libs import filters
from onadata.apps.logger.models.widget import Widget
from onadata.libs.serializers.widget_serilizer import WidgetSerializer
from onadata.libs.serializers.data_serializer import JsonDataSerializer
from onadata.apps.api.permissions import WidgetViewSetPermissions
from onadata.libs.utils.chart_tools import build_chart_data_for_field

class WidgetViewSet(ModelViewSet):
    queryset = Widget.objects.all()
    serializer_class = WidgetSerializer
    permission_classes = [WidgetViewSetPermissions]
    lookup_field = 'pk'
    lookup_fields = ('pk', 'widgetid')
    filter_backends = (filters.WidgetFilter,)

    def get_serializer_class(self):
        if self.action == 'data':
            serializer_class = JsonDataSerializer
        else:
            serializer_class = self.serializer_class

        return serializer_class

    def get_object(self, queryset=None):

        pk_lookup, widgetid_lookup = self.lookup_fields
        pk = self.kwargs.get(pk_lookup)
        widgetid = self.kwargs.get(widgetid_lookup)

        if pk is not None and widgetid is not None:
            try:
                int(widgetid)
            except ValueError:
                raise ParseError(_(u"Invalid widgetid %(widgetid)s"
                                   % {'widgetid': widgetid}))

            obj = get_object_or_404(Widget, pk=widgetid, object_id=pk)
            self.check_object_permissions(self.request, obj)
        else:
            raise ParseError(_("Error"))

        return obj

    @action(methods=['GET'])
    def data(self, request, format='json', **kwargs):
        self.object = self.get_object()

        data = build_chart_data_for_field(self.object.content_object,
                                          self.object.column)

        serializer = self.get_serializer(data, many=True)

        return Response(serializer.data)