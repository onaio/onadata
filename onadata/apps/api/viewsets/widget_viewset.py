from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.exceptions import ParseError

from onadata.libs import filters
from onadata.apps.logger.models.widget import Widget
from onadata.libs.serializers.widget_serilizer import WidgetSerializer
from onadata.apps.api.permissions import WidgetViewSetPermissions


class WidgetViewSet(ModelViewSet):
    queryset = Widget.objects.all()
    serializer_class = WidgetSerializer
    permission_classes = [WidgetViewSetPermissions]
    lookup_field = 'pk'
    lookup_fields = ('formid', 'pk')
    filter_backends = (filters.WidgetFilter,)

    def get_object(self, queryset=None):

        formid_lookup, pk_lookup = self.lookup_fields
        pk = self.kwargs.get(pk_lookup)
        formid = self.kwargs.get(formid_lookup)

        if pk is not None and formid is not None:
            try:
                int(formid)
            except ValueError:
                raise ParseError(_(u"Invalid formid %(formid)s"
                                   % {'formid': formid}))

            obj = get_object_or_404(Widget, pk=pk, object_id=formid)
            self.check_object_permissions(self.request, obj)
        else:
            raise ParseError(_("Error"))

        return obj

    def list(self, request, *args, **kwargs):

        if 'key' in request.GET:
            key = request.GET['key']
            obj = get_object_or_404(Widget, key=key)

            serializer = self.get_serializer(obj)
            return Response(serializer.data)

        return super(WidgetViewSet, self).list(request, *args, **kwargs)
