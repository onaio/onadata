from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.exceptions import ParseError

from onadata.libs import filters
from onadata.libs.mixins.cache_control_mixin import CacheControlMixin
from onadata.apps.logger.models.widget import Widget
from onadata.libs.serializers.widget_serilizer import WidgetSerializer
from onadata.apps.api.permissions import WidgetViewSetPermissions


class WidgetViewSet(CacheControlMixin, ModelViewSet):
    queryset = Widget.objects.all()
    serializer_class = WidgetSerializer
    permission_classes = [WidgetViewSetPermissions]
    lookup_field = 'pk'
    filter_backends = (filters.WidgetFilter,)

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
