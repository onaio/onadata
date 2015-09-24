from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from django.contrib.contenttypes.models import ContentType

from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.exceptions import ParseError

from onadata.libs import filters
from onadata.libs.mixins.authenticate_header_mixin import \
    AuthenticateHeaderMixin
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.libs.mixins.etags_mixin import ETagsMixin
from onadata.apps.logger.models.widget import Widget
from onadata.apps.logger.models.data_view import DataView
from onadata.libs.serializers.widget_serilizer import WidgetSerializer
from onadata.apps.api.permissions import WidgetViewSetPermissions
from onadata.apps.api.tools import get_baseviewset_class

BaseViewset = get_baseviewset_class()


class WidgetViewSet(AuthenticateHeaderMixin,
                    CacheControlMixin, ETagsMixin, BaseViewset, ModelViewSet):
    queryset = Widget.objects.all()
    serializer_class = WidgetSerializer
    permission_classes = [WidgetViewSetPermissions]
    lookup_field = 'pk'
    filter_backends = (filters.WidgetFilter,)

    def filter_queryset(self, queryset):
        dataviewid = self.request.QUERY_PARAMS.get('dataview')

        if dataviewid:
            try:
                int(dataviewid)
            except ValueError:
                raise ParseError(
                    u"Invalid value for dataview %s." % dataviewid)

            dataview = get_object_or_404(DataView, pk=dataviewid)
            dataview_ct = ContentType.objects.get_for_model(dataview)
            dataview_qs = Widget.objects.filter(object_id=dataview.pk,
                                                content_type=dataview_ct)
            return dataview_qs

        return super(WidgetViewSet, self).filter_queryset(queryset)

    def get_object(self, queryset=None):

        pk = self.kwargs.get('pk')

        if pk is not None:

            obj = get_object_or_404(Widget, pk=pk)
            self.check_object_permissions(self.request, obj)
        else:
            raise ParseError(_("'pk' required for this action"))

        return obj

    def list(self, request, *args, **kwargs):

        if 'key' in request.GET:
            key = request.GET['key']
            obj = get_object_or_404(Widget, key=key)

            serializer = self.get_serializer(obj)

            return Response(serializer.data)

        return super(WidgetViewSet, self).list(request, *args, **kwargs)
