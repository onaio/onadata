import json

from django.http import HttpResponseBadRequest
from rest_framework import viewsets
from rest_framework.decorators import detail_route
from rest_framework.response import Response
from rest_framework.settings import api_settings

from onadata.apps.logger.models import MergedXForm
from onadata.libs.renderers import renderers
from onadata.libs.serializers.merged_xform_serializer import \
    MergedXFormSerializer


class MergedXFormViewSet(viewsets.ModelViewSet):
    """
    Merged XForms viewset: create, list, retrieve, destroy
    """

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
