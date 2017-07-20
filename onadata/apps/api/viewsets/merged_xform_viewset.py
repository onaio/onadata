import json

from django.http import HttpResponseBadRequest
from rest_framework import viewsets
from rest_framework.decorators import detail_route
from rest_framework.response import Response
from rest_framework.settings import api_settings

from onadata.apps.api.permissions import XFormPermissions
from onadata.apps.logger.models import Instance, MergedXForm
from onadata.libs import filters
from onadata.libs.renderers import renderers
from onadata.libs.serializers.merged_xform_serializer import \
    MergedXFormSerializer


class MergedXFormViewSet(viewsets.ModelViewSet):
    """
    Merged XForms viewset: create, list, retrieve, destroy
    """

    filter_backends = (filters.AnonDjangoObjectPermissionFilter,
                       filters.PublicDatasetsFilter)
    permission_classes = [XFormPermissions]
    queryset = MergedXForm.objects.all()
    serializer_class = MergedXFormSerializer

    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES + \
        [renderers.StaticXMLRenderer]

    @detail_route(methods=['get'])
    def form(self, request, *args, **kwargs):

        format = kwargs['format']
        if format not in ['json', 'xml', 'xls']:
            return HttpResponseBadRequest(
                '400 BAD REQUEST', content_type='application/json', status=400)

        merged_xform = self.get_object()
        data = getattr(merged_xform, format)
        if format == 'json':
            data = json.loads(data)

        return Response(data)

    @detail_route(methods=['get'])
    def data(self, request, *args, **kwargs):
        merged_xform = self.get_object()
        qs = Instance.objects.filter(
            xform__in=merged_xform.xforms.all()).order_by('pk')

        return Response(qs.values_list('json', flat=True))
